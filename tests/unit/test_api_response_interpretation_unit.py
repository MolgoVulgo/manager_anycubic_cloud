from __future__ import annotations

from pathlib import Path

import httpx

from accloud.api import AnycubicCloudApi
from accloud.client import CloudHttpClient
from accloud.config import AppConfig, RetryConfig
from accloud.models import SessionData


def _build_client(*, handler, tmp_path: Path) -> CloudHttpClient:
    config = AppConfig(
        base_url="https://cloud-universe.anycubic.com",
        session_path=tmp_path / "session.json",
        http_log_path=tmp_path / "http.log",
        fault_log_path=tmp_path / "fault.log",
        retry=RetryConfig(max_attempts=1, base_delay_s=0.0, max_delay_s=0.0),
    )
    client = CloudHttpClient(config=config, session_data=SessionData(tokens={"access_token": "DEMO-TOKEN"}))
    client._client.close()  # noqa: SLF001
    client._client = httpx.Client(  # noqa: SLF001
        base_url=config.base_url,
        timeout=config.timeout_s,
        headers={"User-Agent": config.user_agent},
        follow_redirects=True,
        transport=httpx.MockTransport(handler),
    )
    client.update_session(SessionData(tokens={"access_token": "DEMO-TOKEN"}))
    return client


def test_get_quota_accepts_human_readable_values(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/p/workbench/api/work/index/getUserStore":
            return httpx.Response(
                200,
                json={"code": 1, "data": {"used": "117.7 MB", "total": "2.0 GB"}},
            )
        return httpx.Response(404, json={"error": "not found"})

    client = _build_client(handler=handler, tmp_path=tmp_path)
    api = AnycubicCloudApi(client)
    try:
        quota = api.get_quota()
    finally:
        client.close()

    assert quota.total_bytes == 2 * 1024 * 1024 * 1024
    assert quota.used_bytes == int(117.7 * 1024 * 1024)
    assert quota.free_bytes == quota.total_bytes - quota.used_bytes
    assert quota.used_percent > 5.0


def test_list_files_maps_catalog_fields_and_status(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/p/workbench/api/work/index/files":
            return httpx.Response(
                200,
                json={
                    "code": 1,
                    "data": [
                        {
                            "id": 30553490,
                            "old_filename": "model.pwmb",
                            "filename": "renamed.pwmb",
                            "size": 44851383,
                            "status": 1,
                            "gcode_id": 44306216,
                            "url": "https://cdn.example.com/file.pwmb",
                            "thumbnail": "https://cdn.example.com/thumb.jpg",
                            "region": "us-east-2",
                            "bucket": "workbentch",
                            "path": "file/30553490/model.pwmb",
                            "updateTime": 1771717986822,
                        }
                    ],
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    client = _build_client(handler=handler, tmp_path=tmp_path)
    api = AnycubicCloudApi(client)
    try:
        files = api.list_files(page=1, page_size=20)
    finally:
        client.close()

    assert len(files) == 1
    item = files[0]
    assert item.file_id == "30553490"
    assert item.name == "model.pwmb"
    assert item.size_bytes == 44851383
    assert item.status == "ready"
    assert item.status_code == 1
    assert item.gcode_id == "44306216"
    assert item.thumbnail_url == "https://cdn.example.com/thumb.jpg"
    assert item.download_url == "https://cdn.example.com/file.pwmb"
    assert item.region == "us-east-2"
    assert item.bucket == "workbentch"
    assert item.object_path == "file/30553490/model.pwmb"
    assert item.updated_at is not None and item.updated_at.endswith("UTC")
