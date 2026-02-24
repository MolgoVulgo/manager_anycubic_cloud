from __future__ import annotations

from collections.abc import Mapping
import hashlib
import math
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from typing import Any


_SENSITIVE_EXACT_KEYS = {
    "token",
    "access_token",
    "authorization",
    "cookie",
    "set-cookie",
    "secret",
    "signature",
    "nonce",
    "timestamp",
    "password",
    "email",
    "phone",
    "user_id",
    "refresh",
    "refresh_token",
    "authorization",
    "x-access-token",
    "x-auth-token",
    "xx-token",
    "xx-signature",
    "xx-nonce",
    "xx-timestamp",
}

_SENSITIVE_KEY_PARTS = (
    "token",
    "authorization",
    "cookie",
    "set-cookie",
    "secret",
    "signature",
    "nonce",
    "timestamp",
    "password",
    "email",
    "phone",
    "user_id",
    "refresh",
)


def redact_value(value: Any) -> str:
    _ = value
    return "[REDACTED]"


def redact_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in values.items():
        if is_sensitive_key(str(key)):
            redacted[key] = redact_value(value)
            continue
        redacted[key] = redact_json_like(value)
    return redacted


def redact_json_like(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, nested_value in value.items():
            if is_sensitive_key(str(key)):
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


def safe_url_for_log(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.query:
        return url
    safe_query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if is_sensitive_key(key):
            safe_query.append((key, "[REDACTED]"))
        else:
            safe_query.append((key, value))
    return urlunparse(parsed._replace(query=urlencode(safe_query)))


def is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower()
    if not normalized:
        return False
    if normalized in _SENSITIVE_EXACT_KEYS:
        return True
    return any(fragment in normalized for fragment in _SENSITIVE_KEY_PARTS)


def url_log_parts(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    query = parsed.query
    query_keys = sorted({key for key, _value in parse_qsl(query, keep_blank_values=True)})

    if parsed.scheme and parsed.netloc:
        url_base = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    else:
        url_base = str(url).split("?", 1)[0]

    payload: dict[str, Any] = {
        "url_base": url_base,
        "query_keys": query_keys,
    }
    if query:
        payload["url.query_hash"] = hashlib.sha256(query.encode("utf-8")).hexdigest()
    return payload


def format_bytes(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    units = ["KB", "MB", "GB", "TB", "PB"]
    value = float(num_bytes)
    unit_index = -1
    while value >= 1024.0 and unit_index < len(units) - 1:
        value /= 1024.0
        unit_index += 1
    return f"{value:.1f} {units[unit_index]}"


def pick_first(data: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return default
