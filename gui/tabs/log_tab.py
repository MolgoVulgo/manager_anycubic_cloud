from __future__ import annotations

from pathlib import Path
import re

from gui.qt_compat import require_qt
from gui.widgets import apply_fade_in, make_panel


_LEVEL_ORDER = {
    "UNKNOWN": 0,
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "WARN": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

_LOG_PATTERN = re.compile(
    r"^\S+\s+\S+\s+(?P<level>[A-Z]+)\s+(?P<module>[a-zA-Z0-9_.-]+)\s*:\s*(?P<message>.*)$"
)
_LOG_PATTERN_ALT = re.compile(
    r"^\S+\s+\[(?P<level>[A-Za-z]+)\]\s+(?P<module>[a-zA-Z0-9_.-]+)\s*[-:]\s*(?P<message>.*)$"
)
_LOG_PATTERN_SIMPLE = re.compile(
    r"^(?P<level>[A-Za-z]+)\s+(?P<module>[a-zA-Z0-9_.-]+)\s*[:\-]\s*(?P<message>.*)$"
)
_LOG_PATTERN_PYTHON = re.compile(
    r"^(?P<level>[A-Za-z]+):(?P<module>[a-zA-Z0-9_.-]+):\s*(?P<message>.*)$"
)
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


class LogTab:
    def __init__(self, parent=None, *, log_path: Path) -> None:
        _qtcore, qtwidgets = require_qt()
        self._qtcore = _qtcore
        self._qtwidgets = qtwidgets
        self._log_path = Path(log_path)
        self._paused = False
        self._all_lines: list[str] = []
        self._applied_query = ""
        self._known_modules: set[str] = set()
        self._file_pos = 0
        self._file_id: tuple[int, int] | None = None

        self.root = qtwidgets.QWidget(parent)
        self.root.setObjectName("tabRoot")
        layout = qtwidgets.QVBoxLayout(self.root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = qtwidgets.QLabel("Runtime Logs")
        title.setObjectName("title")
        subtitle = qtwidgets.QLabel("Live tail of application log (poll: 1s, rotation/truncate aware).")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        layout.addLayout(self._build_actions())
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

    def _build_actions(self):
        qtwidgets = self._qtwidgets
        row = qtwidgets.QHBoxLayout()
        row.setSpacing(8)

        self._reload_button = qtwidgets.QPushButton("Reload view")
        self._reload_button.clicked.connect(self.reload_all)
        row.addWidget(self._reload_button)

        self._pause_button = qtwidgets.QPushButton("Pause stream")
        self._pause_button.clicked.connect(self._toggle_pause)
        row.addWidget(self._pause_button)

        self._clear_button = qtwidgets.QPushButton("Clear viewport")
        self._clear_button.clicked.connect(self._clear_viewport)
        row.addWidget(self._clear_button)
        row.addStretch(1)
        return row

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

        self._module_combo = qtwidgets.QComboBox()
        self._module_combo.addItems(["All modules"])
        self._module_combo.setCurrentText("All modules")
        self._module_combo.currentTextChanged.connect(self._render_view)
        layout.addWidget(self._module_combo, 1)

        self._query_edit = qtwidgets.QLineEdit()
        self._query_edit.setPlaceholderText("Filter text...")
        layout.addWidget(self._query_edit, 3)
        self._query_edit.returnPressed.connect(self._apply_query_filter)

        self._apply_query_button = qtwidgets.QPushButton("Filtrer")
        self._apply_query_button.clicked.connect(self._apply_query_filter)
        layout.addWidget(self._apply_query_button)
        return panel

    def _on_tick(self) -> None:
        if self._paused:
            return
        self._read_incremental()
        self._render_view()

    def reload_all(self) -> None:
        self._all_lines = []
        self._known_modules = set()
        self._file_pos = 0
        self._file_id = None
        self._read_incremental(force_reset=True)
        self._render_view()

    def _clear_viewport(self) -> None:
        self._log_view.setPlainText("")
        self._query_edit.clear()
        self._applied_query = ""

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self._pause_button.setText("Resume stream" if self._paused else "Pause stream")

    def _apply_query_filter(self) -> None:
        self._applied_query = self._query_edit.text().strip().lower()
        self._render_view()

    def _read_incremental(self, *, force_reset: bool = False) -> None:
        if not self._log_path.exists():
            self._log_view.setPlainText(f"Log file not found: {self._log_path}")
            return

        stat = self._log_path.stat()
        current_id = (int(stat.st_ino), int(stat.st_dev))
        reset = force_reset or self._file_id != current_id or stat.st_size < self._file_pos
        if reset:
            self._file_pos = 0
            self._file_id = current_id

        with self._log_path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(self._file_pos)
            new_text = handle.read()
            self._file_pos = handle.tell()

        if not new_text:
            return
        new_lines = [line for line in new_text.splitlines() if line.strip()]
        if not new_lines:
            return

        self._all_lines.extend(new_lines)
        if len(self._all_lines) > 5000:
            self._all_lines = self._all_lines[-5000:]

        for line in new_lines:
            parsed = _parse_line(line)
            module = parsed["module"]
            if module:
                self._known_modules.add(module)
        self._refresh_module_filter()

    def _refresh_module_filter(self) -> None:
        current = self._module_combo.currentText()
        modules = sorted(self._known_modules)
        values = ["All modules", *modules]
        self._module_combo.blockSignals(True)
        self._module_combo.clear()
        self._module_combo.addItems(values)
        idx = self._module_combo.findText(current)
        self._module_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._module_combo.blockSignals(False)

    def _render_view(self) -> None:
        level_filter = self._level_combo.currentText().strip().upper()
        module_filter = self._module_combo.currentText()
        query = self._applied_query

        filtered: list[str] = []
        for line in self._all_lines:
            parsed = _parse_line(line)
            line_level = _LEVEL_ORDER.get(parsed["level"], 0)
            if not _level_matches_filter(line_level=line_level, filter_label=level_filter):
                continue
            if module_filter != "All modules" and parsed["module"] != module_filter:
                continue
            if query and query not in line.lower():
                continue
            filtered.append(line)

        if len(filtered) > 1500:
            filtered = filtered[-1500:]
        self._log_view.setPlainText("\n".join(filtered))
        self._log_view.verticalScrollBar().setValue(self._log_view.verticalScrollBar().maximum())


def _parse_line(line: str) -> dict[str, str]:
    match = _LOG_PATTERN.match(line)
    if not match:
        match = _LOG_PATTERN_ALT.match(line)
    if not match:
        match = _LOG_PATTERN_SIMPLE.match(line)
    if not match:
        match = _LOG_PATTERN_PYTHON.match(line)
    if not match:
        return {"level": "UNKNOWN", "module": "", "message": line}
    level = match.group("level").upper()
    if level == "WARN":
        level = "WARNING"
    return {
        "level": level,
        "module": match.group("module"),
        "message": match.group("message"),
    }


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


def build_log_tab(parent=None, *, log_path: Path):
    tab = LogTab(parent=parent, log_path=log_path)
    return tab.root
