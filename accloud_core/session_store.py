from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
import hashlib
import json
import logging
import os
from urllib.parse import parse_qsl, urlparse
from pathlib import Path
from typing import Any

from accloud_core.logging_contract import emit_event, get_op_id
from accloud_core.models import SessionData

LOGGER = logging.getLogger("accloud.session")


def load_session(path: Path) -> SessionData:
    op_id = get_op_id()
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except Exception as exc:
        emit_event(
            LOGGER,
            logging.ERROR,
            event="session.load_fail",
            msg="Session load failed",
            component="accloud.session",
            op_id=op_id,
            error={"type": type(exc).__name__, "message": str(exc)},
        )
        raise

    if not isinstance(raw, dict):
        return SessionData()

    raw_tokens = _as_str_map(raw.get("tokens"))

    # Backward compatibility with legacy session shape.
    legacy_headers = _as_str_map(raw.get("headers"))
    for key in ("Authorization", "X-Access-Token", "X-Auth-Token"):
        if key not in raw_tokens and key in legacy_headers:
            raw_tokens[key] = legacy_headers[key]

    for key in ("access_token", "id_token", "token", "Authorization"):
        value = str(raw.get(key, "")).strip()
        if value and key not in raw_tokens:
            raw_tokens[key] = value

    session = SessionData(tokens=_normalize_tokens_for_runtime(raw_tokens))
    emit_event(
        LOGGER,
        logging.INFO,
        event="session.load_ok",
        msg="Session loaded",
        component="accloud.session",
        op_id=op_id,
        data={"token_count": len(session.tokens)},
    )
    return session


def save_session(path: Path, session: SessionData) -> None:
    op_id = get_op_id()
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized_tokens = _normalize_tokens_for_storage(session.tokens)
    payload = {
        "last_update": datetime.now().strftime("%d/%m/%Y"),
        "tokens": normalized_tokens,
    }

    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
    emit_event(
        LOGGER,
        logging.INFO,
        event="session.save_ok",
        msg="Session saved",
        component="accloud.session",
        op_id=op_id,
        data={"token_count": len(normalized_tokens)},
    )


def extract_session_from_har(har_path: Path, host_contains: str | None = "anycubic") -> SessionData:
    return extract_tokens_from_har(har_path=har_path, host_contains=host_contains)


