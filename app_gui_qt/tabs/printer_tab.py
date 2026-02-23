from __future__ import annotations

from collections.abc import Callable
import json
import logging
import threading

from accloud_core.models import Printer
from app_gui_qt.qt_compat import require_qt
from app_gui_qt.widgets import apply_fade_in, make_badge, make_metric_card, make_panel


RefreshPrintersCallback = Callable[[], tuple[list[Printer], str | None]]
OpenPrintDialogCallback = Callable[[Printer | None], None]


class PrinterTab:
    def __init__(
        self,
        parent=None,
        *,
        on_open_print_dialog: OpenPrintDialogCallback | None = None,
        on_refresh: RefreshPrintersCallback | None = None,
        auto_refresh_interval_ms: int = 30_000,
    ) -> None:
        qtcore, qtwidgets = require_qt()
        self._qtcore = qtcore
        self._qtwidgets = qtwidgets
        self._logger = logging.getLogger("app_gui_qt.printers")
        self._on_open_print_dialog = on_open_print_dialog
        self._on_refresh = on_refresh
        self._printers: list[Printer] = []
        self._selected_printer_id: str | None = None
        self._refresh_timer: object | None = None
        self._refresh_thread: threading.Thread | None = None
        self._refresh_result: dict[str, object] = {}
        self._auto_refresh_interval_ms = max(1_000, int(auto_refresh_interval_ms))
        self._auto_refresh_timer: object | None = None

        self.root = qtwidgets.QWidget(parent)
        self.root.setObjectName("tabRoot")

        layout = qtwidgets.QVBoxLayout(self.root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = qtwidgets.QLabel("Printers")
        title.setObjectName("title")
        subtitle = qtwidgets.QLabel("Station board cloud: refresh, status, details, and print entrypoint.")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        layout.addLayout(self._build_toolbar())
        layout.addLayout(self._build_metrics())

        self._status_label = qtwidgets.QLabel("")
        self._status_label.setObjectName("subtitle")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        board = make_panel(parent=self.root, object_name="panel")
        board_layout = qtwidgets.QHBoxLayout(board)
        board_layout.setContentsMargins(10, 10, 10, 10)
        board_layout.setSpacing(12)
        layout.addWidget(board, 1)

        left = qtwidgets.QWidget(board)
        left_layout = qtwidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self._cards_scroll = qtwidgets.QScrollArea(left)
        self._cards_scroll.setWidgetResizable(True)
        self._cards_scroll.setFrameShape(qtwidgets.QFrame.Shape.NoFrame)
        self._cards_scroll.setVerticalScrollBarPolicy(self._qtcore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._cards_scroll.setHorizontalScrollBarPolicy(self._qtcore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_layout.addWidget(self._cards_scroll, 1)

        right = make_panel(parent=board, object_name="cardAlt")
        right_layout = qtwidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(8)
        side_title = qtwidgets.QLabel("Preview Payload")
        side_title.setStyleSheet("font-size: 16px; font-weight: 650;")
        right_layout.addWidget(side_title)

        self._preview = qtwidgets.QPlainTextEdit(right)
        self._preview.setReadOnly(True)
        self._preview.setObjectName("monoBlock")
        right_layout.addWidget(self._preview, 1)

        board_layout.addWidget(left, 3)
        board_layout.addWidget(right, 2)

        apply_fade_in(self.root)
        if self._on_refresh is None:
            self.render_printers(_demo_printers())
            self._status_label.setText("No cloud callback configured. Showing demo printers.")
        else:
            self.render_printers([])
            self._status_label.setText("Press Refresh printers to load cloud data.")

    def start_auto_refresh(self, *, immediate: bool = False) -> None:
        if self._on_refresh is None:
            return
        if self._auto_refresh_timer is None:
            timer = self._qtcore.QTimer(self.root)
            timer.setInterval(self._auto_refresh_interval_ms)
            timer.timeout.connect(self._auto_refresh_tick)
            timer.start()
            self._auto_refresh_timer = timer
        if immediate:
            self.refresh()

    def _auto_refresh_tick(self) -> None:
        if self._refresh_thread is not None and self._refresh_thread.is_alive():
            return
        self.refresh()

    def _build_toolbar(self):
        qtwidgets = self._qtwidgets
        row = qtwidgets.QHBoxLayout()
        row.setSpacing(8)

        self._refresh_button = qtwidgets.QPushButton("Refresh printers")
        self._refresh_button.clicked.connect(self.refresh)
        row.addWidget(self._refresh_button)

        row.addStretch(1)
        return row

    def _build_metrics(self):
        metrics = self._qtwidgets.QHBoxLayout()
        metrics.setSpacing(10)
        self._metric_online = make_metric_card("Online", "0", "Active now", parent=self.root)
        self._metric_offline = make_metric_card("Offline", "0", "Needs attention", parent=self.root)
        self._metric_printing = make_metric_card("Printing", "0", "Current jobs", parent=self.root)
        self._metric_history = make_metric_card("Jobs history", "0", "Completed jobs", parent=self.root)
        metrics.addWidget(self._metric_online, 1)
        metrics.addWidget(self._metric_offline, 1)
        metrics.addWidget(self._metric_printing, 1)
        metrics.addWidget(self._metric_history, 1)
        return metrics

    def refresh(self) -> None:
        if self._on_refresh is None:
            self._status_label.setText("No cloud refresh callback configured.")
            return
        if self._refresh_thread is not None and self._refresh_thread.is_alive():
            return

        self.set_loading(True, "Loading printers from cloud...")
        self._refresh_result = {}

        def _worker() -> None:
            try:
                printers, error_message = self._on_refresh()
                self._refresh_result["printers"] = printers
                self._refresh_result["error_message"] = error_message
            except Exception as exc:
                self._logger.exception("Printer refresh worker failed.")
                self._refresh_result["exception"] = str(exc)

        self._refresh_thread = threading.Thread(target=_worker, daemon=True, name="printers-refresh")
        self._refresh_thread.start()

        timer = self._qtcore.QTimer(self.root)
        timer.setInterval(70)
        timer.timeout.connect(self._poll_refresh_result)
        timer.start()
        self._refresh_timer = timer

    def _poll_refresh_result(self) -> None:
        if self._refresh_thread is not None and self._refresh_thread.is_alive():
            return
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
            self._refresh_timer = None

        exception = self._refresh_result.get("exception")
        if exception:
            self.set_loading(False, f"Printer refresh failed: {exception}")
            return

        raw_printers = self._refresh_result.get("printers")
        printers = [item for item in raw_printers if isinstance(item, Printer)] if isinstance(raw_printers, list) else []
        error_message = self._refresh_result.get("error_message")
        self.render_printers(printers)
        self.set_loading(False)
        if isinstance(error_message, str) and error_message:
            self._status_label.setText(error_message)
        elif printers:
            self._status_label.setText(f"Loaded {len(printers)} printers from cloud API.")
        else:
            self._status_label.setText("No printers returned by cloud API.")

    def set_loading(self, loading: bool, message: str | None = None) -> None:
        self._refresh_button.setEnabled(not loading)
        if message is not None:
            self._status_label.setText(message)

    def render_printers(self, printers: list[Printer]) -> None:
        self._printers = list(printers)
        if self._selected_printer_id is None and self._printers:
            self._selected_printer_id = self._printers[0].printer_id
        elif self._selected_printer_id is not None:
            ids = {item.printer_id for item in self._printers}
            if self._selected_printer_id not in ids:
                self._selected_printer_id = self._printers[0].printer_id if self._printers else None
        self._update_metrics()
        self._render_printer_cards()
        self._update_preview_payload()

    def _render_printer_cards(self) -> None:
        qtwidgets = self._qtwidgets
        container = qtwidgets.QWidget()
        layout = qtwidgets.QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(8)

        printers = self._printers
        if not printers:
            empty = make_panel(parent=container, object_name="cardAlt")
            empty_layout = qtwidgets.QVBoxLayout(empty)
            empty_layout.setContentsMargins(12, 12, 12, 12)
            empty_layout.addWidget(qtwidgets.QLabel("No printers to display."))
            empty_layout.addWidget(qtwidgets.QLabel("Use Refresh printers to query the cloud API."))
            layout.addWidget(empty)
        else:
            for printer in printers:
                layout.addWidget(self._printer_card(printer, parent=container))

        layout.addStretch(1)
        self._cards_scroll.setWidget(container)

    def _printer_card(self, printer: Printer, parent=None):
        _qtcore, qtwidgets = require_qt()
        card = make_panel(parent=parent, object_name="card")
        layout = qtwidgets.QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top = qtwidgets.QHBoxLayout()
        name = qtwidgets.QLabel(printer.name)
        name.setStyleSheet("font-size: 17px; font-weight: 650;")
        top.addWidget(name, 1)
        badge_text, badge_kind = _status_badge(printer)
        top.addWidget(make_badge(badge_text, badge_kind))
        layout.addLayout(top)

        line_1 = f"Model: {printer.model or '-'}   |   Type: {printer.printer_type or '-'}"
        line_2 = f"State: {printer.state or '-'}"
        line_3 = f"Material: {printer.material_type or '-'}"
        line_4 = (
            f"File: {_format_file_name(printer.current_file_name)}   |   "
            f"Progress: {_format_progress(printer.progress_percent)}"
        )
        line_5 = (
            f"Elapsed: {_format_minutes(printer.elapsed_time_min)}   |   "
            f"Remaining: {_format_minutes(printer.remain_time_min)}   |   "
            f"Layers: {_format_layers(printer.current_layer, printer.total_layers)}"
        )
        layout.addWidget(qtwidgets.QLabel(line_1))
        layout.addWidget(qtwidgets.QLabel(line_2))
        layout.addWidget(qtwidgets.QLabel(line_3))
        layout.addWidget(qtwidgets.QLabel(line_4))
        layout.addWidget(qtwidgets.QLabel(line_5))

        actions = qtwidgets.QHBoxLayout()
        details_button = qtwidgets.QPushButton("Details")
        details_button.clicked.connect(lambda _checked=False, item=printer: self._show_printer_details(item))
        actions.addWidget(details_button)

        actions.addStretch(1)
        layout.addLayout(actions)
        return card

    def _show_printer_details(self, printer: Printer) -> None:
        _qtcore, qtwidgets = require_qt()
        self._select_printer(printer)
        lines = [
            f"Name: {printer.name}",
            f"Printer ID: {printer.printer_id}",
            f"Model: {printer.model or '-'}",
            f"Type: {printer.printer_type or '-'}",
            f"Online: {'yes' if printer.online else 'no'}",
            f"State: {printer.state or '-'}",
            f"Reason: {printer.reason or '-'}",
            f"Description: {printer.description or '-'}",
            f"Device status: {printer.device_status if printer.device_status is not None else '-'}",
            f"Is printing: {printer.is_printing if printer.is_printing is not None else '-'}",
            f"Material type: {printer.material_type or '-'}",
            f"Print total time: {printer.print_total_time or '-'}",
            f"History jobs: {printer.print_count if printer.print_count is not None else '-'}",
            f"Current file: {_format_file_name(printer.current_file_name)}",
            f"Progress: {_format_progress(printer.progress_percent)}",
            f"Elapsed time: {_format_minutes(printer.elapsed_time_min)}",
            f"Remaining time: {_format_minutes(printer.remain_time_min)}",
            f"Current layer: {printer.current_layer if printer.current_layer is not None else '-'}",
            f"Total layers: {printer.total_layers if printer.total_layers is not None else '-'}",
            f"Task ID: {printer.task_id or '-'}",
            f"Print status: {printer.print_status if printer.print_status is not None else '-'}",
            f"Machine type: {printer.machine_type if printer.machine_type is not None else '-'}",
            f"Key: {printer.key or '-'}",
            f"Image URL: {printer.image_url or '-'}",
        ]

        dialog = qtwidgets.QDialog(self.root)
        dialog.setWindowTitle("Printer Details")
        dialog.resize(720, 440)
        dialog.setMinimumSize(580, 320)

        layout = qtwidgets.QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = qtwidgets.QLabel(printer.name)
        title.setObjectName("title")
        layout.addWidget(title)

        body = qtwidgets.QPlainTextEdit(dialog)
        body.setReadOnly(True)
        body.setObjectName("monoBlock")
        body.setPlainText("\n".join(lines))
        layout.addWidget(body, 1)

        close_button = qtwidgets.QPushButton("Close")
        close_button.clicked.connect(dialog.reject)
        layout.addWidget(close_button)

        dialog.exec()

    def _select_printer(self, printer: Printer | None) -> None:
        if printer is None:
            return
        self._selected_printer_id = printer.printer_id
        self._update_preview_payload(printer)

    def _find_selected_printer(self) -> Printer | None:
        if self._selected_printer_id:
            for printer in self._printers:
                if printer.printer_id == self._selected_printer_id:
                    return printer
        return self._printers[0] if self._printers else None

    def _update_preview_payload(self, printer: Printer | None = None) -> None:
        selected = printer or self._find_selected_printer()
        payload: dict[str, object] = {
            "file_id": "demo-file-id",
            "printer_id": None,
            "printer_name": None,
            "print_after_upload": False,
            "delete_after_print": False,
        }
        if selected is not None:
            payload["printer_id"] = selected.printer_id
            payload["printer_name"] = selected.name
            payload["current_file_name"] = selected.current_file_name
            payload["progress_percent"] = selected.progress_percent
            payload["elapsed_time_min"] = selected.elapsed_time_min
            payload["remain_time_min"] = selected.remain_time_min
        self._preview.setPlainText(json.dumps(payload, ensure_ascii=True, indent=2))

    def _update_metrics(self) -> None:
        online = sum(1 for item in self._printers if item.online)
        offline = sum(1 for item in self._printers if not item.online)
        printing = sum(1 for item in self._printers if _is_printing(item))
        history_count = sum(max(item.print_count or 0, 0) for item in self._printers)

        self._set_metric_value(self._metric_online, str(online))
        self._set_metric_value(self._metric_offline, str(offline))
        self._set_metric_value(self._metric_printing, str(printing))
        self._set_metric_value(self._metric_history, str(history_count))

    def _set_metric_value(self, metric_card, value: str) -> None:
        for label in metric_card.findChildren(self._qtwidgets.QLabel):
            if label.objectName() == "metricValue":
                label.setText(value)
                return


def _is_printing(printer: Printer) -> bool:
    state = (printer.state or "").strip().lower()
    if state in {"printing", "busy", "running", "paused", "pause", "heating", "resuming", "starting"}:
        return True
    if state in {"online", "idle", "ready", "finished", "complete", "completed", "stopped", "offline", "error", "failed"}:
        return False

    if printer.print_status is not None:
        if printer.print_status == 1:
            return True
        if printer.print_status in {0, 2}:
            return False

    if printer.is_printing is not None:
        return printer.is_printing > 0

    if printer.progress_percent is not None and 0 < printer.progress_percent < 100:
        return True
    if printer.remain_time_min is not None and printer.remain_time_min > 0:
        return True
    return False


def _status_badge(printer: Printer) -> tuple[str, str]:
    if not printer.online:
        return "OFFLINE", "danger"
    if _is_printing(printer):
        return "PRINTING", "warn"
    return "ONLINE", "ok"


def _format_file_name(value: str | None) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    if not text:
        return "-"
    return text


def _format_progress(value: int | None) -> str:
    if value is None:
        return "-"
    if value < 0:
        return "-"
    return f"{value}%"


def _format_minutes(value: int | None) -> str:
    if value is None:
        return "-"
    if value < 0:
        return "-"
    hours, minutes = divmod(value, 60)
    if hours <= 0:
        return f"{minutes} min"
    return f"{hours}h {minutes:02d}m"


def _format_layers(current_layer: int | None, total_layers: int | None) -> str:
    if current_layer is None and total_layers is None:
        return "-"
    if current_layer is None:
        return f"- / {total_layers}"
    if total_layers is None:
        return f"{current_layer} / -"
    return f"{current_layer} / {total_layers}"


def _demo_printers() -> list[Printer]:
    return [
        Printer(
            printer_id="42859",
            name="Photon Mono M7 - Lab A",
            online=True,
            state="online",
            model="Anycubic Photon M7",
            printer_type="LCD",
            description="Workshop A",
            is_printing=0,
            last_update_time="2 min ago",
            material_type="ABS-Like Grey",
            material_used="23260.42ml",
            print_count=58,
            current_file_name="-",
            progress_percent=0,
            elapsed_time_min=0,
            remain_time_min=0,
        ),
        Printer(
            printer_id="42860",
            name="Photon Mono 4 - Rack 2",
            online=True,
            state="printing",
            model="Anycubic Photon Mono 4",
            printer_type="LCD",
            description="Workshop B",
            is_printing=1,
            last_update_time="30 sec ago",
            material_type="Tough Resin",
            material_used="11020.13ml",
            print_count=77,
            current_file_name="raven_skull_19_v3.pwmb",
            progress_percent=14,
            elapsed_time_min=38,
            remain_time_min=218,
            current_layer=155,
            total_layers=1073,
            task_id="72244987",
            print_status=1,
        ),
        Printer(
            printer_id="42861",
            name="M5S Pro - QA",
            online=False,
            state="offline",
            model="Anycubic M5S Pro",
            printer_type="LCD",
            description="QA room",
            reason="offline",
            is_printing=0,
            last_update_time="43 min ago",
            material_type="Water Washable",
            material_used="4201.00ml",
            print_count=14,
            current_file_name="-",
            progress_percent=0,
        ),
    ]


def build_printer_tab(
    parent=None,
    *,
    on_open_print_dialog: OpenPrintDialogCallback | None = None,
    on_refresh: RefreshPrintersCallback | None = None,
    auto_refresh: bool = False,
    auto_refresh_interval_ms: int = 30_000,
):
    tab = PrinterTab(
        parent=parent,
        on_open_print_dialog=on_open_print_dialog,
        on_refresh=on_refresh,
        auto_refresh_interval_ms=auto_refresh_interval_ms,
    )
    if auto_refresh:
        tab.start_auto_refresh(immediate=True)
    tab.root._printer_tab_controller = tab  # type: ignore[attr-defined]
    return tab.root
