from __future__ import annotations

from collections.abc import Callable
import json
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
    ) -> None:
        qtcore, qtwidgets = require_qt()
        self._qtcore = qtcore
        self._qtwidgets = qtwidgets
        self._on_open_print_dialog = on_open_print_dialog
        self._on_refresh = on_refresh
        self._printers: list[Printer] = []
        self._selected_printer_id: str | None = None
        self._refresh_timer: object | None = None
        self._refresh_thread: threading.Thread | None = None
        self._refresh_result: dict[str, object] = {}

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

        self._open_print_button = qtwidgets.QPushButton("Open Print Dialog")
        self._open_print_button.setObjectName("primary")
        self._open_print_button.clicked.connect(self._open_print_dialog_for_selected)
        right_layout.addWidget(self._open_print_button)

        board_layout.addWidget(left, 3)
        board_layout.addWidget(right, 2)

        apply_fade_in(self.root)
        if self._on_refresh is None:
            self.render_printers(_demo_printers())
            self._status_label.setText("No cloud callback configured. Showing demo printers.")
        else:
            self.render_printers([])
            self._status_label.setText("Press Refresh printers to load cloud data.")

    def _build_toolbar(self):
        qtwidgets = self._qtwidgets
        row = qtwidgets.QHBoxLayout()
        row.setSpacing(8)

        self._refresh_button = qtwidgets.QPushButton("Refresh printers")
        self._refresh_button.clicked.connect(self.refresh)
        row.addWidget(self._refresh_button)

        self._toggle_filter_button = qtwidgets.QPushButton("Add filter")
        self._toggle_filter_button.clicked.connect(self._toggle_filter)
        row.addWidget(self._toggle_filter_button)

        self._bulk_button = qtwidgets.QPushButton("Bulk print check")
        self._bulk_button.clicked.connect(self._run_bulk_print_check)
        row.addWidget(self._bulk_button)

        self._filter_combo = qtwidgets.QComboBox()
        self._filter_combo.addItems(["All printers", "Online", "Printing", "Offline"])
        self._filter_combo.currentTextChanged.connect(self._render_printer_cards)
        self._filter_combo.setVisible(False)
        row.addWidget(self._filter_combo, 1)

        row.addStretch(1)
        return row

    def _build_metrics(self):
        metrics = self._qtwidgets.QHBoxLayout()
        metrics.setSpacing(10)
        self._metric_online = make_metric_card("Online", "0", "Active now", parent=self.root)
        self._metric_offline = make_metric_card("Offline", "0", "Needs attention", parent=self.root)
        self._metric_printing = make_metric_card("Printing", "0", "Current jobs", parent=self.root)
        self._metric_queued = make_metric_card("Queued jobs", "0", "Ready to start", parent=self.root)
        metrics.addWidget(self._metric_online, 1)
        metrics.addWidget(self._metric_offline, 1)
        metrics.addWidget(self._metric_printing, 1)
        metrics.addWidget(self._metric_queued, 1)
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

        printers = self._filtered_printers()
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
        line_2 = f"Last sync: {printer.last_update_time or '-'}   |   State: {printer.state or '-'}"
        line_3 = f"Material: {printer.material_type or '-'} ({printer.material_used or '-'})"
        layout.addWidget(qtwidgets.QLabel(line_1))
        layout.addWidget(qtwidgets.QLabel(line_2))
        layout.addWidget(qtwidgets.QLabel(line_3))

        actions = qtwidgets.QHBoxLayout()
        open_button = qtwidgets.QPushButton("Open print dialog")
        open_button.setObjectName("primary")
        open_button.clicked.connect(lambda _checked=False, item=printer: self._open_print_dialog_for(item))
        actions.addWidget(open_button)

        live_button = qtwidgets.QPushButton("Live status")
        live_button.clicked.connect(lambda _checked=False, item=printer: self._show_live_status(item))
        actions.addWidget(live_button)

        details_button = qtwidgets.QPushButton("Details")
        details_button.clicked.connect(lambda _checked=False, item=printer: self._show_printer_details(item))
        actions.addWidget(details_button)

        actions.addStretch(1)
        layout.addLayout(actions)
        return card

    def _filtered_printers(self) -> list[Printer]:
        if not self._filter_combo.isVisible():
            return self._printers
        selected = self._filter_combo.currentText()
        if selected == "All printers":
            return self._printers
        if selected == "Online":
            return [item for item in self._printers if item.online]
        if selected == "Printing":
            return [item for item in self._printers if _is_printing(item)]
        if selected == "Offline":
            return [item for item in self._printers if not item.online]
        return self._printers

    def _toggle_filter(self) -> None:
        visible = not self._filter_combo.isVisible()
        self._filter_combo.setVisible(visible)
        self._toggle_filter_button.setText("Hide filter" if visible else "Add filter")
        self._render_printer_cards()

    def _run_bulk_print_check(self) -> None:
        _qtcore, qtwidgets = require_qt()
        online = sum(1 for item in self._printers if item.online)
        offline = sum(1 for item in self._printers if not item.online)
        printing = sum(1 for item in self._printers if _is_printing(item))
        idle_online = max(online - printing, 0)
        qtwidgets.QMessageBox.information(
            self.root,
            "Bulk print check",
            "\n".join(
                [
                    f"Printers loaded: {len(self._printers)}",
                    f"Online: {online}",
                    f"Printing: {printing}",
                    f"Idle online: {idle_online}",
                    f"Offline: {offline}",
                ]
            ),
        )

    def _open_print_dialog_for_selected(self) -> None:
        self._open_print_dialog_for(self._find_selected_printer())

    def _open_print_dialog_for(self, printer: Printer | None) -> None:
        self._select_printer(printer)
        if self._on_open_print_dialog is None:
            _qtcore, qtwidgets = require_qt()
            qtwidgets.QMessageBox.information(
                self.root,
                "Print dialog",
                "No print dialog callback configured.",
            )
            return
        try:
            self._on_open_print_dialog(printer)
        except TypeError:
            self._on_open_print_dialog(None)

    def _show_live_status(self, printer: Printer) -> None:
        _qtcore, qtwidgets = require_qt()
        self._select_printer(printer)
        status_line = [
            f"Printer: {printer.name}",
            f"Online: {'yes' if printer.online else 'no'}",
            f"State: {printer.state or '-'}",
            f"Is printing: {printer.is_printing if printer.is_printing is not None else '-'}",
            f"Reason: {printer.reason or '-'}",
            f"Device status: {printer.device_status if printer.device_status is not None else '-'}",
            f"Last sync: {printer.last_update_time or '-'}",
        ]
        qtwidgets.QMessageBox.information(
            self.root,
            "Live status",
            "\n".join(status_line),
        )

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
            f"Last update: {printer.last_update_time or '-'}",
            f"Material type: {printer.material_type or '-'}",
            f"Material used: {printer.material_used or '-'}",
            f"Print total time: {printer.print_total_time or '-'}",
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
        self._preview.setPlainText(json.dumps(payload, ensure_ascii=True, indent=2))

    def _update_metrics(self) -> None:
        online = sum(1 for item in self._printers if item.online)
        offline = sum(1 for item in self._printers if not item.online)
        printing = sum(1 for item in self._printers if _is_printing(item))
        queued = max(online - printing, 0)

        self._set_metric_value(self._metric_online, str(online))
        self._set_metric_value(self._metric_offline, str(offline))
        self._set_metric_value(self._metric_printing, str(printing))
        self._set_metric_value(self._metric_queued, str(queued))

    def _set_metric_value(self, metric_card, value: str) -> None:
        for label in metric_card.findChildren(self._qtwidgets.QLabel):
            if label.objectName() == "metricValue":
                label.setText(value)
                return


def _is_printing(printer: Printer) -> bool:
    if printer.is_printing is not None and printer.is_printing > 0:
        return True
    state = (printer.state or "").strip().lower()
    if not state:
        return False
    return state in {"printing", "busy", "running"}


def _status_badge(printer: Printer) -> tuple[str, str]:
    if not printer.online:
        return "OFFLINE", "danger"
    if _is_printing(printer):
        return "PRINTING", "warn"
    return "ONLINE", "ok"


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
        ),
    ]


def build_printer_tab(
    parent=None,
    *,
    on_open_print_dialog: OpenPrintDialogCallback | None = None,
    on_refresh: RefreshPrintersCallback | None = None,
    auto_refresh: bool = False,
):
    tab = PrinterTab(
        parent=parent,
        on_open_print_dialog=on_open_print_dialog,
        on_refresh=on_refresh,
    )
    if auto_refresh:
        tab.refresh()
    tab.root._printer_tab_controller = tab  # type: ignore[attr-defined]
    return tab.root
