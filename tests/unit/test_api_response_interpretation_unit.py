from __future__ import annotations

from pathlib import Path

import httpx

from accloud_core.api import AnycubicCloudApi
from accloud_core.client import CloudHttpClient
from accloud_core.config import AppConfig, RetryConfig
from accloud_core.models import SessionData


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
                            "layers": 287,
                            "estimate": 3114,
                            "layer_height": 0.05,
                            "material_name": "Resin",
                            "supplies_usage": 68.18040466308594,
                            "size_x": 0,
                            "size_y": 0,
                            "size_z": 23.5,
                            "file_extension": "pwmb",
                            "printer_names": ["Anycubic Photon M3 Plus"],
                            "md5": "1d3aff6dfda0ffd0438eceda7eb817a0",
                            "slice_param": {
                                "layers": 470,
                                "estimate": 4698,
                                "zthick": 0.05000000074505806,
                                "machine_name": "Anycubic Photon M3 Plus",
                                "material_name": "Basic",
                                "supplies_usage": 68.18040466308594,
                                "bott_layers": 6,
                                "exposure_time": 1.5,
                                "off_time": 0.5,
                                "size_x": 0,
                                "size_y": 0,
                                "size_z": 23.5,
                            },
                            "url": "https://cdn.example.com/file.pwmb",
                            "thumbnail": "https://cdn.example.com/thumb.jpg",
                            "region": "us-east-2",
                            "bucket": "workbentch",
                            "path": "file/30553490/model.pwmb",
                            "createTime": 1771717986822,
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
    assert item.layer_count == 287
    assert item.print_time_s == 3114
    assert item.layer_thickness_mm == 0.05
    assert item.material_name == "Resin"
    assert item.resin_usage_ml == 68.18040466308594
    assert item.size_x_mm == 0.0
    assert item.size_y_mm == 0.0
    assert item.size_z_mm == 23.5
    assert item.file_extension == "pwmb"
    assert item.bottom_layers == 6
    assert item.exposure_time_s == 1.5
    assert item.off_time_s == 0.5
    assert item.printer_names == ["Anycubic Photon M3 Plus"]
    assert item.md5 == "1d3aff6dfda0ffd0438eceda7eb817a0"
    assert item.upload_time is not None and item.upload_time.endswith("UTC")
    assert item.thumbnail_url == "https://cdn.example.com/thumb.jpg"
    assert item.download_url == "https://cdn.example.com/file.pwmb"
    assert item.region == "us-east-2"
    assert item.bucket == "workbentch"
    assert item.object_path == "file/30553490/model.pwmb"
    assert item.updated_at is not None and item.updated_at.endswith("UTC")


def test_list_printers_maps_cloud_fields_and_online_state(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/p/workbench/api/work/printer/getPrinters":
            return httpx.Response(
                200,
                json={
                    "code": 1,
                    "data": [
                        {
                            "id": 42859,
                            "name": "Anycubic Photon M3 Plus",
                            "model": "Anycubic Photon M3 Plus",
                            "type": "LCD",
                            "description": "A7F6-B0FF-F706-3D49",
                            "device_status": 1,
                            "is_printing": 1,
                            "reason": "busy",
                            "last_update_time": 1770662731054,
                            "material_type": "Resin",
                            "material_used": "23127.1ml",
                            "print_totaltime": "642h53m",
                            "base": {"print_count": 58},
                            "machine_type": 107,
                            "key": "device-key",
                            "img": "https://cdn.example.com/printer.png",
                            "status": 1,
                            "print_status": 1,
                            "gcode_name": "raven_skull_19_v3.pwmb",
                            "progress": 14,
                            "remain_time": 218,
                            "print_time": 38,
                            "taskid": 72244987,
                            "settings": "{\"curr_layer\":155,\"total_layers\":1073}",
                        },
                        {
                            "id": 42860,
                            "name": "Anycubic Photon Mono 4",
                            "model": "Anycubic Photon Mono 4",
                            "type": "LCD",
                            "device_status": 2,
                            "is_printing": 0,
                            "reason": "offline",
                            "status": 1,
                        },
                    ],
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    client = _build_client(handler=handler, tmp_path=tmp_path)
    api = AnycubicCloudApi(client)
    try:
        printers = api.list_printers()
    finally:
        client.close()

    assert len(printers) == 2
    printer_online = printers[0]
    assert printer_online.printer_id == "42859"
    assert printer_online.online is True
    assert printer_online.state == "printing"
    assert printer_online.printer_type == "LCD"
    assert printer_online.material_used == "23127.1ml"
    assert printer_online.print_count == 58
    assert printer_online.last_update_time is not None and printer_online.last_update_time.endswith("UTC")
    assert printer_online.current_file_name == "raven_skull_19_v3.pwmb"
    assert printer_online.progress_percent == 14
    assert printer_online.remain_time_min == 218
    assert printer_online.elapsed_time_min == 38
    assert printer_online.current_layer == 155
    assert printer_online.total_layers == 1073
    assert printer_online.task_id == "72244987"
    assert printer_online.print_status == 1

    printer_offline = printers[1]
    assert printer_offline.printer_id == "42860"
    assert printer_offline.online is False
    assert printer_offline.state == "offline"


def test_list_printers_uses_nested_project_fields_when_needed(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/p/workbench/api/work/printer/getPrinters":
            return httpx.Response(
                200,
                json={
                    "code": 1,
                    "data": [
                        {
                            "id": 42859,
                            "name": "Anycubic Photon M3 Plus",
                            "model": "Anycubic Photon M3 Plus",
                            "type": "LCD",
                            "device_status": 1,
                            "is_printing": 2,
                            "project": {
                                "name": "raven_skull_19_v3.pwmb",
                                "progress": 27,
                                "remain_time": 190,
                                "print_time": 44,
                                "curr_layer": 201,
                                "total_layers": 1073,
                                "task_id": 72244987,
                                "print_status": 1,
                            },
                        }
                    ],
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    client = _build_client(handler=handler, tmp_path=tmp_path)
    api = AnycubicCloudApi(client)
    try:
        printers = api.list_printers()
    finally:
        client.close()

    assert len(printers) == 1
    printer = printers[0]
    assert printer.online is True
    assert printer.state == "printing"
    assert printer.current_file_name == "raven_skull_19_v3.pwmb"
    assert printer.progress_percent == 27
    assert printer.remain_time_min == 190
    assert printer.elapsed_time_min == 44
    assert printer.current_layer == 201
    assert printer.total_layers == 1073
    assert printer.task_id == "72244987"
    assert printer.print_status == 1
