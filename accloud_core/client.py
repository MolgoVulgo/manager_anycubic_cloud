from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import logging
import threading
import time
from typing import Any
from urllib.parse import urlparse
from uuid import uuid1, uuid4

import httpx

from accloud_core.config import AppConfig
from accloud_core.errors import CloudApiError, CloudTransportError
from accloud_core.logging_contract import emit_event, get_op_id
from accloud_core.models import SessionData
from accloud_core.utils import (
    backoff_seconds,
    is_retryable_status,
    redact_json_like,
    redact_mapping,
    safe_url_for_log,
    truncate_text,
    url_log_parts,
)


LOGIN_WITH_ACCESS_TOKEN_PATH = "/p/p/workbench/api/v3/public/loginWithAccessToken"
OAUTH_TOKEN_EXCHANGE_PATH = "/p/p/workbench/api/v3/public/getoauthToken"
AUTH_RECOVERY_STATUS_CODES = {401, 403}


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
        self._auth_recovery_lock = threading.Lock()

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
        include_session_headers: bool = True,
        op_id: str | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        active_op_id = str(op_id).strip() or get_op_id()
        safe_url = safe_url_for_log(url)
        safe_json = self._safe_json_payload(kwargs.get("json"))
        safe_url_parts = url_log_parts(url)

        attempt = 0
        last_error: Exception | None = None
        max_attempts = self._config.retry.max_attempts
        auth_recovery_attempted = False

        while attempt < max_attempts:
            request_headers = self._build_headers(
                url=url,
                headers=headers,
                include_session_headers=include_session_headers,
            )
            request_id = request_headers.get("X-Request-Id", "")
            safe_headers = redact_mapping(request_headers)
            http_context = {
                "method": method.upper(),
                "url_base": safe_url_parts.get("url_base", safe_url),
                "query_keys": safe_url_parts.get("query_keys", []),
                "attempt": attempt + 1,
                "timeout_s": self._config.timeout_s,
            }
            query_hash = safe_url_parts.get("url.query_hash")
            if isinstance(query_hash, str) and query_hash:
                http_context["query_hash"] = query_hash
            bytes_out = self._estimate_request_bytes(kwargs)
            if bytes_out is not None:
                http_context["bytes_out"] = bytes_out

            emit_event(
                self._logger,
                logging.INFO,
                event="http.request",
                msg="HTTP request",
                component="accloud.http",
                op_id=active_op_id,
                req_id=request_id,
                data={"headers": safe_headers, "json": safe_json},
                http=http_context,
            )
            start_s = time.perf_counter()
            try:
                response = self._client.request(method, url, headers=request_headers, **kwargs)
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt >= max_attempts - 1:
                    emit_event(
                        self._logger,
                        logging.ERROR,
                        event="http.error",
                        msg="HTTP timeout",
                        component="accloud.http",
                        op_id=active_op_id,
                        req_id=request_id,
                        http=http_context,
                        error={"type": type(exc).__name__, "message": str(exc)},
                    )
                    raise CloudTransportError(f"Timeout during {method} {safe_url}") from exc
                self._sleep_before_retry(
                    method=method,
                    url_parts=safe_url_parts,
                    attempt=attempt,
                    reason="timeout",
                    op_id=active_op_id,
                    req_id=request_id,
                )
                attempt += 1
                continue
            except httpx.TransportError as exc:
                last_error = exc
                if attempt >= max_attempts - 1:
                    emit_event(
                        self._logger,
                        logging.ERROR,
                        event="http.error",
                        msg="HTTP transport error",
                        component="accloud.http",
                        op_id=active_op_id,
                        req_id=request_id,
                        http=http_context,
                        error={"type": type(exc).__name__, "message": str(exc)},
                    )
                    raise CloudTransportError(f"Transport error during {method} {safe_url}") from exc
                self._sleep_before_retry(
                    method=method,
                    url_parts=safe_url_parts,
                    attempt=attempt,
                    reason="transport",
                    op_id=active_op_id,
                    req_id=request_id,
                )
                attempt += 1
                continue

            elapsed_ms = (time.perf_counter() - start_s) * 1000.0
            bytes_in = self._estimate_response_bytes(response)
            response_http_context = {
                **http_context,
                "status": response.status_code,
            }
            if bytes_in is not None:
                response_http_context["bytes_in"] = bytes_in
            emit_event(
                self._logger,
                logging.INFO,
                event="http.response",
                msg="HTTP response",
                component="accloud.http",
                op_id=active_op_id,
                req_id=request_id,
                duration_ms=elapsed_ms,
                http=response_http_context,
            )

            if (
                response.status_code in AUTH_RECOVERY_STATUS_CODES
                and self._should_attempt_auth_recovery(
                    url=url,
                    method=method,
                    already_attempted=auth_recovery_attempted,
                )
            ):
                response.close()
                if self._attempt_auth_recovery(
                    trigger_method=method,
                    trigger_url=url,
                    trigger_status=response.status_code,
                    op_id=active_op_id,
                    req_id=request_id,
                ):
                    auth_recovery_attempted = True
                    continue
                emit_event(
                    self._logger,
                    logging.ERROR,
                    event="http.error",
                    msg="Authentication recovery failed",
                    component="accloud.http",
                    op_id=active_op_id,
                    req_id=request_id,
                    http=response_http_context,
                )
                raise CloudApiError(
                    f"Authentication failed for {method} {safe_url}: {response.status_code}",
                    status_code=response.status_code,
                )

            if is_retryable_status(response.status_code) and attempt < max_attempts - 1:
                self._sleep_before_retry(
                    method=method,
                    url_parts=safe_url_parts,
                    attempt=attempt,
                    reason=f"status={response.status_code}",
                    op_id=active_op_id,
                    req_id=request_id,
                )
                response.close()
                attempt += 1
                continue

            if expected_status is not None and not self._status_matches(response.status_code, expected_status):
                response_text = truncate_text(response.text, max_len=1200)
                emit_event(
                    self._logger,
                    logging.ERROR,
                    event="http.error",
                    msg="HTTP unexpected status",
                    component="accloud.http",
                    op_id=active_op_id,
                    req_id=request_id,
                    data={"expected_status": expected_status, "body": response_text},
                    http=response_http_context,
                )
                raise CloudApiError(
                    f"Unexpected status for {method} {safe_url}: {response.status_code}",
                    status_code=response.status_code,
                )

            return response

        emit_event(
            self._logger,
            logging.ERROR,
            event="http.error",
            msg="Retry budget exhausted",
            component="accloud.http",
            op_id=active_op_id,
            http={
                "method": method.upper(),
                "url_base": safe_url_parts.get("url_base", safe_url),
                "query_keys": safe_url_parts.get("query_keys", []),
            },
        )
        raise CloudTransportError(f"Retry budget exhausted for {method} {safe_url}") from last_error

    def request_json(
        self,
        method: str,
        url: str,
        *,
        expected_status: int | tuple[int, ...] = 200,
        op_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        active_op_id = str(op_id).strip() or get_op_id()
        safe_url_parts = url_log_parts(url)
        response = self.request(
            method,
            url,
            expected_status=expected_status,
            op_id=active_op_id,
            **kwargs,
        )
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            text = truncate_text(response.text, max_len=1000)
            req_id = response.request.headers.get("X-Request-Id", "")
            emit_event(
                self._logger,
                logging.ERROR,
                event="http.error",
                msg="HTTP invalid JSON response",
                component="accloud.http",
                op_id=active_op_id,
                req_id=req_id,
                data={"body": text},
                http={
                    "method": method.upper(),
                    "url_base": safe_url_parts.get("url_base", safe_url_for_log(url)),
                    "query_keys": safe_url_parts.get("query_keys", []),
                    "status": response.status_code,
                },
                error={"type": type(exc).__name__, "message": str(exc)},
            )
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
        emit_event(
            self._logger,
            logging.ERROR,
            event="http.error",
            msg="HTTP unexpected JSON shape",
            component="accloud.http",
            op_id=active_op_id,
            data={"shape": type(payload).__name__},
            http={
                "method": method.upper(),
                "url_base": safe_url_parts.get("url_base", safe_url_for_log(url)),
                "query_keys": safe_url_parts.get("query_keys", []),
                "status": response.status_code,
            },
        )
        raise CloudApiError(
            f"Unexpected JSON shape for {method} {safe_url_for_log(url)}: {type(payload).__name__}",
            status_code=response.status_code,
        )

    def _build_headers(
        self,
        *,
        url: str,
        headers: Mapping[str, str] | None = None,
        include_session_headers: bool = True,
    ) -> dict[str, str]:
        merged_headers = dict(self._session_data.auth_headers()) if include_session_headers else {}
        if include_session_headers and self._is_workbench_api(url):
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

    @staticmethod
    def _estimate_request_bytes(kwargs: Mapping[str, Any]) -> int | None:
        json_payload = kwargs.get("json")
        if json_payload is not None:
            try:
                return len(json.dumps(json_payload, ensure_ascii=True, default=str).encode("utf-8"))
            except (TypeError, ValueError):
                return None

        content = kwargs.get("content")
        if isinstance(content, (bytes, bytearray)):
            return len(content)
        if isinstance(content, str):
            return len(content.encode("utf-8"))
        return None

    @staticmethod
    def _estimate_response_bytes(response: httpx.Response) -> int | None:
        content_length = response.headers.get("Content-Length")
        if content_length and str(content_length).strip().isdigit():
            return int(str(content_length).strip())
        return None

    def _should_attempt_auth_recovery(self, *, url: str, method: str, already_attempted: bool) -> bool:
        _ = method
        if already_attempted:
            return False
        if not self._is_workbench_api(url):
            return False
        path = self._normalized_path(url)
        if path in {LOGIN_WITH_ACCESS_TOKEN_PATH, OAUTH_TOKEN_EXCHANGE_PATH}:
            return False
        return bool(self._auth_recovery_candidates())

    def _attempt_auth_recovery(
        self,
        *,
        trigger_method: str,
        trigger_url: str,
        trigger_status: int,
        op_id: str,
        req_id: str | None,
    ) -> bool:
        safe_trigger_url_parts = url_log_parts(trigger_url)
        trigger_http_context = {
            "method": trigger_method.upper(),
            "url_base": safe_trigger_url_parts.get("url_base", safe_url_for_log(trigger_url)),
            "query_keys": safe_trigger_url_parts.get("query_keys", []),
            "status": trigger_status,
        }
        with self._auth_recovery_lock:
            candidates = self._auth_recovery_candidates()
            if not candidates:
                emit_event(
                    self._logger,
                    logging.WARNING,
                    event="http.retry",
                    msg="HTTP auth recovery skipped",
                    component="accloud.http",
                    op_id=op_id,
                    req_id=req_id,
                    data={"reason": "no-candidates"},
                    http=trigger_http_context,
                )
                return False

            emit_event(
                self._logger,
                logging.WARNING,
                event="http.retry",
                msg="HTTP auth recovery started",
                component="accloud.http",
                op_id=op_id,
                req_id=req_id,
                data={"candidates": len(candidates)},
                http=trigger_http_context,
            )

            for candidate in candidates:
                recovered_tokens = self._login_with_access_token(
                    candidate,
                    op_id=op_id,
                    req_id=req_id,
                )
                if recovered_tokens is None:
                    continue
                self.update_session(SessionData(tokens=self._merge_session_tokens(recovered_tokens)))
                emit_event(
                    self._logger,
                    logging.INFO,
                    event="http.response",
                    msg="HTTP auth recovery succeeded",
                    component="accloud.http",
                    op_id=op_id,
                    req_id=req_id,
                    http=trigger_http_context,
                )
                return True

            emit_event(
                self._logger,
                logging.ERROR,
                event="http.error",
                msg="HTTP auth recovery failed",
                component="accloud.http",
                op_id=op_id,
                req_id=req_id,
                http=trigger_http_context,
            )
            return False

    def _auth_recovery_candidates(self) -> list[str]:
        tokens = self._session_data.tokens
        ordered_candidates = (
            str(tokens.get("id_token", "")).strip(),
            str(tokens.get("access_token", "")).strip(),
            str(tokens.get("token", "")).strip(),
            str(tokens.get("Authorization", "")).strip(),
        )
        selected: list[str] = []
        seen: set[str] = set()
        for raw in ordered_candidates:
            normalized = self._strip_bearer(raw)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            selected.append(normalized)
        return selected

    def _login_with_access_token(
        self,
        access_token: str,
        *,
        op_id: str,
        req_id: str | None,
    ) -> dict[str, str] | None:
        attempts = (
            {"access_token": access_token, "device_type": "web"},
            {"accessToken": access_token, "device_type": "web"},
            {"accessToken": access_token},
        )
        safe_url_parts = url_log_parts(LOGIN_WITH_ACCESS_TOKEN_PATH)

        for payload in attempts:
            headers = self._build_headers(url=LOGIN_WITH_ACCESS_TOKEN_PATH, headers=None)
            request_id = headers.get("X-Request-Id", "")
            safe_headers = redact_mapping(headers)
            safe_payload = self._safe_json_payload(payload)
            http_context = {
                "method": "POST",
                "url_base": safe_url_parts.get("url_base", LOGIN_WITH_ACCESS_TOKEN_PATH),
                "query_keys": safe_url_parts.get("query_keys", []),
                "attempt": 1,
                "timeout_s": self._config.timeout_s,
            }
            try:
                emit_event(
                    self._logger,
                    logging.INFO,
                    event="http.request",
                    msg="HTTP auth recovery request",
                    component="accloud.http",
                    op_id=op_id,
                    req_id=request_id,
                    data={"headers": safe_headers, "json": safe_payload, "trigger_req_id": req_id},
                    http=http_context,
                )
                start_s = time.perf_counter()
                response = self._client.request(
                    "POST",
                    LOGIN_WITH_ACCESS_TOKEN_PATH,
                    headers=headers,
                    json=payload,
                )
            except httpx.TransportError as exc:
                emit_event(
                    self._logger,
                    logging.WARNING,
                    event="http.retry",
                    msg="HTTP auth recovery transport error",
                    component="accloud.http",
                    op_id=op_id,
                    req_id=request_id,
                    http=http_context,
                    error={"type": type(exc).__name__, "message": str(exc)},
                )
                continue

            try:
                elapsed_ms = (time.perf_counter() - start_s) * 1000.0
                emit_event(
                    self._logger,
                    logging.INFO,
                    event="http.response",
                    msg="HTTP auth recovery response",
                    component="accloud.http",
                    op_id=op_id,
                    req_id=request_id,
                    duration_ms=elapsed_ms,
                    http={
                        **http_context,
                        "status": response.status_code,
                        "bytes_in": self._estimate_response_bytes(response),
                    },
                )
                if response.status_code not in {200, 201}:
                    continue
                try:
                    payload_json = response.json()
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload_json, dict):
                    continue
                if not self._payload_is_business_success(payload_json):
                    continue
                extracted = self._extract_tokens_from_login_payload(payload_json)
                if extracted:
                    return extracted
            finally:
                response.close()
        return None

    @staticmethod
    def _payload_is_business_success(payload: Mapping[str, Any]) -> bool:
        if "code" not in payload:
            return True
        try:
            return int(payload.get("code")) == 1
        except (TypeError, ValueError):
            return False

    def _extract_tokens_from_login_payload(self, payload: Mapping[str, Any]) -> dict[str, str]:
        data = payload.get("data")
        data_map: Mapping[str, Any] = data if isinstance(data, dict) else {}

        access_token = self._first_non_empty(data_map, payload, "access_token", "accessToken")
        id_token = self._first_non_empty(data_map, payload, "id_token", "idToken")
        session_token = self._first_non_empty(data_map, payload, "token")
        refresh_token = self._first_non_empty(data_map, payload, "refresh_token", "refreshToken")

        access_token = self._strip_bearer(access_token)
        id_token = self._strip_bearer(id_token)
        session_token = self._strip_bearer(session_token)
        refresh_token = self._strip_bearer(refresh_token)

        extracted: dict[str, str] = {}
        if access_token:
            extracted["access_token"] = access_token
            extracted["Authorization"] = f"Bearer {access_token}"
        if id_token:
            extracted["id_token"] = id_token
        elif access_token:
            extracted["id_token"] = access_token
        if session_token:
            extracted["token"] = session_token
        if refresh_token:
            extracted["refresh_token"] = refresh_token
        return extracted

    @staticmethod
    def _first_non_empty(primary: Mapping[str, Any], secondary: Mapping[str, Any], *keys: str) -> str:
        for key in keys:
            value_primary = str(primary.get(key, "")).strip()
            if value_primary:
                return value_primary
            value_secondary = str(secondary.get(key, "")).strip()
            if value_secondary:
                return value_secondary
        return ""

    def _merge_session_tokens(self, incoming: Mapping[str, str]) -> dict[str, str]:
        merged = dict(self._session_data.tokens)
        merged.update({str(key): str(value) for key, value in incoming.items()})

        access_token = self._strip_bearer(str(merged.get("access_token", "")).strip())
        if not access_token:
            access_token = self._strip_bearer(str(merged.get("Authorization", "")).strip())
        if access_token:
            merged["access_token"] = access_token
            merged["Authorization"] = f"Bearer {access_token}"
            merged.setdefault("id_token", access_token)

        id_token = self._strip_bearer(str(merged.get("id_token", "")).strip())
        if id_token:
            merged["id_token"] = id_token

        session_token = self._strip_bearer(str(merged.get("token", "")).strip())
        if session_token:
            merged["token"] = session_token

        refresh_token = self._strip_bearer(str(merged.get("refresh_token", "")).strip())
        if refresh_token:
            merged["refresh_token"] = refresh_token

        return merged

    @staticmethod
    def _strip_bearer(value: str) -> str:
        raw = str(value).strip()
        if not raw:
            return ""
        if raw.lower().startswith("bearer "):
            return raw[7:].strip()
        return raw

    def _sleep_before_retry(
        self,
        *,
        method: str,
        url_parts: Mapping[str, Any],
        attempt: int,
        reason: str,
        op_id: str,
        req_id: str | None,
    ) -> None:
        delay_s = backoff_seconds(
            attempt=attempt,
            base_delay_s=self._config.retry.base_delay_s,
            max_delay_s=self._config.retry.max_delay_s,
        )
        emit_event(
            self._logger,
            logging.WARNING,
            event="http.retry",
            msg="HTTP retry scheduled",
            component="accloud.http",
            op_id=op_id,
            req_id=req_id,
            data={"reason": reason},
            http={
                "method": method.upper(),
                "url_base": url_parts.get("url_base"),
                "query_keys": url_parts.get("query_keys", []),
                "attempt": attempt + 1,
                "timeout_s": self._config.timeout_s,
            },
            duration_ms=delay_s * 1000.0,
        )
        time.sleep(delay_s)
