from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

import httpx
import pytest

from accloud_core.api import AnycubicCloudApi
from accloud_core.client import CloudHttpClient
from accloud_core.config import AppConfig, RetryConfig
from accloud_core.errors import CloudApiError
from accloud_core.models import SessionData


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


def test_cloud_download_signed_url_string_data_flow(tmp_path: Path) -> None:
    output = tmp_path / "downloaded-string-data.pwmb"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/p/workbench/api/work/index/getDowdLoadUrl":
            assert request.method == "POST"
            return httpx.Response(
                200,
                json={"code": 1, "data": "https://signed.anycubic.example/download/file-2"},
            )
        if request.url.host == "signed.anycubic.example" and request.url.path == "/download/file-2":
            return httpx.Response(200, content=b"PWMB-BINARY-STRING-DATA")
        return httpx.Response(404, json={"error": "not found"})

    client = _build_client(handler=handler, tmp_path=tmp_path)
    api = AnycubicCloudApi(client)
    try:
        api.download_file("file-2", str(output))
    finally:
        client.close()

    assert output.exists()
    assert output.read_bytes() == b"PWMB-BINARY-STRING-DATA"


def test_cloud_download_signed_url_get_has_no_cloud_auth_headers(tmp_path: Path) -> None:
    output = tmp_path / "downloaded-no-auth-header.pwmb"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/p/workbench/api/work/index/getDowdLoadUrl":
            assert request.method == "POST"
            assert request.headers.get("Authorization") == "Bearer DEMO-TOKEN"
            return httpx.Response(
                200,
                json={"code": 1, "data": "https://signed.anycubic.example/download/file-3"},
            )
        if request.url.host == "signed.anycubic.example" and request.url.path == "/download/file-3":
            if request.headers.get("Authorization"):
                return httpx.Response(400, json={"error": "auth header must not be present on presigned URL"})
            return httpx.Response(200, content=b"PWMB-NO-AUTH-HEADER")
        return httpx.Response(404, json={"error": "not found"})

    session = SessionData(tokens={"access_token": "DEMO-TOKEN"})
    client = _build_client(handler=handler, tmp_path=tmp_path, session=session)
    api = AnycubicCloudApi(client)
    try:
        api.download_file("file-3", str(output))
    finally:
        client.close()

    assert output.exists()
    assert output.read_bytes() == b"PWMB-NO-AUTH-HEADER"


def test_cloud_download_prefers_numeric_id_payload_for_numeric_file_id(tmp_path: Path) -> None:
    output = tmp_path / "downloaded-numeric-id.pwmb"
    seen_download_payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/p/workbench/api/work/index/getDowdLoadUrl":
            assert request.method == "POST"
            payload = json.loads(request.content.decode("utf-8"))
            assert isinstance(payload, dict)
            seen_download_payloads.append(payload)
            if isinstance(payload.get("id"), int):
                return httpx.Response(
                    200,
                    json={"code": 1, "data": "https://signed.anycubic.example/download/file-4"},
                )
            return httpx.Response(200, json={"code": 1, "data": ""})
        if request.url.host == "signed.anycubic.example" and request.url.path == "/download/file-4":
            return httpx.Response(200, content=b"PWMB-NUMERIC-ID")
        return httpx.Response(404, json={"error": "not found"})

    client = _build_client(handler=handler, tmp_path=tmp_path)
    api = AnycubicCloudApi(client)
    try:
        api.download_file("53095239", str(output))
    finally:
        client.close()

    assert seen_download_payloads
    assert isinstance(seen_download_payloads[0].get("id"), int)
    assert output.exists()
    assert output.read_bytes() == b"PWMB-NUMERIC-ID"