def extract_tokens_from_har(har_path: Path, host_contains: str | None = "anycubic") -> SessionData:
    LOGGER.debug("HAR extract start path=%s host_filter=%s", har_path, host_contains)
    with har_path.open("r", encoding="utf-8") as handle:
        har = json.load(handle)

    tokens: dict[str, str] = {}
    metadata: dict[str, Any] = {
        "source": "har",
        "path": str(har_path),
        "captured_at": datetime.now(UTC).isoformat(),
    }

    entries = _as_list(_as_dict(har.get("log")).get("entries"))
    LOGGER.debug("HAR extract loaded entries=%s", len(entries))

    response_candidates: list[dict[str, Any]] = []
    header_candidates: list[dict[str, Any]] = []
    fallback_cookie_tokens: dict[str, str] = {}
    filtered_out_count = 0

    for index, entry in enumerate(entries):
        request = _as_dict(_as_dict(entry).get("request"))
        response = _as_dict(_as_dict(entry).get("response"))
        url = str(request.get("url", "")).strip()
        if not url:
            continue
        if host_contains and host_contains.lower() not in url.lower():
            filtered_out_count += 1
            continue

        method = str(request.get("method", "")).upper()
        status = int(_as_dict(entry).get("response", {}).get("status", 0) or 0)
        is_auth_endpoint = _is_auth_url(url)
        query_tokens = _extract_token_like_from_query(url)
        if query_tokens:
            LOGGER.debug(
                "HAR extract query-token candidate idx=%s url=%s token_keys=%s",
                index,
                url,
                sorted(query_tokens.keys()),
            )
            fallback_cookie_tokens.update(query_tokens)

        request_headers = _extract_request_token_headers(request)
        if request_headers:
            LOGGER.debug(
                "HAR extract header-token candidate idx=%s status=%s method=%s auth=%s token_keys=%s",
                index,
                status,
                method,
                is_auth_endpoint,
                sorted(request_headers.keys()),
            )
            header_candidates.append(
                {
                    "index": index,
                    "status": status,
                    "url": url,
                    "is_auth_endpoint": is_auth_endpoint,
                    "method": method,
                    "headers": request_headers,
                }
            )

        response_payload = _extract_response_json_payload(response)
        if not response_payload:
            continue

        token_fields = _extract_token_fields(response_payload)
        if not token_fields:
            continue
        LOGGER.debug(
            "HAR extract response-token candidate idx=%s status=%s method=%s auth=%s url=%s token_fields=%s",
            index,
            status,
            method,
            is_auth_endpoint,
            url,
            sorted(token_fields.keys()),
        )
        response_candidates.append(
            {
                "index": index,
                "status": status,
                "url": url,
                "is_auth_endpoint": is_auth_endpoint,
                "method": method,
                "token_fields": token_fields,
            }
        )

    LOGGER.debug(
        "HAR extract candidates response=%s headers=%s query=%s filtered_out=%s",
        len(response_candidates),
        len(header_candidates),
        len(fallback_cookie_tokens),
        filtered_out_count,
    )

    selected = _select_best_response_candidate(response_candidates)
    if selected is not None:
        LOGGER.debug(
            "HAR extract selected response candidate idx=%s status=%s url=%s",
            selected.get("index"),
            selected.get("status"),
            selected.get("url"),
        )
        token_fields = _as_dict(selected.get("token_fields"))
        access_token = str(token_fields.get("access_token", "")).strip()
        id_token = str(token_fields.get("id_token", "")).strip()
        session_token = str(token_fields.get("token", "")).strip()
        token_type = str(token_fields.get("token_type", "Bearer")).strip() or "Bearer"
        if id_token:
            tokens["id_token"] = id_token
        if session_token:
            tokens["token"] = session_token
        if access_token:
            tokens["access_token"] = access_token
            tokens["Authorization"] = _normalize_bearer(access_token, token_type=token_type)
            metadata["auth_endpoint"] = selected.get("url")
            metadata["token_type"] = token_type
            expires_in = _as_positive_int(token_fields.get("expires_in"))
            if expires_in is not None:
                metadata["expires_in"] = expires_in
                captured_at = datetime.fromisoformat(metadata["captured_at"])
                metadata["expires_at"] = (captured_at + timedelta(seconds=expires_in)).isoformat()
            if "refresh_token" in token_fields:
                metadata["refresh_token"] = str(token_fields["refresh_token"])
            LOGGER.debug(
                "HAR extract token from response endpoint=%s auth=%s auth_fp=%s refresh=%s expires_in=%s",
                metadata.get("auth_endpoint"),
                _mask_secret(tokens.get("Authorization", "")),
                _token_fingerprint(tokens.get("Authorization", "")),
                _mask_secret(str(metadata.get("refresh_token", ""))),
                metadata.get("expires_in"),
            )

    if "Authorization" not in tokens:
        selected_headers = _select_best_header_candidate(header_candidates)
        if selected_headers is not None:
            LOGGER.debug(
                "HAR extract selected header candidate idx=%s status=%s url=%s",
                selected_headers.get("index"),
                selected_headers.get("status"),
                selected_headers.get("url"),
            )
            for name, value in _as_dict(selected_headers.get("headers")).items():
                tokens[str(name)] = str(value)
            metadata["auth_endpoint"] = selected_headers.get("url")
            LOGGER.debug(
                "HAR extract tokens from headers keys=%s auth=%s auth_fp=%s",
                sorted(tokens.keys()),
                _mask_secret(tokens.get("Authorization", "")),
                _token_fingerprint(tokens.get("Authorization", "")),
            )

    if not tokens and fallback_cookie_tokens:
        tokens.update(fallback_cookie_tokens)
        LOGGER.debug(
            "HAR extract fallback query tokens keys=%s auth=%s auth_fp=%s",
            sorted(tokens.keys()),
            _mask_secret(tokens.get("Authorization", "")),
            _token_fingerprint(tokens.get("Authorization", "")),
        )

    normalized_tokens = _normalize_tokens_for_runtime(tokens)
    metadata["token_count"] = len(normalized_tokens)
    if response_candidates:
        metadata["response_candidate_count"] = len(response_candidates)
    if header_candidates:
        metadata["header_candidate_count"] = len(header_candidates)
    LOGGER.debug(
        "HAR extract done token_count=%s token_keys=%s auth_endpoint=%s metadata_keys=%s",
        metadata["token_count"],
        sorted(normalized_tokens.keys()),
        metadata.get("auth_endpoint"),
        sorted(metadata.keys()),
    )
    return SessionData(tokens=normalized_tokens)


