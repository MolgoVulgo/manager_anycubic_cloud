from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Mapping

from app_gui_qt.qt_compat import require_qt
from app_gui_qt.widgets import apply_fade_in, make_panel


_LEVEL_ORDER = {
    "UNKNOWN": 0,
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

_LEVEL_FILTERS = [
    "ALL",
    "UNKNOWN",
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
    "DEBUG+",
    "INFO+",
    "WARNING+",
    "ERROR+",
    "CRITICAL+",
]

_CACHE_MAX_LINES = 1000


class LogTab:
    def __init__(
        self,
        parent=None,
        *,
        app_log_path: Path,
        http_log_path: Path,
        fault_log_path: Path,
    ) -> None:
        _qtcore, qtwidgets = require_qt()
        self._qtcore = _qtcore
        self._qtwidgets = qtwidgets
        self._rows: list[dict[str, Any]] = []
        self._applied_query = ""
        self._seq = 0
        self._known_components: set[str] = set()
        self._known_events: set[str] = set()
        self._sources = {
            "app": {
                "path": Path(app_log_path),
                "file_pos": 0,
                "file_id": None,
            },
            "http": {
                "path": Path(http_log_path),
                "file_pos": 0,
                "file_id": None,
            },
            "fault": {
                "path": Path(fault_log_path),
                "file_pos": 0,
                "file_id": None,
            },
        }

        self.root = qtwidgets.QWidget(parent)
        self.root.setObjectName("tabRoot")
        layout = qtwidgets.QVBoxLayout(self.root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = qtwidgets.QLabel("Runtime Logs")
        title.setObjectName("title")
        subtitle = qtwidgets.QLabel(
            "Live tail app/http/fault (poll: 1s, rotation/truncate aware, parse fallback)."
        )
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        layout.addWidget(self._build_filter_bar())

        panel = make_panel(parent=self.root, object_name="cardAlt")
        panel_layout = qtwidgets.QVBoxLayout(panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(8)
        self._log_view = qtwidgets.QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setObjectName("monoBlock")
        panel_layout.addWidget(self._log_view, 1)
        layout.addWidget(panel, 1)

        self._timer = _qtcore.QTimer(self.root)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

        self.reload_all()
        apply_fade_in(self.root)

    def _build_filter_bar(self):
        qtwidgets = self._qtwidgets
        panel = make_panel(parent=self.root, object_name="panel")
        layout = qtwidgets.QHBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self._level_combo = qtwidgets.QComboBox()
        self._level_combo.addItems(_LEVEL_FILTERS)
        self._level_combo.setCurrentText("ALL")
        self._level_combo.currentTextChanged.connect(self._render_view)
        layout.addWidget(self._level_combo, 1)

        self._source_combo = qtwidgets.QComboBox()
        self._source_combo.addItems(["All sources", "app", "http", "fault"])
        self._source_combo.currentTextChanged.connect(self._render_view)
        layout.addWidget(self._source_combo, 1)

        self._component_combo = qtwidgets.QComboBox()
        self._component_combo.addItems(["All components"])
        self._component_combo.currentTextChanged.connect(self._render_view)
        layout.addWidget(self._component_combo, 2)

        self._event_combo = qtwidgets.QComboBox()
        self._event_combo.addItems(["All events"])
        self._event_combo.currentTextChanged.connect(self._render_view)
        layout.addWidget(self._event_combo, 2)

        self._op_id_edit = qtwidgets.QLineEdit()
        self._op_id_edit.setPlaceholderText("op_id exact")
        layout.addWidget(self._op_id_edit, 2)
        self._op_id_edit.textChanged.connect(self._render_view)

        self._query_edit = qtwidgets.QLineEdit()
        self._query_edit.setPlaceholderText("Filter text...")
        layout.addWidget(self._query_edit, 3)
        self._query_edit.textChanged.connect(self._apply_query_filter)
        return panel

    def _on_tick(self) -> None:
        self._read_incremental()
        self._render_view()

    def reload_all(self) -> None:
        self._rows = []
        self._known_components = set()
        self._known_events = set()
        for state in self._sources.values():
            state["file_pos"] = 0
            state["file_id"] = None
        self._read_incremental(force_reset=True)
        self._render_view()

    def _apply_query_filter(self, *_args: object) -> None:
        self._applied_query = self._query_edit.text().strip().lower()
        self._render_view()

    def _read_incremental(self, *, force_reset: bool = False) -> None:
        missing_messages: list[str] = []
        has_new_rows = False
        for source_name, state in self._sources.items():
            path: Path = state["path"]
            if not path.exists():
                missing_messages.append(f"{source_name}: {path}")
                continue

            stat = path.stat()
            current_id = (int(stat.st_ino), int(stat.st_dev))
            reset = force_reset or state["file_id"] != current_id or stat.st_size < state["file_pos"]
            if reset:
                state["file_pos"] = 0
                state["file_id"] = current_id

            with path.open("r", encoding="utf-8", errors="replace") as handle:
                handle.seek(state["file_pos"])
                new_text = handle.read()
                state["file_pos"] = handle.tell()

            if not new_text:
                continue
            new_lines = [line for line in new_text.splitlines() if line.strip()]
            if not new_lines:
                continue
            for line in new_lines:
                row = _parse_line(line, source=source_name, seq=self._seq)
                self._seq += 1
                self._rows.append(row)
                has_new_rows = True
                component = str(row.get("component", "")).strip()
                event = str(row.get("event", "")).strip()
                if component:
                    self._known_components.add(component)
                if event:
                    self._known_events.add(event)

        if missing_messages and not self._rows:
            self._log_view.setPlainText(
                "Log file(s) not found:\n" + "\n".join(missing_messages)
            )
            return

        if has_new_rows:
            self._rows.sort(
                key=lambda item: (float(item.get("_ts_sort", 0.0)), int(item.get("_seq", 0))),
                reverse=True,
            )
            if len(self._rows) > _CACHE_MAX_LINES:
                self._rows = self._rows[:_CACHE_MAX_LINES]
        self._refresh_filter_combos()

    def _refresh_filter_combos(self) -> None:
        component_current = self._component_combo.currentText()
        event_current = self._event_combo.currentText()

        components = ["All components", *sorted(self._known_components)]
        events = ["All events", *sorted(self._known_events)]

        self._component_combo.blockSignals(True)
        self._component_combo.clear()
        self._component_combo.addItems(components)
        idx = self._component_combo.findText(component_current)
        self._component_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._component_combo.blockSignals(False)

        self._event_combo.blockSignals(True)
        self._event_combo.clear()
        self._event_combo.addItems(events)
        idx = self._event_combo.findText(event_current)
        self._event_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._event_combo.blockSignals(False)

    def _render_view(self, *_args: object) -> None:
        filters = {
            "level": self._level_combo.currentText().strip().upper(),
            "source": self._source_combo.currentText().strip().lower(),
            "component": self._component_combo.currentText().strip(),
            "event": self._event_combo.currentText().strip(),
            "query": self._applied_query.strip(),
            "op_id": self._op_id_edit.text().strip(),
        }

        filtered: list[str] = []
        for row in self._rows:
            if not _row_matches_filters(row=row, filters=filters):
                continue
            serialized = _render_row(row)
            filtered.append(serialized)

        if len(filtered) > _CACHE_MAX_LINES:
            filtered = filtered[:_CACHE_MAX_LINES]
        self._log_view.setPlainText("\n".join(filtered))
        self._log_view.verticalScrollBar().setValue(self._log_view.verticalScrollBar().minimum())


def _parse_line(line: str, *, source: str, seq: int) -> dict[str, Any]:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        if source == "fault":
            ts = _now_local_iso()
            return {
                "ts": ts,
                "level": "ERROR",
                "component": "app.fault",
                "event": "fault.raw",
                "msg": line,
                "op_id": "",
                "req_id": "",
                "duration_ms": "",
                "http_status": "",
                "source": source,
                "_ts_sort": _ts_to_sort_value(ts),
                "_seq": seq,
            }
        ts = _now_local_iso()
        return {
            "ts": ts,
            "level": "UNKNOWN",
            "component": "parse_error",
            "event": "parse_error",
            "msg": line,
            "op_id": "",
            "req_id": "",
            "duration_ms": "",
            "http_status": "",
            "source": source,
            "_ts_sort": _ts_to_sort_value(ts),
            "_seq": seq,
        }

    if not isinstance(payload, dict):
        if source == "fault":
            ts = _now_local_iso()
            return {
                "ts": ts,
                "level": "ERROR",
                "component": "app.fault",
                "event": "fault.raw",
                "msg": str(payload),
                "op_id": "",
                "req_id": "",
                "duration_ms": "",
                "http_status": "",
                "source": source,
                "_ts_sort": _ts_to_sort_value(ts),
                "_seq": seq,
            }
        ts = _now_local_iso()
        return {
            "ts": ts,
            "level": "UNKNOWN",
            "component": "parse_error",
            "event": "parse_error",
            "msg": str(payload),
            "op_id": "",
            "req_id": "",
            "duration_ms": "",
            "http_status": "",
            "source": source,
            "_ts_sort": _ts_to_sort_value(ts),
            "_seq": seq,
        }

    http_payload = payload.get("http")
    http_status = ""
    if isinstance(http_payload, dict):
        raw_status = http_payload.get("status")
        http_status = str(raw_status) if raw_status is not None else ""

    ts = str(payload.get("ts", "-"))
    return {
        "ts": ts,
        "level": str(payload.get("level", "UNKNOWN")).upper(),
        "component": str(payload.get("component", "")),
        "event": str(payload.get("event", "")),
        "msg": str(payload.get("msg", "")),
        "op_id": str(payload.get("op_id", "")),
        "req_id": str(payload.get("req_id", "")),
        "duration_ms": payload.get("duration_ms", ""),
        "http_status": http_status,
        "source": source,
        "_ts_sort": _ts_to_sort_value(ts),
        "_seq": seq,
    }


def _render_row(row: Mapping[str, Any]) -> str:
    ts = _format_ts_local(str(row.get("ts", "-")))
    duration_raw = row.get("duration_ms", "")
    duration = str(duration_raw) if duration_raw not in {"", None} else "-"
    status = str(row.get("http_status", "")) or "-"
    req_id = str(row.get("req_id", "")) or "-"
    op_id = str(row.get("op_id", "")) or "-"
    component = str(row.get("component", "")) or "-"
    event = str(row.get("event", "")) or "-"
    msg = str(row.get("msg", ""))
    return (
        f"{ts}"
        f" | {str(row.get('level', 'UNKNOWN')).upper():<8}"
        f" | {row.get('source', '-')}"
        f" | {component}"
        f" | {event}"
        f" | op={op_id}"
        f" | req={req_id}"
        f" | ms={duration}"
        f" | status={status}"
        f" | {msg}"
    )


def _row_matches_filters(*, row: Mapping[str, Any], filters: Mapping[str, str]) -> bool:
    level_filter = str(filters.get("level", "ALL"))
    source_filter = str(filters.get("source", "all sources")).lower()
    component_filter = str(filters.get("component", "All components"))
    event_filter = str(filters.get("event", "All events"))
    query = str(filters.get("query", "")).lower()
    op_id_filter = str(filters.get("op_id", ""))

    line_level = _LEVEL_ORDER.get(str(row.get("level", "UNKNOWN")).upper(), 0)
    if not _level_matches_filter(line_level=line_level, filter_label=level_filter):
        return False

    if source_filter != "all sources" and str(row.get("source", "")).lower() != source_filter:
        return False

    if component_filter != "All components" and str(row.get("component", "")).lower() != component_filter.lower():
        return False

    if event_filter != "All events" and str(row.get("event", "")).lower() != event_filter.lower():
        return False

    if op_id_filter and str(row.get("op_id", "")) != op_id_filter:
        return False

    if query and query not in _row_search_text(row).lower():
        return False

    return True


def _row_search_text(row: Mapping[str, Any]) -> str:
    return " ".join(
        [
            str(row.get("ts", "")),
            str(row.get("level", "")),
            str(row.get("source", "")),
            str(row.get("component", "")),
            str(row.get("event", "")),
            str(row.get("op_id", "")),
            str(row.get("req_id", "")),
            str(row.get("duration_ms", "")),
            str(row.get("http_status", "")),
            str(row.get("msg", "")),
        ]
    )


def _format_ts_local(value: str) -> str:
    raw = str(value).strip()
    if not raw or raw == "-":
        return "-"

    normalized = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return raw

    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.strftime("%Y-%m-%d__%H:%M:%S")


def _now_local_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _ts_to_sort_value(value: str) -> float:
    raw = str(value).strip()
    if not raw or raw == "-":
        return 0.0

    normalized = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return 0.0

    if dt.tzinfo is None:
        dt = dt.astimezone()
    return float(dt.timestamp())


def _level_matches_filter(*, line_level: int, filter_label: str) -> bool:
    normalized = filter_label.strip().upper()
    if normalized == "ALL":
        return True

    if normalized.endswith("+"):
        base = normalized[:-1]
        threshold = _LEVEL_ORDER.get(base)
        if threshold is None:
            return True
        return line_level >= threshold

    expected = _LEVEL_ORDER.get(normalized)
    if expected is None:
        return True
    return line_level == expected


def build_log_tab(parent=None, *, app_log_path: Path, http_log_path: Path, fault_log_path: Path):
    tab = LogTab(
        parent=parent,
        app_log_path=app_log_path,
        http_log_path=http_log_path,
        fault_log_path=fault_log_path,
    )
    return tab.root