def test_cloud_list_projects_for_printer_flow(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/p/workbench/api/work/project/getProjects":
            assert request.method == "GET"
            params = dict(request.url.params)
            assert params.get("printer_id") == "42859"
            assert params.get("print_status") == "1"
            assert params.get("page") == "1"
            assert params.get("limit") == "1"
            return httpx.Response(
                200,
                json={
                    "code": 1,
                    "data": [
                        {
                            "taskid": 72244987,
                            "gcode_name": "raven_skull_19_v3.pwmb",
                            "progress": 14,
                            "remain_time": 218,
                            "print_time": 38,
                            "settings": "{\"curr_layer\":155,\"total_layers\":1073}",
                        }
                    ],
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    client = _build_client(handler=handler, tmp_path=tmp_path)
    api = AnycubicCloudApi(client)
    try:
        projects = api.list_projects(printer_id="42859", print_status=1, page=1, limit=1)
    finally:
        client.close()

    assert len(projects) == 1
    assert str(projects[0]["taskid"]) == "72244987"
    assert str(projects[0]["gcode_name"]) == "raven_skull_19_v3.pwmb"


def test_cloud_upload_signed_url_put_has_no_cloud_auth_headers(tmp_path: Path) -> None:
    source = tmp_path / "upload.pwmb"
    source.write_bytes(b"PWMB-UPLOAD-BINARY")

    seen_put_payload: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/p/workbench/api/v2/cloud_storage/lockStorageSpace":
            assert request.method == "POST"
            assert request.headers.get("Authorization") == "Bearer DEMO-TOKEN"
            return httpx.Response(
                200,
                json={"code": 1, "data": {"id": 12345, "preSignUrl": "https://signed.anycubic.example/upload/file-5"}},
            )
        if request.url.host == "signed.anycubic.example" and request.url.path == "/upload/file-5":
            assert request.method == "PUT"
            assert request.headers.get("Authorization") in {None, ""}
            seen_put_payload.append(request.content)
            return httpx.Response(200, content=b"")
        if request.url.path == "/p/p/workbench/api/v2/profile/newUploadFile":
            assert request.method == "POST"
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["user_lock_space_id"] == 12345
            return httpx.Response(200, json={"code": 1, "data": {"id": 987654}})
        if request.url.path == "/p/p/workbench/api/v2/cloud_storage/unlockStorageSpace":
            assert request.method == "POST"
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["id"] == 12345
            return httpx.Response(200, json={"code": 1, "data": True})
        return httpx.Response(404, json={"error": "not found"})

    session = SessionData(tokens={"access_token": "DEMO-TOKEN"})
    client = _build_client(handler=handler, tmp_path=tmp_path, session=session)
    api = AnycubicCloudApi(client)
    try:
        file_id = api.upload_file(str(source))
    finally:
        client.close()

    assert file_id == "987654"
    assert seen_put_payload == [b"PWMB-UPLOAD-BINARY"]


def test_cloud_delete_file_prefers_numeric_id_payload(tmp_path: Path) -> None:
    seen_payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/p/workbench/api/work/index/delFiles":
            payload = json.loads(request.content.decode("utf-8"))
            assert isinstance(payload, dict)
            seen_payloads.append(payload)
            return httpx.Response(200, json={"code": 1, "data": True})
        return httpx.Response(404, json={"error": "not found"})

    client = _build_client(handler=handler, tmp_path=tmp_path)
    api = AnycubicCloudApi(client)
    try:
        api.delete_file("53095239")
    finally:
        client.close()

    assert seen_payloads
    id_arr = seen_payloads[0].get("idArr")
    assert isinstance(id_arr, list) and id_arr
    assert isinstance(id_arr[0], int)


def test_cloud_delete_file_falls_back_to_string_payload_and_succeeds(tmp_path: Path) -> None:
    seen_payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path != "/p/p/workbench/api/work/index/delFiles":
            return httpx.Response(404, json={"error": "not found"})
        payload = json.loads(request.content.decode("utf-8"))
        assert isinstance(payload, dict)
        seen_payloads.append(payload)
        id_arr = payload.get("idArr")
        if isinstance(id_arr, list) and id_arr and isinstance(id_arr[0], int):
            return httpx.Response(200, json={"code": 0, "msg": "numeric payload rejected"})
        return httpx.Response(200, json={"code": 1, "data": True})

    client = _build_client(handler=handler, tmp_path=tmp_path)
    api = AnycubicCloudApi(client)
    try:
        api.delete_file("53095239")
    finally:
        client.close()

    assert len(seen_payloads) == 2
    assert isinstance(seen_payloads[0]["idArr"][0], int)
    assert isinstance(seen_payloads[1]["idArr"][0], str)


def test_cloud_delete_file_surfaces_business_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/p/workbench/api/work/index/delFiles":
            return httpx.Response(200, json={"code": 0, "msg": "Delete rejected"})
        return httpx.Response(404, json={"error": "not found"})

    client = _build_client(handler=handler, tmp_path=tmp_path)
    api = AnycubicCloudApi(client)
    try:
        with pytest.raises(CloudApiError) as exc_info:
            api.delete_file("53095239")
    finally:
        client.close()

    assert "rejected" in str(exc_info.value).lower()


def test_cloud_print_order_uses_legacy_form_payload(tmp_path: Path) -> None:
    seen_calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/p/workbench/api/work/operation/sendOrder":
            seen_calls["count"] += 1
            assert request.method == "POST"
            content_type = request.headers.get("content-type", "")
            assert content_type.startswith("application/x-www-form-urlencoded")
            body = request.content.decode("utf-8")
            assert "printer_id=42859" in body
            assert "project_id=0" in body
            assert "order_id=1" in body
            assert "is_delete_file=0" in body
            assert "file_id" in body
            return httpx.Response(200, json={"code": 1, "data": {"taskid": 70291599}})
        return httpx.Response(404, json={"error": "not found"})

    client = _build_client(handler=handler, tmp_path=tmp_path)
    api = AnycubicCloudApi(client)
    try:
        api.send_print_order("30553490", "42859")
    finally:
        client.close()

    assert seen_calls["count"] == 1


def test_cloud_print_order_falls_back_when_legacy_payload_is_rejected(tmp_path: Path) -> None:
    seen_calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path != "/p/p/workbench/api/work/operation/sendOrder":
            return httpx.Response(404, json={"error": "not found"})

        content_type = request.headers.get("content-type", "")
        if content_type.startswith("application/x-www-form-urlencoded"):
            seen_calls.append("legacy-form")
            return httpx.Response(200, json={"code": 0, "msg": "legacy rejected"})

        payload = json.loads(request.content.decode("utf-8"))
        if "project_id" in payload and "order_id" in payload:
            seen_calls.append("legacy-json")
            return httpx.Response(200, json={"code": 0, "msg": "json legacy rejected"})

        seen_calls.append("minimal-json")
        assert payload["file_id"] == "30553490"
        assert payload["printer_id"] == "42859"
        return httpx.Response(200, json={"code": 1, "data": {"taskid": 70291991}})

    client = _build_client(handler=handler, tmp_path=tmp_path)
    api = AnycubicCloudApi(client)
    try:
        api.send_print_order("30553490", "42859")
    finally:
        client.close()

    assert seen_calls == ["legacy-form", "legacy-json", "minimal-json"]


def test_cloud_print_order_surfaces_business_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/p/workbench/api/work/operation/sendOrder":
            return httpx.Response(200, json={"code": 0, "msg": "Printer offline"})
        return httpx.Response(404, json={"error": "not found"})

    client = _build_client(handler=handler, tmp_path=tmp_path)
    api = AnycubicCloudApi(client)
    try:
        with pytest.raises(CloudApiError) as exc_info:
            api.send_print_order("30553490", "42859")
    finally:
        client.close()

    assert "offline" in str(exc_info.value).lower()


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

    monkeypatch.setattr("accloud_core.client.time.time", lambda: fixed_timestamp_s)
    monkeypatch.setattr("accloud_core.client.uuid1", lambda: fixed_nonce)

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


def test_auth_recovery_relogin_on_401_replays_request(tmp_path: Path) -> None:
    state = {"quota_calls": 0, "login_calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/p/workbench/api/work/index/getUserStore":
            state["quota_calls"] += 1
            if state["quota_calls"] == 1:
                return httpx.Response(401, json={"code": 0, "msg": "invalid token"})
            return httpx.Response(200, json={"code": 1, "data": {"total_bytes": 100, "used_bytes": 10, "free": 90}})
        if request.url.path == "/p/p/workbench/api/v3/public/loginWithAccessToken":
            state["login_calls"] += 1
            return httpx.Response(
                200,
                json={
                    "code": 1,
                    "data": {
                        "token": "RECOVERED-SESSION",
                        "access_token": "RECOVERED-ACCESS",
                        "id_token": "RECOVERED-ID",
                    },
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    session = SessionData(tokens={"access_token": "EXPIRED-ACCESS", "id_token": "VALID-ID", "token": "EXPIRED-SESSION"})
    client = _build_client(handler=handler, tmp_path=tmp_path, session=session)
    api = AnycubicCloudApi(client)
    try:
        quota = api.get_quota()
    finally:
        client.close()

    assert quota.total_bytes == 100
    assert state["login_calls"] == 1
    assert state["quota_calls"] == 2
    assert client.session_data.tokens.get("token") == "RECOVERED-SESSION"
    assert client.session_data.tokens.get("access_token") == "RECOVERED-ACCESS"
    assert client.session_data.tokens.get("Authorization") == "Bearer RECOVERED-ACCESS"


def test_auth_recovery_failure_surfaces_401(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/p/workbench/api/work/index/getUserStore":
            return httpx.Response(401, json={"code": 0, "msg": "invalid token"})
        if request.url.path == "/p/p/workbench/api/v3/public/loginWithAccessToken":
            return httpx.Response(200, json={"code": 0, "msg": "login failed"})
        return httpx.Response(404, json={"error": "not found"})

    session = SessionData(tokens={"access_token": "EXPIRED-ACCESS", "id_token": "EXPIRED-ID", "token": "EXPIRED-SESSION"})
    client = _build_client(handler=handler, tmp_path=tmp_path, session=session)
    api = AnycubicCloudApi(client)
    try:
        with pytest.raises(CloudApiError) as exc_info:
            _ = api.get_quota()
    finally:
        client.close()

    assert exc_info.value.status_code == 401
