from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
import gzip
import json
import logging
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
import os
from pathlib import Path
import queue
import shutil
import traceback
from typing import Any
from uuid import uuid4

from accloud_core.utils import is_sensitive_key, truncate_text


_REDACTED = "[REDACTED]"
_DEFAULT_DATA_MAX_DEPTH = 6
_DEFAULT_DATA_MAX_BYTES = 64 * 1024
_DEFAULT_STACK_MAX_BYTES = 8 * 1024
_OP_ID_CTX: ContextVar[str] = ContextVar("accloud_op_id", default=str(uuid4()))

_COMPONENT_PREFIXES: tuple[tuple[str, str], ...] = (
    ("accloud.http", "accloud.http"),
    ("accloud_core.http", "accloud.http"),
    ("accloud_core.client", "accloud.http"),
    ("accloud.session", "accloud.session"),
    ("accloud_core.session", "accloud.session"),
    ("accloud.auth", "accloud.auth"),
    ("accloud_core.auth", "accloud.auth"),
    ("accloud.api", "accloud.api"),
    ("accloud_core.api", "accloud.api"),
    ("pwmb_core.decode", "pwmb.decode"),
    ("pwmb_core.container", "pwmb.parse"),
    ("pwmb_core.structs", "pwmb.parse"),
    ("pwmb_core", "pwmb.parse"),
    ("render3d_core.gpu", "render3d.gpu"),
    ("render3d_core", "render3d.build"),
    ("app.task", "app.task"),
    ("app_gui_qt", "app.gui"),
)


def new_op_id() -> str:
    return str(uuid4())


def get_op_id() -> str:
    return _OP_ID_CTX.get()


def set_op_id(op_id: str) -> Token[str]:
    normalized = str(op_id).strip() or new_op_id()
    return _OP_ID_CTX.set(normalized)


def reset_op_id(token: Token[str]) -> None:
    _OP_ID_CTX.reset(token)


@contextmanager
def operation_context(op_id: str | None = None):
    value = str(op_id).strip() if op_id else new_op_id()
    token = set_op_id(value)
    try:
        yield value
    finally:
        reset_op_id(token)


def emit_event(
    logger: logging.Logger,
    level: int,
    *,
    event: str,
    msg: str,
    component: str | None = None,
    op_id: str | None = None,
    req_id: str | None = None,
    duration_ms: float | int | None = None,
    tags: Sequence[str] | None = None,
    data: Any = None,
    http: Mapping[str, Any] | None = None,
    error: Mapping[str, Any] | None = None,
    exc_info: Any = None,
) -> None:
    extra: dict[str, Any] = {
        "accloud_event": str(event).strip() or "app.log",
        "accloud_op_id": str(op_id).strip() if op_id else get_op_id(),
    }
    if component:
        extra["accloud_component"] = component
    if req_id:
        extra["accloud_req_id"] = str(req_id).strip()
    if duration_ms is not None:
        extra["accloud_duration_ms"] = float(duration_ms)
    if tags:
        extra["accloud_tags"] = [str(tag) for tag in tags if str(tag).strip()]
    if data is not None:
        extra["accloud_data"] = data
    if http:
        extra["accloud_http"] = dict(http)
    if error:
        extra["accloud_error"] = dict(error)
    logger.log(level, msg, extra=extra, exc_info=exc_info)


class CompressedRotatingFileHandler(RotatingFileHandler):
    def __init__(
        self,
        filename: str,
        *,
        max_bytes: int,
        backups: int,
        encoding: str = "utf-8",
        compress: bool = True,
        compress_level: int = 6,
    ) -> None:
        super().__init__(
            filename=filename,
            maxBytes=max(1, int(max_bytes)),
            backupCount=max(1, int(backups)),
            encoding=encoding,
        )
        self._compress = bool(compress)
        self._compress_level = max(1, min(9, int(compress_level)))
        if self._compress:
            self.namer = self._gzip_namer
            self.rotator = self._gzip_rotator

    @staticmethod
    def _gzip_namer(default_name: str) -> str:
        return f"{default_name}.gz"

    def _gzip_rotator(self, source: str, dest: str) -> None:
        with open(source, "rb") as source_handle:
            with gzip.open(dest, "wb", compresslevel=self._compress_level) as dest_handle:
                shutil.copyfileobj(source_handle, dest_handle)
        os.remove(source)


