from __future__ import annotations

from pathlib import Path
import re

from gui.qt_compat import require_qt
from gui.widgets import apply_fade_in, make_metric_card, make_panel


_LEVEL_ORDER = {
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


class LogTab:
    def __init__(self, parent=None, *, log_path: Path) -> None:
        _qtcore, qtwidgets = require_qt()
        self._qtcore = _qtcore
        self._qtwidgets = qtwidgets
        self._log_path = Path(log_path)
        self._paused = False
        self._all_lines: list[str] = []
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
        subtitle = qtwidgets.QLabel("Live tail of accloud_http.log (poll: 1s, rotation/truncate aware).")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        layout.addLayout(self._build_actions())
        layout.addLayout(self._build_metrics())
        layout.addWidget(self._build_filter_bar())

        self._status = qtwidgets.QLabel(f"Log file: {self._log_path}")
        self._status.setObjectName("subtitle")
        layout.addWidget(self._status)

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

    def _build_metrics(self):
        layout = self._qtwidgets.QHBoxLayout()
        layout.setSpacing(10)
        self._metric_level = make_metric_card("Current level", "INFO+", "UI filter", parent=self.root)
        self._metric_lines = make_metric_card("HTTP lines", "0", "loaded lines", parent=self.root)
        self._metric_errors = make_metric_card("Errors", "0", "in viewport", parent=self.root)
        self._metric_file = make_metric_card("Log file", self._log_path.name, str(self._log_path), parent=self.root)
        for metric in [self._metric_level, self._metric_lines, self._metric_errors, self._metric_file]:
            layout.addWidget(metric, 1)
        return layout

    def _build_filter_bar(self):
        qtwidgets = self._qtwidgets
        panel = make_panel(parent=self.root, object_name="panel")
        layout = qtwidgets.QHBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self._level_combo = qtwidgets.QComboBox()
        self._level_combo.addItems(["DEBUG+", "INFO+", "WARNING+", "ERROR+"])
        self._level_combo.currentTextChanged.connect(self._render_view)
        layout.addWidget(self._level_combo, 1)

        self._module_combo = qtwidgets.QComboBox()
        self._module_combo.addItems(["All modules"])
        self._module_combo.currentTextChanged.connect(self._render_view)
        layout.addWidget(self._module_combo, 1)

        self._query_edit = qtwidgets.QLineEdit()
        self._query_edit.setPlaceholderText("Filter text...")
        self._query_edit.textChanged.connect(self._render_view)
        layout.addWidget(self._query_edit, 3)
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
        self._set_metric_value(self._metric_lines, "0")
        self._set_metric_value(self._metric_errors, "0")

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self._pause_button.setText("Resume stream" if self._paused else "Pause stream")
        self._status.setText(f"Log file: {self._log_path} | {'paused' if self._paused else 'live'}")

    def _read_incremental(self, *, force_reset: bool = False) -> None:
        if not self._log_path.exists():
            self._status.setText(f"Log file not found: {self._log_path}")
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
        level_threshold = _LEVEL_ORDER[self._level_combo.currentText().replace("+", "")]
        module_filter = self._module_combo.currentText()
        query = self._query_edit.text().strip().lower()

        filtered: list[str] = []
        error_count = 0
        for line in self._all_lines:
            parsed = _parse_line(line)
            line_level = _LEVEL_ORDER.get(parsed["level"], 20)
            if line_level < level_threshold:
                continue
            if module_filter != "All modules" and parsed["module"] != module_filter:
                continue
            if query and query not in line.lower():
                continue
            filtered.append(line)
            if line_level >= 40:
                error_count += 1

        if len(filtered) > 1500:
            filtered = filtered[-1500:]
        self._log_view.setPlainText("\n".join(filtered))
        self._log_view.verticalScrollBar().setValue(self._log_view.verticalScrollBar().maximum())

        self._set_metric_value(self._metric_level, self._level_combo.currentText())
        self._set_metric_value(self._metric_lines, str(len(filtered)))
        self._set_metric_value(self._metric_errors, str(error_count))
        self._status.setText(
            f"Log file: {self._log_path} | lines={len(self._all_lines)} | "
            f"{'paused' if self._paused else 'live'}"
        )

    @staticmethod
    def _set_metric_value(metric_card, value: str) -> None:
        _qtcore_unused, qtwidgets = require_qt()
        for label in metric_card.findChildren(qtwidgets.QLabel):
            if label.objectName() == "metricValue":
                label.setText(value)
                return


def _parse_line(line: str) -> dict[str, str]:
    match = _LOG_PATTERN.match(line)
    if not match:
        return {"level": "INFO", "module": "", "message": line}
    return {
        "level": match.group("level"),
        "module": match.group("module"),
        "message": match.group("message"),
    }


def build_log_tab(parent=None, *, log_path: Path):
    tab = LogTab(parent=parent, log_path=log_path)
    return tab.root

