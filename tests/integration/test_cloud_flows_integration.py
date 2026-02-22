from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

import httpx

from accloud.api import AnycubicCloudApi
from accloud.client import CloudHttpClient
from accloud.config import AppConfig, RetryConfig
from accloud.models import SessionData


def _build_client(
    *,
    handler,
    tmp_path: Path,
    retry: RetryConfig | None = None,
    session: SessionData | None = None,
) -> CloudHttpClient:
    config = AppConfig(
        base_url="https://cloud-universe.anycubic.com",
        session_path=tmp_path / "session.json",
        http_log_path=tmp_path / "http.log",
        fault_log_path=tmp_path / "fault.log",
        retry=retry or RetryConfig(max_attempts=3, base_delay_s=0.0, max_delay_s=0.0),
    )
    client = CloudHttpClient(config=config, session_data=session or SessionData())
    client._client.close()  # noqa: SLF001
    client._client = httpx.Client(  # noqa: SLF001
        base_url=config.base_url,
        timeout=config.timeout_s,
        headers={"User-Agent": config.user_agent},
        follow_redirects=True,
        transport=httpx.MockTransport(handler),
    )
    client.update_session(session or SessionData())
    return client


def test_cloud_quota_and_files_flow(tmp_path: Path) -> None:
    seen_auth: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_auth.append(request.headers.get("Authorization", ""))
        if request.url.path == "/p/p/workbench/api/work/index/getUserStore":
            return httpx.Response(200, json={"code": 1, "data": {"total_bytes": 1000, "used_bytes": 400, "free": 600}})
        if request.url.path == "/p/p/workbench/api/work/index/files":
            return httpx.Response(
                200,
                json={
                    "code": 1,
                    "data": [
                        {"id": "file-1", "name": "demo.pwmb", "size": 42, "status": "ready"},
                        {"id": "file-2", "name": "test.pwmb", "size": 84, "status": "printing"},
                    ],
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    session = SessionData(tokens={"access_token": "DEMO-TOKEN"})
    client = _build_client(handler=handler, tmp_path=tmp_path, session=session)
    api = AnycubicCloudApi(client)
    try:
        quota = api.get_quota()
        files = api.list_files(page=1, page_size=20)
    finally:
        client.close()

    assert quota.total_bytes == 1000
    assert quota.used_bytes == 400
    assert quota.free_bytes == 600
    assert len(files) == 2
    assert files[0].file_id == "file-1"
    assert files[0].name == "demo.pwmb"
    assert any(value == "Bearer DEMO-TOKEN" for value in seen_auth)


def test_cloud_download_signed_url_flow(tmp_path: Path) -> None:
    output = tmp_path / "downloaded.pwmb"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/p/workbench/api/work/index/getDowdLoadUrl":
            assert request.method == "POST"
            return httpx.Response(
                200,
                json={"code": 1, "data": {"signedUrl": "https://signed.anycubic.example/download/file-1"}},
            )
        if request.url.host == "signed.anycubic.example" and request.url.path == "/download/file-1":
            return httpx.Response(200, content=b"PWMB-BINARY")
        return httpx.Response(404, json={"error": "not found"})

    client = _build_client(handler=handler, tmp_path=tmp_path)
    api = AnycubicCloudApi(client)
    try:
        api.download_file("file-1", str(output))
    finally:
        client.close()

    assert output.exists()
    assert output.read_bytes() == b"PWMB-BINARY"


def test_cloud_client_retries_transport_errors(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ConnectError("network down", request=request)
        if request.url.path == "/p/p/workbench/api/work/index/getUserStore":
            return httpx.Response(200, json={"code": 1, "data": {"total_bytes": 10, "used_bytes": 1, "free": 9}})
        return httpx.Response(404, json={"error": "not found"})

    retry = RetryConfig(max_attempts=2, base_delay_s=0.0, max_delay_s=0.0)
    client = _build_client(handler=handler, tmp_path=tmp_path, retry=retry)
    api = AnycubicCloudApi(client)
    try:
        quota = api.get_quota()
    finally:
        client.close()

    assert calls["count"] == 2
    assert quota.total_bytes == 10


def test_validate_session_uses_workbench_endpoint_and_code_contract(tmp_path: Path) -> None:
    seen_paths: list[str] = []
    seen_headers: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        seen_headers.append(request.headers)
        if request.url.path == "/p/p/workbench/api/work/index/getUserStore":
            return httpx.Response(200, json={"code": 1, "data": {"storeId": "ok"}})
        return httpx.Response(404, json={"error": "not found"})

    session = SessionData(tokens={"access_token": "DEMO-TOKEN", "token": "SESSION-TOKEN"})
    client = _build_client(handler=handler, tmp_path=tmp_path, session=session)
    api = AnycubicCloudApi(client)
    try:
        payload = api.validate_session()
    finally:
        client.close()

    assert payload["storeId"] == "ok"
    assert "/p/p/workbench/api/work/index/getUserStore" in seen_paths
    assert any(headers.get("xx-token") == "SESSION-TOKEN" for headers in seen_headers)
    assert all(headers.get("xx-device-type") == "web" for headers in seen_headers)
    assert all(headers.get("xx-version") for headers in seen_headers)
    assert all(headers.get("xx-nonce") for headers in seen_headers)
    assert all(headers.get("xx-timestamp") for headers in seen_headers)
    assert all(headers.get("xx-signature") for headers in seen_headers)


def test_workbench_public_signature_matches_legacy_formula(tmp_path: Path, monkeypatch) -> None:
    fixed_timestamp_ms = 1771717986822
    fixed_timestamp_s = fixed_timestamp_ms / 1000.0
    fixed_nonce = UUID("77f8ca60-0f80-11f1-a14c-e351ea8cc889")
    app_id = "f9b3528877c94d5c9c5af32245db46ef"
    app_secret = "0cf75926606049a3937f56b0373b99fb"
    app_version = "1.0.0"

    monkeypatch.setattr("accloud.client.time.time", lambda: fixed_timestamp_s)
    monkeypatch.setattr("accloud.client.uuid1", lambda: fixed_nonce)

    seen_headers: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers)
        if request.url.path == "/p/p/workbench/api/work/index/getUserStore":
            return httpx.Response(200, json={"code": 1, "data": {"storeId": "ok"}})
        return httpx.Response(404, json={"error": "not found"})

    session = SessionData(tokens={"token": "SESSION-TOKEN"})
    client = _build_client(handler=handler, tmp_path=tmp_path, session=session)
    api = AnycubicCloudApi(client)
    try:
        _ = api.validate_session()
    finally:
        client.close()

    assert seen_headers
    headers = seen_headers[0]
    assert headers.get("xx-token") == "SESSION-TOKEN"
    assert headers.get("xx-nonce") == str(fixed_nonce)
    assert headers.get("xx-timestamp") == str(fixed_timestamp_ms)
    assert headers.get("xx-version") == app_version

    raw = f"{app_id}{fixed_timestamp_ms}{app_version}{app_secret}{fixed_nonce}{app_id}"
    expected_signature = hashlib.md5(raw.encode("utf-8"), usedforsecurity=False).hexdigest()
    assert headers.get("xx-signature") == expected_signature