class StructuredQueueHandler(QueueHandler):
    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        return logging.makeLogRecord(record.__dict__.copy())


class JsonLineFormatter(logging.Formatter):
    def __init__(
        self,
        *,
        data_max_depth: int = _DEFAULT_DATA_MAX_DEPTH,
        data_max_bytes: int = _DEFAULT_DATA_MAX_BYTES,
    ) -> None:
        super().__init__()
        self._data_max_depth = max(1, int(data_max_depth))
        self._data_max_bytes = max(256, int(data_max_bytes))

    def format(self, record: logging.LogRecord) -> str:
        component = _resolve_component(record)
        event = _resolve_event(record, component=component)
        message = _single_line(truncate_text(record.getMessage(), max_len=2000))
        op_id = _resolve_op_id(record)

        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).astimezone().isoformat(timespec="seconds"),
            "level": record.levelname,
            "component": component,
            "event": event,
            "msg": message,
            "op_id": op_id,
            "pid": int(record.process),
            "thread": record.threadName or str(record.thread),
        }

        req_id = _opt_text(getattr(record, "accloud_req_id", None))
        if req_id:
            payload["req_id"] = req_id

        duration_ms = getattr(record, "accloud_duration_ms", None)
        if duration_ms is not None:
            payload["duration_ms"] = round(float(duration_ms), 3)

        tags = getattr(record, "accloud_tags", None)
        if isinstance(tags, Sequence) and not isinstance(tags, (str, bytes)):
            normalized_tags = [str(tag) for tag in tags if str(tag).strip()]
            if normalized_tags:
                payload["tags"] = normalized_tags

        data_payload = _sanitize_for_log(
            getattr(record, "accloud_data", None),
            max_depth=self._data_max_depth,
            max_bytes=self._data_max_bytes,
        )
        if data_payload is not None:
            payload["data"] = data_payload

        http_payload = _sanitize_for_log(
            getattr(record, "accloud_http", None),
            max_depth=self._data_max_depth,
            max_bytes=self._data_max_bytes,
        )
        if http_payload is not None:
            payload["http"] = http_payload

        error_payload = _error_payload(record)
        if error_payload:
            payload["error"] = error_payload

        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), default=str)


class AppLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        component = _resolve_component(record)
        event = _resolve_event(record, component=component)
        return not (component == "accloud.http" and event.startswith("http."))


class HttpLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        component = _resolve_component(record)
        event = _resolve_event(record, component=component)
        return component == "accloud.http" and event.startswith("http.")


def build_queue_listener(
    *,
    app_log_path: Path,
    http_log_path: Path,
    app_level: int,
    http_level: int,
    max_bytes: int,
    backups: int,
    compress: bool,
    compress_level: int,
) -> tuple[StructuredQueueHandler, QueueListener]:
    app_log_path.parent.mkdir(parents=True, exist_ok=True)
    http_log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = JsonLineFormatter()
    app_handler = CompressedRotatingFileHandler(
        filename=str(app_log_path),
        max_bytes=max_bytes,
        backups=backups,
        compress=compress,
        compress_level=compress_level,
    )
    app_handler.setLevel(app_level)
    app_handler.setFormatter(formatter)
    app_handler.addFilter(AppLogFilter())

    http_handler = CompressedRotatingFileHandler(
        filename=str(http_log_path),
        max_bytes=max_bytes,
        backups=backups,
        compress=compress,
        compress_level=compress_level,
    )
    http_handler.setLevel(http_level)
    http_handler.setFormatter(formatter)
    http_handler.addFilter(HttpLogFilter())

    log_queue: queue.SimpleQueue[logging.LogRecord] = queue.SimpleQueue()
    queue_handler = StructuredQueueHandler(log_queue)
    queue_handler.setLevel(min(app_level, http_level))

    listener = QueueListener(log_queue, app_handler, http_handler, respect_handler_level=True)
    return queue_handler, listener


