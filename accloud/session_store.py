from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from accloud.models import SessionData


def load_session(path: Path) -> SessionData:
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    return SessionData(
        cookies=_as_str_map(raw.get("cookies")),
        headers=_as_str_map(raw.get("headers")),
        tokens=_as_str_map(raw.get("tokens")),
        metadata=_as_dict(raw.get("metadata")),
    )


def save_session(path: Path, session: SessionData) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cookies": session.cookies,
        "headers": session.headers,
        "tokens": session.tokens,
        "metadata": session.metadata,
    }

    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)


def extract_session_from_har(har_path: Path, host_contains: str | None = "anycubic") -> SessionData:
    with har_path.open("r", encoding="utf-8") as handle:
        har = json.load(handle)

    cookies: dict[str, str] = {}
    headers: dict[str, str] = {}
    tokens: dict[str, str] = {}
    metadata: dict[str, Any] = {"source": "har", "path": str(har_path)}

    entries = _as_list(_as_dict(har.get("log")).get("entries"))
    for entry in entries:
        request = _as_dict(_as_dict(entry).get("request"))
        url = str(request.get("url", "")).strip()
        if host_contains and host_contains.lower() not in url.lower():
            continue

        for cookie in _as_list(request.get("cookies")):
            cookie_map = _as_dict(cookie)
            name = str(cookie_map.get("name", "")).strip()
            value = str(cookie_map.get("value", "")).strip()
            if name and value:
                cookies[name] = value

        for header in _as_list(request.get("headers")):
            header_map = _as_dict(header)
            name = str(header_map.get("name", "")).strip()
            value = str(header_map.get("value", "")).strip()
            if not name or not value:
                continue
            lowered = name.lower()
            if lowered == "authorization":
                tokens[name] = value
            elif lowered.startswith("x-") and "token" in lowered:
                tokens[name] = value
            elif lowered in {"user-agent", "accept", "accept-language", "origin", "referer"}:
                headers[name] = value

    metadata["cookie_count"] = len(cookies)
    metadata["token_count"] = len(tokens)
    return SessionData(cookies=cookies, headers=headers, tokens=tokens, metadata=metadata)


def extract_tokens_from_har(har_path: Path, host_contains: str | None = "anycubic") -> SessionData:
    with har_path.open("r", encoding="utf-8") as handle:
        har = json.load(handle)

    tokens: dict[str, str] = {}
    metadata: dict[str, Any] = {"source": "har", "path": str(har_path)}

    entries = _as_list(_as_dict(har.get("log")).get("entries"))
    for entry in entries:
        request = _as_dict(_as_dict(entry).get("request"))
        url = str(request.get("url", "")).strip()
        if host_contains and host_contains.lower() not in url.lower():
            continue

        for header in _as_list(request.get("headers")):
            header_map = _as_dict(header)
            name = str(header_map.get("name", "")).strip()
            value = str(header_map.get("value", "")).strip()
            if not name or not value:
                continue
            lowered = name.lower()
            if lowered == "authorization":
                tokens[name] = value
            elif lowered.startswith("x-") and "token" in lowered:
                tokens[name] = value

    metadata["token_count"] = len(tokens)
    return SessionData(tokens=tokens, metadata=metadata)


def merge_sessions(base: SessionData, incoming: SessionData) -> SessionData:
    merged = SessionData(
        cookies={**base.cookies, **incoming.cookies},
        headers={**base.headers, **incoming.headers},
        tokens={**base.tokens, **incoming.tokens},
        metadata={**base.metadata, **incoming.metadata},
    )
    return merged


def _as_str_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, nested in value.items():
        result[str(key)] = str(nested)
    return result


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []
