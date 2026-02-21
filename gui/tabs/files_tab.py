from __future__ import annotations

from collections.abc import Callable

from accloud.models import FileItem, Quota
from accloud.utils import format_bytes
from gui.qt_compat import require_qt
from gui.widgets import apply_fade_in, connect_stub_action, make_badge, make_metric_card, make_panel


RefreshCallback = Callable[[], tuple[Quota | None, list[FileItem], str | None]]


def _make_thumbnail(file_name: str, parent=None):
    qtcore, qtwidgets = require_qt()
    frame = make_panel(parent=parent, object_name="card")
    frame.setFixedSize(100, 100)
    frame.setStyleSheet(
        frame.styleSheet()
        + """
        QFrame#card {
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 #dfe8d7, stop:0.5 #bfd3bd, stop:1 #93b39f
            );
            border: 1px solid #7f9b85;
            border-radius: 10px;
        }
        QLabel {
            color: #1f3527;
        }
        """
    )
    layout = qtwidgets.QVBoxLayout(frame)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(2)

    ext = file_name.split(".")[-1].upper()
    ext_label = qtwidgets.QLabel(ext)
    ext_label.setAlignment(qtcore.Qt.AlignmentFlag.AlignCenter)
    ext_label.setStyleSheet("font-size: 22px; font-weight: 700;")

    size_label = qtwidgets.QLabel("100x100")
    size_label.setAlignment(qtcore.Qt.AlignmentFlag.AlignCenter)
    size_label.setStyleSheet("font-size: 11px;")

    layout.addStretch(1)
    layout.addWidget(ext_label)
    layout.addWidget(size_label)
    layout.addStretch(1)
    return frame


def _status_badge_from_file(file_item: FileItem):
    status = (file_item.status or "Unknown").strip().lower()
    if status in {"ready", "online", "done"}:
        return make_badge("READY", "ok"), "READY"
    if status in {"printing", "running", "queued"}:
        return make_badge("PRINTING", "warn"), "PRINTING"
    if status in {"error", "failed", "offline"}:
        return make_badge("ERROR", "danger"), "ERROR"
    return make_badge(status.upper() if status else "UNKNOWN", "warn"), status.upper() if status else "UNKNOWN"


class FilesTab:
    def __init__(
        self,
        parent=None,
        *,
        on_open_viewer: Callable[[], None] | None = None,
        on_refresh: RefreshCallback | None = None,
    ) -> None:
        _qtcore, qtwidgets = require_qt()
        self._qtwidgets = qtwidgets
        self._on_open_viewer = on_open_viewer
        self._on_refresh = on_refresh

        self.root = qtwidgets.QWidget(parent)
        self.root.setObjectName("tabRoot")

        layout = qtwidgets.QVBoxLayout(self.root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = qtwidgets.QLabel("Cloud Files")
        title.setObjectName("title")
        subtitle = qtwidgets.QLabel("Session + cloud read actions are active in phase 3.")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        layout.addLayout(self._build_toolbar())
        layout.addLayout(self._build_metrics())
        layout.addWidget(self._build_filters())

        self._status_label = qtwidgets.QLabel("")
        self._status_label.setObjectName("subtitle")
        layout.addWidget(self._status_label)

        self._cards_panel = make_panel(parent=self.root, object_name="panel")
        cards_layout = qtwidgets.QVBoxLayout(self._cards_panel)
        cards_layout.setContentsMargins(8, 8, 8, 8)
        cards_layout.setSpacing(8)
        self._cards_scroll = qtwidgets.QScrollArea(self._cards_panel)
        self._cards_scroll.setWidgetResizable(True)
        self._cards_scroll.setFrameShape(qtwidgets.QFrame.Shape.NoFrame)
        cards_layout.addWidget(self._cards_scroll)
        layout.addWidget(self._cards_panel, 1)

        apply_fade_in(self.root)
        self.render_files(self._demo_files())

    def _build_toolbar(self):
        qtwidgets = self._qtwidgets
        row = qtwidgets.QHBoxLayout()
        row.setSpacing(8)

        self._refresh_button = qtwidgets.QPushButton("Refresh")
        self._refresh_button.clicked.connect(self.refresh)
        row.addWidget(self._refresh_button)

        upload_button = qtwidgets.QPushButton("Upload .pwmb")
        upload_button.setObjectName("primary")
        connect_stub_action(upload_button, "Upload")
        row.addWidget(upload_button)

        row.addStretch(1)
        return row

    def _build_metrics(self):
        layout = self._qtwidgets.QHBoxLayout()
        layout.setSpacing(10)
        self._metric_total = make_metric_card("Total", "-", "Account quota", parent=self.root)
        self._metric_used = make_metric_card("Used", "-", "Used quota", parent=self.root)
        self._metric_free = make_metric_card("Free", "-", "Available", parent=self.root)
        self._metric_files = make_metric_card("Files", "-", "Current page", parent=self.root)
        for metric in [self._metric_total, self._metric_used, self._metric_free, self._metric_files]:
            layout.addWidget(metric, 1)
        return layout

    def _build_filters(self):
        qtwidgets = self._qtwidgets
        panel = make_panel(parent=self.root, object_name="panel")
        layout = qtwidgets.QHBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        search = qtwidgets.QLineEdit()
        search.setPlaceholderText("Search file by name, machine, or profile")
        layout.addWidget(search, 3)

        status = qtwidgets.QComboBox()
        status.addItems(["All status", "Ready", "Printing", "Error"])
        layout.addWidget(status, 1)

        page_size = qtwidgets.QComboBox()
        page_size.addItems(["20 rows", "50 rows", "100 rows"])
        layout.addWidget(page_size, 1)

        sort = qtwidgets.QComboBox()
        sort.addItems(["Newest first", "Oldest first", "Largest first", "Name A-Z"])
        layout.addWidget(sort, 1)
        return panel

    def refresh(self) -> None:
        if self._on_refresh is None:
            self._status_label.setText("No cloud refresh callback configured.")
            return

        self._refresh_button.setEnabled(False)
        try:
            quota, files, error_message = self._on_refresh()
        finally:
            self._refresh_button.setEnabled(True)

        if quota is not None:
            self.set_quota(quota)
        self.render_files(files)
        if error_message:
            self._status_label.setText(error_message)
        elif files:
            self._status_label.setText(f"Loaded {len(files)} files from cloud API.")
        else:
            self._status_label.setText("No file returned by cloud API.")

    def set_quota(self, quota: Quota) -> None:
        self._set_metric_value(self._metric_total, format_bytes(quota.total_bytes))
        self._set_metric_value(self._metric_used, f"{format_bytes(quota.used_bytes)} ({quota.used_percent:.1f}%)")
        self._set_metric_value(self._metric_free, format_bytes(quota.free_bytes))

    def render_files(self, files: list[FileItem]) -> None:
        qtwidgets = self._qtwidgets
        container = qtwidgets.QWidget()
        layout = qtwidgets.QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(10)

        if not files:
            empty = make_panel(parent=container, object_name="cardAlt")
            empty_layout = qtwidgets.QVBoxLayout(empty)
            empty_layout.setContentsMargins(12, 12, 12, 12)
            empty_layout.addWidget(qtwidgets.QLabel("No files to display."))
            empty_layout.addWidget(qtwidgets.QLabel("Use Refresh to query the cloud API."))
            layout.addWidget(empty)
        else:
            for file_item in files:
                layout.addWidget(self._build_file_card(file_item, container))

        layout.addStretch(1)
        self._cards_scroll.setWidget(container)
        self._set_metric_value(self._metric_files, str(len(files)))

    def _build_file_card(self, file_item: FileItem, parent):
        qtwidgets = self._qtwidgets
        card = make_panel(parent=parent, object_name="cardAlt")
        card_layout = qtwidgets.QHBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(12)

        card_layout.addWidget(_make_thumbnail(file_item.name, parent=card), 0)

        right = qtwidgets.QWidget(card)
        right_layout = qtwidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        top = qtwidgets.QHBoxLayout()
        name = qtwidgets.QLabel(file_item.name)
        name.setObjectName("title")
        name.setStyleSheet("font-size: 18px; font-weight: 650;")
        top.addWidget(name, 1)
        badge, _badge_text = _status_badge_from_file(file_item)
        top.addWidget(badge)
        right_layout.addLayout(top)

        meta = qtwidgets.QLabel(
            f"Size: {format_bytes(file_item.size_bytes)}   |   Updated: {file_item.updated_at or '-'}   |   Id: {file_item.file_id}"
        )
        meta.setObjectName("subtitle")
        right_layout.addWidget(meta)

        actions = qtwidgets.QHBoxLayout()
        for label in ["Details", "Print", "Download", "Delete", "Open 3D Viewer"]:
            button = qtwidgets.QPushButton(label)
            if label == "Delete":
                button.setObjectName("danger")
            if label == "Open 3D Viewer" and self._on_open_viewer is not None:
                button.clicked.connect(self._on_open_viewer)
            else:
                connect_stub_action(button, f"{label} for {file_item.name}")
            actions.addWidget(button)
        actions.addStretch(1)
        right_layout.addLayout(actions)
        card_layout.addWidget(right, 1)
        return card

    def _demo_files(self) -> list[FileItem]:
        return [
            FileItem(
                file_id="demo-001",
                name="tower_calibration_v517.pwmb",
                size_bytes=112 * 1024 * 1024,
                updated_at="2026-02-20 22:14",
                status="ready",
            ),
            FileItem(
                file_id="demo-002",
                name="resin_benchmark_a2.pwmb",
                size_bytes=87 * 1024 * 1024,
                updated_at="2026-02-20 09:52",
                status="printing",
            ),
            FileItem(
                file_id="demo-003",
                name="prototype_shell_v08.pwmb",
                size_bytes=142 * 1024 * 1024,
                updated_at="2026-02-19 17:03",
                status="error",
            ),
        ]

    @staticmethod
    def _set_metric_value(metric_card, value: str) -> None:
        _qtcore_unused, qtwidgets = require_qt()
        for label in metric_card.findChildren(qtwidgets.QLabel):
            if label.objectName() == "metricValue":
                label.setText(value)
                return


def build_files_tab(
    parent=None,
    on_open_viewer=None,
    on_refresh: RefreshCallback | None = None,
    auto_refresh: bool = False,
):
    tab = FilesTab(parent=parent, on_open_viewer=on_open_viewer, on_refresh=on_refresh)
    if auto_refresh:
        tab.refresh()
    return tab.root
