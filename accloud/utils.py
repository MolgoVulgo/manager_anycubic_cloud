from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any


SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-access-token",
    "x-auth-token",
}

SENSITIVE_JSON_KEYS = {
    "access_token",
    "authorization",
    "cookie",
    "password",
    "refresh_token",
    "secret",
    "signature",
    "token",
}


def redact_value(value: Any) -> str:
    if value is None:
        return "<redacted:none>"
    return "<redacted>"


def redact_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in values.items():
        if key.lower() in SENSITIVE_HEADER_NAMES or key.lower() in SENSITIVE_JSON_KEYS:
            redacted[key] = redact_value(value)
            continue
        redacted[key] = redact_json_like(value)
    return redacted


def redact_json_like(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, nested_value in value.items():
            if str(key).lower() in SENSITIVE_JSON_KEYS:
                redacted[str(key)] = redact_value(nested_value)
            else:
                redacted[str(key)] = redact_json_like(nested_value)
        return redacted
    if isinstance(value, list):
        return [redact_json_like(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_json_like(item) for item in value)
    return value


def truncate_text(text: str, max_len: int = 2000) -> str:
    if max_len < 0:
        raise ValueError("max_len must be >= 0")
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}...<truncated:{len(text) - max_len}>"


def is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code <= 599


def backoff_seconds(attempt: int, base_delay_s: float, max_delay_s: float) -> float:
    if attempt < 0:
        raise ValueError("attempt must be >= 0")
    unclamped = base_delay_s * math.pow(2, attempt)
    return min(unclamped, max_delay_s)

