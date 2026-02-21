from __future__ import annotations

from collections.abc import Mapping
import logging
import time
from typing import Any

import httpx

from accloud.config import AppConfig
from accloud.models import SessionData
from accloud.utils import backoff_seconds, is_retryable_status, redact_mapping


class CloudHttpClient:
    """HTTP transport skeleton with safe logging and retry/backoff."""

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
            headers={"User-Agent": config.user_agent},
            follow_redirects=True,
        )

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
        **kwargs: Any,
    ) -> httpx.Response:
        merged_headers = dict(self._session_data.auth_headers())
        if headers:
            merged_headers.update(headers)

        safe_headers = redact_mapping(merged_headers)
        self._logger.debug("HTTP request method=%s url=%s headers=%s", method, url, safe_headers)

        attempt = 0
        while True:
            response = self._client.request(method, url, headers=merged_headers, **kwargs)
            if attempt >= self._config.retry.max_attempts - 1:
                return response
            if not is_retryable_status(response.status_code):
                return response

            delay_s = backoff_seconds(
                attempt=attempt,
                base_delay_s=self._config.retry.base_delay_s,
                max_delay_s=self._config.retry.max_delay_s,
            )
            self._logger.warning(
                "Retrying request method=%s url=%s status=%s attempt=%s delay_s=%.2f",
                method,
                url,
                response.status_code,
                attempt + 1,
                delay_s,
            )
            response.close()
            time.sleep(delay_s)
            attempt += 1

