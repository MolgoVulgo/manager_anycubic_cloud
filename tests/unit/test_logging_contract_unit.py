from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from accloud_core.logging_contract import (
    AppLogFilter,
    HttpLogFilter,
    JsonLineFormatter,
    Render3DLogFilter,
    build_queue_listener,
    emit_event,
    operation_context,
)


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        formatted = self.format(record)
        self.lines.append(formatted)


def test_jsonl_formatter_outputs_required_fields() -> None:
    logger = logging.getLogger("tests.logging.required")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = _CaptureHandler()
    handler.setFormatter(JsonLineFormatter())
    logger.handlers = [handler]

    with operation_context("12345678-1234-1234-1234-1234567890ab"):
        emit_event(
            logger,
            logging.INFO,
            event="ui.action",
            msg="Refresh requested",
            component="app.gui",
            data={"action": "refresh"},
        )

    assert handler.lines
    payload = json.loads(handler.lines[-1])
    assert payload["ts"]
    assert payload["level"] == "INFO"
    assert payload["component"] == "app.gui"
    assert payload["event"] == "ui.action"
    assert payload["msg"] == "Refresh requested"
    assert payload["op_id"] == "12345678-1234-1234-1234-1234567890ab"
    assert isinstance(payload["pid"], int)
    assert payload["thread"]


def test_jsonl_formatter_redacts_sensitive_data() -> None:
    logger = logging.getLogger("tests.logging.redaction")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = _CaptureHandler()
    handler.setFormatter(JsonLineFormatter())
    logger.handlers = [handler]

    emit_event(
        logger,
        logging.INFO,
        event="api.call_ok",
        msg="API call complete",
        component="accloud.api",
        data={
            "Authorization": "Bearer TOP_SECRET",
            "nested": {
                "token": "abc",
                "email": "demo@example.test",
            },
        },
    )

    assert handler.lines
    line = handler.lines[-1]
    payload = json.loads(line)
    assert payload["data"]["Authorization"] == "[REDACTED]"
    assert payload["data"]["nested"]["token"] == "[REDACTED]"
    assert payload["data"]["nested"]["email"] == "[REDACTED]"
    assert "Bearer TOP_SECRET" not in line
    assert "demo@example.test" not in line


def test_filters_keep_http_logs_exclusive() -> None:
    http_record = logging.makeLogRecord(
        {
            "name": "accloud.http",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "HTTP request",
            "accloud_component": "accloud.http",
            "accloud_event": "http.request",
        }
    )
    app_record = logging.makeLogRecord(
        {
            "name": "app_gui_qt.app",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "UI action",
            "accloud_component": "app.gui",
            "accloud_event": "ui.action",
        }
    )

    assert HttpLogFilter().filter(http_record) is True
    assert AppLogFilter().filter(http_record) is False
    assert HttpLogFilter().filter(app_record) is False
    assert AppLogFilter().filter(app_record) is True


def test_render3d_filter_keeps_3d_components_only() -> None:
    render_record = logging.makeLogRecord(
        {
            "name": "render3d_core.geometry_v2",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "Geometry built",
            "accloud_component": "render3d.build",
            "accloud_event": "build.stage_done",
        }
    )
    app_record = logging.makeLogRecord(
        {
            "name": "app_gui_qt.app",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "Session imported",
            "accloud_component": "app.gui",
            "accloud_event": "ui.action",
        }
    )

    assert Render3DLogFilter().filter(render_record) is True
    assert Render3DLogFilter().filter(app_record) is False


def test_queue_listener_routes_app_and_http_to_separate_files(tmp_path: Path) -> None:
    app_log_path = tmp_path / "accloud_app.log"
    http_log_path = tmp_path / "accloud_http.log"
    render3d_log_path = tmp_path / "accloud_render3d.log"
    queue_handler, listener = build_queue_listener(
        app_log_path=app_log_path,
        http_log_path=http_log_path,
        render3d_log_path=render3d_log_path,
        app_level=logging.INFO,
        http_level=logging.INFO,
        max_bytes=1024 * 1024,
        backups=2,
        compress=False,
        compress_level=6,
    )

    root = logging.getLogger("tests.logging.queue")
    root.setLevel(logging.INFO)
    root.propagate = False
    root.handlers = [queue_handler]
    listener.start()
    try:
        emit_event(
            root,
            logging.INFO,
            event="ui.action",
            msg="UI click",
            component="app.gui",
        )
        emit_event(
            root,
            logging.INFO,
            event="http.request",
            msg="HTTP call",
            component="accloud.http",
        )
        emit_event(
            root,
            logging.INFO,
            event="build.stage_done",
            msg="Geometry built",
            component="render3d.build",
            data={"render3d": {"stage": "triangulate", "tris": 10}},
        )
        time.sleep(0.1)
    finally:
        listener.stop()
        root.handlers = []

    app_lines = [line for line in app_log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    http_lines = [line for line in http_log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    render3d_lines = [line for line in render3d_log_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert len(app_lines) == 2
    assert len(http_lines) == 1
    assert len(render3d_lines) == 1
    assert json.loads(app_lines[0])["event"] == "ui.action"
    assert json.loads(http_lines[0])["event"] == "http.request"
    assert json.loads(render3d_lines[0])["event"] == "build.stage_done"