def _resolve_component(record: logging.LogRecord) -> str:
    existing = _opt_text(getattr(record, "accloud_component", None))
    if existing:
        return existing
    logger_name = _opt_text(record.name) or "app.gui"
    for prefix, component in _COMPONENT_PREFIXES:
        if logger_name.startswith(prefix):
            record.accloud_component = component
            return component
    record.accloud_component = "app.gui"
    return "app.gui"


def _resolve_event(record: logging.LogRecord, *, component: str) -> str:
    existing = _opt_text(getattr(record, "accloud_event", None))
    if existing:
        return existing
    message = _opt_text(record.getMessage()).lower()
    if component == "accloud.http":
        if record.levelno >= logging.ERROR:
            event = "http.error"
        elif "retry" in message:
            event = "http.retry"
        elif "response" in message or "status" in message:
            event = "http.response"
        else:
            event = "http.request"
    else:
        event = "app.log"
    record.accloud_event = event
    return event


def _resolve_op_id(record: logging.LogRecord) -> str:
    explicit = _opt_text(getattr(record, "accloud_op_id", None))
    if explicit:
        return explicit
    op_id = get_op_id()
    record.accloud_op_id = op_id
    return op_id


def _sanitize_for_log(value: Any, *, max_depth: int, max_bytes: int) -> Any:
    if value is None:
        return None

    sanitized = _sanitize_value(value, depth=0, max_depth=max_depth)
    encoded = json.dumps(sanitized, ensure_ascii=True, default=str)
    encoded_size = len(encoded.encode("utf-8"))
    if encoded_size <= max_bytes:
        return sanitized
    budget = max(0, max_bytes - len("...TRUNCATED"))
    return f"{encoded[:budget]}...TRUNCATED"


def _sanitize_value(value: Any, *, depth: int, max_depth: int) -> Any:
    if depth >= max_depth:
        return "...TRUNCATED"

    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key)
            if is_sensitive_key(key_text):
                output[key_text] = _REDACTED
            else:
                output[key_text] = _sanitize_value(nested, depth=depth + 1, max_depth=max_depth)
        return output

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_sanitize_value(item, depth=depth + 1, max_depth=max_depth) for item in value]

    if isinstance(value, (bytes, bytearray)):
        return f"<bytes:{len(value)}>"

    if isinstance(value, Path):
        return str(value)

    return value


def _error_payload(record: logging.LogRecord) -> dict[str, Any] | None:
    explicit = getattr(record, "accloud_error", None)
    if isinstance(explicit, Mapping):
        parsed = _sanitize_for_log(explicit, max_depth=4, max_bytes=2048)
        if isinstance(parsed, Mapping):
            return dict(parsed)

    if record.exc_info:
        exc_type, exc_value, exc_tb = record.exc_info
        stack_raw = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        stack_text = _single_line(stack_raw)
        if len(stack_text.encode("utf-8")) > _DEFAULT_STACK_MAX_BYTES:
            budget = max(0, _DEFAULT_STACK_MAX_BYTES - len("...TRUNCATED"))
            stack_text = f"{stack_text[:budget]}...TRUNCATED"
        return {
            "type": exc_type.__name__ if exc_type else "Exception",
            "message": str(exc_value),
            "stack": stack_text,
        }
    return None


def _single_line(text: str) -> str:
    return " ".join(str(text).splitlines()).strip()


def _opt_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
