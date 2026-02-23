from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from accloud_core.models import SessionData
from accloud_core.session_store import (
    extract_tokens_from_har,
    load_session,
    merge_sessions,
    save_session,
)


def _write_har(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_extract_tokens_from_har_filters_host_and_headers(tmp_path: Path) -> None:
    har_path = tmp_path / "session.har"
    _write_har(
        har_path,
        {
            "log": {
                "entries": [
                    {
                        "request": {
                            "url": "https://api.anycubic.example/files",
                            "headers": [
                                {"name": "Authorization", "value": "Bearer TOKEN-1"},
                                {"name": "X-Access-Token", "value": "X-TOKEN-2"},
                                {"name": "User-Agent", "value": "UA"},
                            ],
                        }
                    },
                    {
                        "request": {
                            "url": "https://unrelated.example.com/files",
                            "headers": [
                                {"name": "Authorization", "value": "Bearer SHOULD-NOT-BE-USED"},
                            ],
                        }
                    },
                ]
            }
        },
    )

    session = extract_tokens_from_har(har_path, host_contains="anycubic")

    assert session.tokens["Authorization"] == "Bearer TOKEN-1"
    assert session.tokens["access_token"] == "TOKEN-1"
    assert session.tokens["id_token"] == "TOKEN-1"
    assert session.tokens["token"] == "X-TOKEN-2"


def test_extract_tokens_from_har_prefers_auth_response_json(tmp_path: Path) -> None:
    har_path = tmp_path / "auth_response.har"
    _write_har(
        har_path,
        {
            "log": {
                "entries": [
                    {
                        "request": {
                            "method": "POST",
                            "url": "https://api.anycubic.example/auth/login",
                            "headers": [],
                        },
                        "response": {
                            "status": 200,
                            "content": {
                                "text": json.dumps(
                                    {
                                        "data": {
                                            "access_token": "ACCESS-12345",
                                            "refresh_token": "REFRESH-99999",
                                            "token_type": "Bearer",
                                            "expires_in": 3600,
                                        }
                                    }
                                )
                            },
                        },
                    }
                ]
            }
        },
    )

    session = extract_tokens_from_har(har_path)

    assert session.tokens["Authorization"] == "Bearer ACCESS-12345"
    assert session.tokens["access_token"] == "ACCESS-12345"
    assert session.tokens["id_token"] == "ACCESS-12345"


def test_extract_tokens_from_har_supports_base64_response_content(tmp_path: Path) -> None:
    payload = json.dumps({"access_token": "BASE64-ACCESS", "token_type": "Bearer"}).encode("utf-8")
    encoded = base64.b64encode(payload).decode("ascii")
    har_path = tmp_path / "base64_response.har"
    _write_har(
        har_path,
        {
            "log": {
                "entries": [
                    {
                        "request": {
                            "method": "POST",
                            "url": "https://api.anycubic.example/token",
                            "headers": [],
                        },
                        "response": {
                            "status": 200,
                            "content": {
                                "encoding": "base64",
                                "text": encoded,
                            },
                        },
                    }
                ]
            }
        },
    )

    session = extract_tokens_from_har(har_path)
    assert session.tokens["Authorization"] == "Bearer BASE64-ACCESS"
    assert session.tokens["access_token"] == "BASE64-ACCESS"


def test_save_load_and_merge_session_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "session.json"
    base = SessionData(tokens={"access_token": "OLD"})
    incoming = SessionData(
        tokens={"access_token": "NEW", "token": "ABC"},
    )

    merged = merge_sessions(base, incoming)
    save_session(target, merged)
    loaded = load_session(target)

    assert loaded.tokens["access_token"] == "NEW"
    assert loaded.tokens["id_token"] == "NEW"
    assert loaded.tokens["token"] == "ABC"
    assert loaded.tokens["Authorization"] == "Bearer NEW"

    raw = json.loads(target.read_text(encoding="utf-8"))
    assert set(raw.keys()) == {"last_update", "tokens"}
    assert set(raw["tokens"].keys()) == {"id_token", "token", "access_token"}

    mode = os.stat(target).st_mode & 0o777
    assert mode == 0o600


def test_load_session_from_canonical_shape_rebuilds_authorization(tmp_path: Path) -> None:
    target = tmp_path / "session.json"
    target.write_text(
        json.dumps(
            {
                "last_update": "22/02/2026",
                "tokens": {
                    "id_token": "ID-123",
                    "token": "TOK-456",
                    "access_token": "ACCESS-789",
                },
            }
        ),
        encoding="utf-8",
    )

    loaded = load_session(target)
    assert loaded.tokens["access_token"] == "ACCESS-789"
    assert loaded.tokens["id_token"] == "ID-123"
    assert loaded.tokens["token"] == "TOK-456"
    assert loaded.tokens["Authorization"] == "Bearer ACCESS-789"


def test_load_session_supports_legacy_headers_and_top_level_keys(tmp_path: Path) -> None:
    target = tmp_path / "session_legacy.json"
    target.write_text(
        json.dumps(
            {
                "headers": {"Authorization": "Bearer LEGACY-AUTH"},
                "access_token": "TOP-ACCESS",
                "id_token": "TOP-ID",
                "token": "TOP-TOKEN",
            }
        ),
        encoding="utf-8",
    )

    loaded = load_session(target)
    assert loaded.tokens["access_token"] == "TOP-ACCESS"
    assert loaded.tokens["id_token"] == "TOP-ID"
    assert loaded.tokens["token"] == "TOP-TOKEN"
    assert loaded.tokens["Authorization"] == "Bearer LEGACY-AUTH"
