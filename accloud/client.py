from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import logging
import time
from typing import Any
from urllib.parse import urlparse
from uuid import uuid1, uuid4

import httpx

from accloud.config import AppConfig
from accloud.errors import CloudApiError, CloudTransportError
from accloud.models import SessionData
from accloud.utils import (
    backoff_seconds,
    is_retryable_status,
    redact_json_like,
    redact_mapping,
    safe_url_for_log,
    truncate_text,
)


class CloudHttpClient:
    """HTTP transport with retry/backoff and safe logging."""

    def __init__(
        self,
        config: AppConfig,
        session_data: SessionData | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._config = config
        self._session_data = session_data or SessionData()
        self._logger = logger or logging.getLogger("accloud.http")

        self._client = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout_s,
            headers={
                "User-Agent": config.user_agent,
                "X-Client-Version": config.client_version,
                "X-Region": config.region,
                "X-Device-Id": config.device_id,
            },
            follow_redirects=True,
        )
        self.update_session(self._session_data)

    @property
    def session_data(self) -> SessionData:
        return self._session_data

    def update_session(self, session_data: SessionData) -> None:
        self._session_data = session_data

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CloudHttpClient":
        return self

    def __exit__(self, exc_type: object, exc: BaseException | None, tb: object) -> None:
        self.close()

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        expected_status: int | tuple[int, ...] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        request_headers = self._build_headers(url=url, headers=headers)
        request_id = request_headers.get("X-Request-Id", "")
        safe_headers = redact_mapping(request_headers)
        safe_url = safe_url_for_log(url)
        safe_json = self._safe_json_payload(kwargs.get("json"))

        self._logger.debug(
            "HTTP request method=%s url=%s request_id=%s headers=%s json=%s",
            method,
            safe_url,
            request_id,
            safe_headers,
            safe_json,
        )

        attempt = 0
        last_error: Exception | None = None
        max_attempts = self._config.retry.max_attempts

        while attempt < max_attempts:
            start_s = time.perf_counter()
            try:
                response = self._client.request(method, url, headers=request_headers, **kwargs)
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt >= max_attempts - 1:
                    raise CloudTransportError(f"Timeout during {method} {safe_url}") from exc
                self._sleep_before_retry(method, safe_url, attempt, reason="timeout")
                attempt += 1
                continue
            except httpx.TransportError as exc:
                last_error = exc
                if attempt >= max_attempts - 1:
                    raise CloudTransportError(f"Transport error during {method} {safe_url}") from exc
                self._sleep_before_retry(method, safe_url, attempt, reason="transport")
                attempt += 1
                continue

            elapsed_ms = (time.perf_counter() - start_s) * 1000.0
            self._logger.info(
                "HTTP response method=%s url=%s request_id=%s status=%s elapsed_ms=%.2f",
                method,
                safe_url,
                request_id,
                response.status_code,
                elapsed_ms,
            )

            if expected_status is not None and not self._status_matches(response.status_code, expected_status):
                response_text = truncate_text(response.text, max_len=1200)
                self._logger.error(
                    "HTTP unexpected-status method=%s url=%s request_id=%s expected=%s got=%s body=%s",
                    method,
                    safe_url,
                    request_id,
                    expected_status,
                    response.status_code,
                    response_text,
                )
                raise CloudApiError(
                    f"Unexpected status for {method} {safe_url}: {response.status_code}",
                    status_code=response.status_code,
                )

            if is_retryable_status(response.status_code) and attempt < max_attempts - 1:
                self._sleep_before_retry(method, safe_url, attempt, reason=f"status={response.status_code}")
                response.close()
                attempt += 1
                continue

            return response

        raise CloudTransportError(f"Retry budget exhausted for {method} {safe_url}") from last_error

    def request_json(
        self,
        method: str,
        url: str,
        *,
        expected_status: int | tuple[int, ...] = 200,
        **kwargs: Any,
    ) -> dict[str, Any]:
        response = self.request(
            method,
            url,
            expected_status=expected_status,
            **kwargs,
        )
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            text = truncate_text(response.text, max_len=1000)
            raise CloudApiError(
                f"Invalid JSON response for {method} {safe_url_for_log(url)}: {text}",
                status_code=response.status_code,
            ) from exc
        finally:
            response.close()

        if isinstance(payload, dict):
            return payload
        if isinstance(payload, list):
            return {"data": payload}
        raise CloudApiError(
            f"Unexpected JSON shape for {method} {safe_url_for_log(url)}: {type(payload).__name__}",
            status_code=response.status_code,
        )

    def _build_headers(self, *, url: str, headers: Mapping[str, str] | None = None) -> dict[str, str]:
        merged_headers = dict(self._session_data.auth_headers())
        if self._is_workbench_api(url):
            merged_headers.update(self._build_public_headers(url=url))
        if headers:
            merged_headers.update(headers)
        merged_headers.setdefault("X-Request-Id", str(uuid4()))
        return merged_headers

    def _build_public_headers(self, *, url: str) -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        nonce = str(uuid1())
        token = self._resolve_public_token()

        public_headers: dict[str, str] = {
            "XX-Device-Type": self._config.public_device_type,
            "XX-IS-CN": self._config.public_is_cn,
            "XX-Version": self._config.public_version,
            "XX-Nonce": nonce,
            "XX-Timestamp": timestamp,
        }
        if token:
            public_headers["XX-Token"] = token

        public_headers["XX-Signature"] = self._compute_public_signature(
            url=url,
            timestamp=timestamp,
            nonce=nonce,
            token=token,
        )
        return public_headers

    def _compute_public_signature(self, *, url: str, timestamp: str, nonce: str, token: str) -> str:
        # JS formula from working legacy client:
        # md5(appid + timestamp + version + appSecret + nonce + appid)
        _ = url  # preserved argument for call compatibility
        _ = token
        base = (
            f"{self._config.public_app_id}"
            f"{timestamp}"
            f"{self._config.public_version}"
            f"{self._config.public_app_secret}"
            f"{nonce}"
            f"{self._config.public_app_id}"
        )
        return hashlib.md5(base.encode("utf-8"), usedforsecurity=False).hexdigest()

    def _resolve_public_token(self) -> str:
        tokens = self._session_data.tokens
        token = str(tokens.get("token", "")).strip()
        return token

    @staticmethod
    def _is_workbench_api(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return "/p/p/workbench/api/" in parsed.path
        return "/p/p/workbench/api/" in url

    @staticmethod
    def _normalized_path(url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return parsed.path or "/"
        return str(url).split("?", 1)[0]

    @staticmethod
    def _status_matches(status_code: int, expected_status: int | tuple[int, ...]) -> bool:
        if isinstance(expected_status, tuple):
            return status_code in expected_status
        return status_code == expected_status

    @staticmethod
    def _safe_json_payload(payload: Any) -> Any:
        if payload is None:
            return None
        return redact_json_like(payload)

    def _sleep_before_retry(self, method: str, safe_url: str, attempt: int, reason: str) -> None:
        delay_s = backoff_seconds(
            attempt=attempt,
            base_delay_s=self._config.retry.base_delay_s,
            max_delay_s=self._config.retry.max_delay_s,
        )
        self._logger.warning(
            "HTTP retry method=%s url=%s attempt=%s/%s reason=%s delay_s=%.2f",
            method,
            safe_url,
            attempt + 1,
            self._config.retry.max_attempts,
            reason,
            delay_s,
        )
        time.sleep(delay_s)
