from __future__ import annotations

import logging
from pathlib import Path

from accloud_core.cache_store import CacheStore
from accloud_core.config import AppConfig
from accloud_core.models import Printer
from app_gui_qt.app import _make_refresh_printers_callback


class _FakeApi:
    def __init__(self) -> None:
        self.project_calls: list[tuple[str, int | None]] = []

    def list_printers(self) -> list[Printer]:
        return [
            Printer(
                printer_id="42859",
                name="Anycubic Photon M3 Plus",
                online=True,
                state="online",
                is_printing=0,
            ),
            Printer(
                printer_id="42860",
                name="Anycubic Photon Mono 4",
                online=False,
                state="offline",
                is_printing=0,
            ),
        ]

    def list_projects(
        self,
        *,
        printer_id: str,
        print_status: int | None = 1,
        page: int = 1,
        limit: int = 1,
    ) -> list[dict[str, object]]:
        _ = (print_status, page, limit)
        self.project_calls.append((printer_id, print_status))
        if printer_id != "42859":
            return []
        return [
            {
                "taskid": 70001,
                "gcode_name": "fallback_name.pwmb",
                "progress": 23,
                "remain_time": 47,
                "print_time": 12,
                "settings": (
                    "{\"filename\":\"demo_job.pwmb\",\"curr_layer\":321,"
                    "\"total_layers\":1400,\"state\":\"printing\"}"
                ),
                "print_status": 1,
            }
        ]


class _FallbackProjectApi:
    def __init__(self) -> None:
        self.project_calls: list[tuple[str, int | None]] = []

    def list_printers(self) -> list[Printer]:
        return [
            Printer(
                printer_id="42859",
                name="Anycubic Photon M3 Plus",
                online=True,
                state="printing",
                is_printing=2,
                current_file_name="from-printer-endpoint.pwmb",
                progress_percent=21,
                remain_time_min=49,
                elapsed_time_min=11,
                current_layer=88,
                total_layers=512,
                task_id="72300",
                print_status=1,
            )
        ]

    def list_projects(
        self,
        *,
        printer_id: str,
        print_status: int | None = 1,
        page: int = 1,
        limit: int = 1,
    ) -> list[dict[str, object]]:
        _ = (page, limit)
        self.project_calls.append((printer_id, print_status))
        if print_status == 1:
            return []
        return [
            {
                "taskid": 72300,
                "settings": "{\"state\":\"printing\"}",
                "gcode_name": "fallback-from-projects.pwmb",
                "progress": 22,
                "remain_time": 48,
                "print_time": 12,
                "curr_layer": 89,
                "total_layers": 512,
                "print_status": 1,
            }
        ]


def test_refresh_printers_enriches_active_job_fields(tmp_path: Path) -> None:
    api = _FakeApi()
    config = AppConfig(
        session_path=tmp_path / "session.json",
        cache_dir=tmp_path / "cache",
        http_log_path=tmp_path / "http.log",
        fault_log_path=tmp_path / "fault.log",
    )
    cache_store = CacheStore(config.cache_dir)
    logger = logging.getLogger("tests.printers")

    refresh_cb = _make_refresh_printers_callback(
        api=api,  # type: ignore[arg-type]
        logger=logger,
        config=config,
        cache_store=cache_store,
    )
    printers, error_message = refresh_cb()

    assert error_message is None
    assert len(printers) == 2
    assert api.project_calls == [("42859", 1)]

    active = printers[0]
    assert active.current_file_name == "demo_job.pwmb"
    assert active.progress_percent == 23
    assert active.remain_time_min == 47
    assert active.elapsed_time_min == 12
    assert active.current_layer == 321
    assert active.total_layers == 1400
    assert active.task_id == "70001"
    assert active.print_status == 1
    assert active.state == "printing"
    assert active.is_printing == 1

    offline = printers[1]
    assert offline.current_file_name is None
    assert offline.progress_percent is None


def test_refresh_printers_falls_back_to_unfiltered_projects_when_active_filter_is_empty(tmp_path: Path) -> None:
    api = _FallbackProjectApi()
    config = AppConfig(
        session_path=tmp_path / "session.json",
        cache_dir=tmp_path / "cache",
        http_log_path=tmp_path / "http.log",
        fault_log_path=tmp_path / "fault.log",
    )
    cache_store = CacheStore(config.cache_dir)
    logger = logging.getLogger("tests.printers.fallback")

    refresh_cb = _make_refresh_printers_callback(
        api=api,  # type: ignore[arg-type]
        logger=logger,
        config=config,
        cache_store=cache_store,
    )
    printers, error_message = refresh_cb()

    assert error_message is None
    assert len(printers) == 1
    assert api.project_calls == [("42859", 1), ("42859", None)]
    active = printers[0]
    assert active.current_file_name == "fallback-from-projects.pwmb"
    assert active.progress_percent == 22
    assert active.remain_time_min == 48
    assert active.elapsed_time_min == 12
    assert active.current_layer == 89
    assert active.total_layers == 512
    assert active.task_id == "72300"
    assert active.print_status == 1