def merge_sessions(base: SessionData, incoming: SessionData) -> SessionData:
    merged_tokens = {**base.tokens, **incoming.tokens}
    return SessionData(tokens=_normalize_tokens_for_runtime(merged_tokens))


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


def _is_auth_url(url: str) -> bool:
    lowered = url.lower()
    markers = ("/login", "/auth", "/token", "/refresh")
    return any(marker in lowered for marker in markers)


def _extract_request_token_headers(request: dict[str, Any]) -> dict[str, str]:
    token_headers: dict[str, str] = {}
    for header in _as_list(request.get("headers")):
        header_map = _as_dict(header)
        name = str(header_map.get("name", "")).strip()
        value = str(header_map.get("value", "")).strip()
        if not name or not value:
            continue
        lowered = name.lower()
        if lowered == "authorization":
            token_headers["Authorization"] = value
        elif lowered in {"x-auth-token", "x-access-token"}:
            token_headers[name] = value
        elif "token" in lowered and lowered.startswith("x-"):
            token_headers[name] = value
    return token_headers


def _extract_response_json_payload(response: dict[str, Any]) -> dict[str, Any] | None:
    content = _as_dict(response.get("content"))
    text = content.get("text")
    if text is None:
        return None
    raw_text = str(text)
    if not raw_text.strip():
        return None

    encoding = str(content.get("encoding", "")).lower().strip()
    if encoding == "base64":
        try:
            decoded = base64.b64decode(raw_text, validate=False)
            raw_text = decoded.decode("utf-8", errors="replace")
        except Exception:
            return None

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _extract_token_fields(payload: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    flat = _collect_interesting_fields(payload)

    raw_auth = _first_non_empty(flat, "authorization", "auth", "bearer")
    access_token = _first_non_empty(flat, "access_token", "accesstoken")
    raw_token = _first_non_empty(flat, "token")
    id_token = _first_non_empty(flat, "id_token", "idtoken")
    refresh_token = _first_non_empty(flat, "refresh_token", "refreshtoken")
    token_type = _first_non_empty(flat, "token_type", "tokentype")
    expires_in = _first_non_empty(flat, "expires_in", "expiresin")

    if not access_token and raw_token:
        access_token = raw_token
    if raw_auth and not access_token and raw_auth.lower().startswith("bearer "):
        access_token = raw_auth[7:].strip()
    if access_token and access_token.lower().startswith("bearer "):
        access_token = access_token[7:].strip()

    if access_token:
        normalized["access_token"] = access_token.strip()
    if raw_token:
        normalized["token"] = raw_token.strip()
    if id_token:
        normalized["id_token"] = id_token.strip()
    if refresh_token:
        normalized["refresh_token"] = refresh_token.strip()
    if token_type:
        normalized["token_type"] = token_type.strip()
    if expires_in:
        expires_value = _as_positive_int(expires_in)
        if expires_value is not None:
            normalized["expires_in"] = expires_value
    if raw_auth:
        normalized["raw_auth_header"] = raw_auth.strip()
    return normalized


def _collect_interesting_fields(value: Any) -> dict[str, str]:
    collected: dict[str, str] = {}

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, nested in node.items():
                key_norm = str(key).strip().lower()
                if isinstance(nested, (str, int, float, bool)):
                    collected[key_norm] = str(nested).strip()
                _walk(nested)
        elif isinstance(node, list):
            for nested in node:
                _walk(nested)

    _walk(value)
    return collected


def _first_non_empty(mapping: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if value and value.strip():
            return value
    return None


def _normalize_bearer(access_token: str, *, token_type: str) -> str:
    if access_token.lower().startswith("bearer "):
        return access_token
    if token_type.lower() == "bearer":
        return f"Bearer {access_token}"
    return f"{token_type} {access_token}"


def _as_positive_int(value: Any) -> int | None:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _select_best_response_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None

    def _score(candidate: dict[str, Any]) -> tuple[int, int]:
        is_success = 1 if int(candidate.get("status", 0)) in {200, 201} else 0
        is_auth = 1 if bool(candidate.get("is_auth_endpoint")) else 0
        has_post = 1 if str(candidate.get("method", "")).upper() == "POST" else 0
        composite = (is_success * 100) + (is_auth * 10) + has_post
        return composite, int(candidate.get("index", 0))

    return max(candidates, key=_score)


def _select_best_header_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None

    def _score(candidate: dict[str, Any]) -> tuple[int, int]:
        is_success = 1 if int(candidate.get("status", 0)) in {200, 201} else 0
        is_auth = 1 if bool(candidate.get("is_auth_endpoint")) else 0
        has_post = 1 if str(candidate.get("method", "")).upper() == "POST" else 0
        composite = (is_success * 100) + (is_auth * 10) + has_post
        return composite, int(candidate.get("index", 0))

    return max(candidates, key=_score)


def _extract_token_like_from_query(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    if not parsed.query:
        return {}
    found: dict[str, str] = {}
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        lowered = key.lower()
        if lowered in {"access_token", "token", "authorization"} and value:
            found["Authorization"] = _normalize_bearer(value, token_type="Bearer")
    return found


def _mask_secret(value: str) -> str:
    secret = value.strip()
    if not secret:
        return "<empty>"
    if len(secret) <= 10:
        return "<masked>"
    return f"{secret[:6]}...{secret[-4:]}"


def _token_fingerprint(value: str) -> str:
    secret = value.strip()
    if not secret:
        return "<none>"
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]
    return f"sha256:{digest} len:{len(secret)}"


def _normalize_tokens_for_runtime(raw_tokens: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}

    access_token = _strip_bearer(raw_tokens.get("access_token", ""))
    if not access_token:
        access_token = _strip_bearer(raw_tokens.get("Authorization", ""))
    if not access_token:
        access_token = _strip_bearer(raw_tokens.get("token", ""))
    if access_token:
        normalized["access_token"] = access_token

    id_token = _strip_bearer(raw_tokens.get("id_token", ""))
    if not id_token and access_token:
        id_token = access_token
    if id_token:
        normalized["id_token"] = id_token

    session_token = _strip_bearer(raw_tokens.get("token", ""))
    if not session_token:
        session_token = _strip_bearer(raw_tokens.get("X-Access-Token", ""))
    if not session_token:
        session_token = _strip_bearer(raw_tokens.get("X-Auth-Token", ""))
    if session_token:
        normalized["token"] = session_token

    authorization = str(raw_tokens.get("Authorization", "")).strip()
    if not authorization and access_token:
        authorization = f"Bearer {access_token}"
    if authorization:
        normalized["Authorization"] = _normalize_bearer(_strip_bearer(authorization), token_type="Bearer")

    return normalized


def _normalize_tokens_for_storage(raw_tokens: dict[str, str]) -> dict[str, str]:
    runtime_tokens = _normalize_tokens_for_runtime(raw_tokens)
    stored: dict[str, str] = {}
    for key in ("id_token", "token", "access_token"):
        value = _strip_bearer(runtime_tokens.get(key, ""))
        if value:
            stored[key] = value
    return stored


def _strip_bearer(value: str) -> str:
    raw = str(value).strip()
    if not raw:
        return ""
    if raw.lower().startswith("bearer "):
        return raw[7:].strip()
    return raw
