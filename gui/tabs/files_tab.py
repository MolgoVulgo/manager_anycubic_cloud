from __future__ import annotations

from collections.abc import Callable
import logging

import httpx

from accloud.models import FileItem, Quota
from accloud.utils import format_bytes
from gui.qt_compat import require_qt
from gui.widgets import apply_fade_in, connect_stub_action, make_badge, make_metric_card, make_panel


RefreshCallback = Callable[[], tuple[Quota | None, list[FileItem], str | None]]


def _require_qt_gui():
    try:
        from PySide6 import QtGui  # type: ignore
    except ImportError as exc:  # pragma: no cover - runtime env path
        raise RuntimeError(
            "PySide6 is required to run the GUI. Install dependencies from pyproject.toml."
        ) from exc
    return QtGui


def _status_badge_from_file(file_item: FileItem):
    status = (file_item.status or "Unknown").strip().lower()
    if status in {"ready", "online", "done", "uploaded"}:
        return make_badge("READY", "ok"), "READY"
    if status in {"printing", "running"}:
        return make_badge("PRINTING", "warn"), "PRINTING"
    if status in {"queued", "pending"}:
        return make_badge("QUEUED", "warn"), "QUEUED"
    if status in {"error", "failed", "offline"}:
        return make_badge("ERROR", "danger"), "ERROR"
    return make_badge(status.upper() if status else "UNKNOWN", "warn"), status.upper() if status else "UNKNOWN"


class FilesTab:
    def __init__(
        self,
        parent=None,
        *,
        on_open_viewer: Callable | None = None,
        on_refresh: RefreshCallback | None = None,
    ) -> None:
        _qtcore, qtwidgets = require_qt()
        self._qtwidgets = qtwidgets
        self._logger = logging.getLogger("gui.files")
        self._on_open_viewer = on_open_viewer
        self._on_refresh = on_refresh
        self._all_files: list[FileItem] = []
        self._thumbnail_cache: dict[str, object] = {}
        self._thumbnail_failed: set[str] = set()

        self.root = qtwidgets.QWidget(parent)
        self.root.setObjectName("tabRoot")

        layout = qtwidgets.QVBoxLayout(self.root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = qtwidgets.QLabel("Cloud Files")
        title.setObjectName("title")
        subtitle = qtwidgets.QLabel(
            "Quota, fichiers cloud et miniatures sont alimentes depuis les endpoints workbench."
        )
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
        self.render_files([])

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
        self._metric_files = make_metric_card("Files", "0", "Visible / total", parent=self.root)
        for metric in [self._metric_total, self._metric_used, self._metric_free, self._metric_files]:
            layout.addWidget(metric, 1)
        return layout

    def _build_filters(self):
        qtwidgets = self._qtwidgets
        panel = make_panel(parent=self.root, object_name="panel")
        layout = qtwidgets.QHBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self._search_input = qtwidgets.QLineEdit()
        self._search_input.setPlaceholderText("Search file by name, machine, id, or path")
        self._search_input.textChanged.connect(self._apply_filters)
        layout.addWidget(self._search_input, 3)

        self._status_filter = qtwidgets.QComboBox()
        self._status_filter.addItems(["All status", "Ready", "Printing", "Queued", "Error"])
        self._status_filter.currentIndexChanged.connect(self._apply_filters)
        layout.addWidget(self._status_filter, 1)

        self._page_size_filter = qtwidgets.QComboBox()
        self._page_size_filter.addItems(["20 rows", "50 rows", "100 rows"])
        self._page_size_filter.currentIndexChanged.connect(self._apply_filters)
        layout.addWidget(self._page_size_filter, 1)

        self._sort_filter = qtwidgets.QComboBox()
        self._sort_filter.addItems(["Newest first", "Oldest first", "Largest first", "Name A-Z"])
        self._sort_filter.currentIndexChanged.connect(self._apply_filters)
        layout.addWidget(self._sort_filter, 1)
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
        self._all_files = list(files)
        self._apply_filters()

    def _apply_filters(self) -> None:
        search = self._search_input.text().strip().lower() if hasattr(self, "_search_input") else ""
        status_label = self._status_filter.currentText().strip().lower() if hasattr(self, "_status_filter") else "all status"
        sort_label = self._sort_filter.currentText().strip().lower() if hasattr(self, "_sort_filter") else "newest first"
        page_size = self._selected_page_size()

        filtered = [item for item in self._all_files if self._matches_filters(item, search=search, status=status_label)]
        filtered.sort(key=lambda item: self._sort_key(item, sort_label=sort_label))
        if sort_label in {"newest first", "largest first"}:
            filtered.reverse()

        visible = filtered[:page_size]
        self._render_file_cards(visible)
        self._set_metric_value(self._metric_files, f"{len(visible)}/{len(self._all_files)}")

    def _render_file_cards(self, files: list[FileItem]) -> None:
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

    def _build_file_card(self, file_item: FileItem, parent):
        qtwidgets = self._qtwidgets
        card = make_panel(parent=parent, object_name="cardAlt")
        card_layout = qtwidgets.QHBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(12)

        card_layout.addWidget(self._build_thumbnail(file_item, parent=card), 0)

        right = qtwidgets.QWidget(card)
        right_layout = qtwidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        top = qtwidgets.QHBoxLayout()
        name = qtwidgets.QLabel(file_item.name)
        name.setObjectName("title")
        name.setStyleSheet("font-size: 17px; font-weight: 650;")
        name.setWordWrap(True)
        top.addWidget(name, 1)
        badge, _badge_text = _status_badge_from_file(file_item)
        top.addWidget(badge)
        right_layout.addLayout(top)

        base_meta = [
            f"Size: {format_bytes(file_item.size_bytes)}",
            f"Id: {file_item.file_id}",
        ]
        if file_item.updated_at:
            base_meta.append(f"Updated: {file_item.updated_at}")
        elif file_item.created_at:
            base_meta.append(f"Created: {file_item.created_at}")
        if file_item.gcode_id:
            base_meta.append(f"GCode: {file_item.gcode_id}")
        meta = qtwidgets.QLabel(" | ".join(base_meta))
        meta.setObjectName("subtitle")
        meta.setWordWrap(True)
        right_layout.addWidget(meta)

        extras: list[str] = []
        if file_item.machine_name:
            extras.append(f"Machine: {file_item.machine_name}")
        if file_item.region:
            extras.append(f"Region: {file_item.region}")
        if file_item.bucket:
            extras.append(f"Bucket: {file_item.bucket}")
        if extras:
            extra_label = qtwidgets.QLabel(" | ".join(extras))
            extra_label.setObjectName("subtitle")
            extra_label.setWordWrap(True)
            right_layout.addWidget(extra_label)

        if file_item.object_path:
            path_label = qtwidgets.QLabel(f"Path: {file_item.object_path}")
            path_label.setObjectName("subtitle")
            path_label.setWordWrap(True)
            right_layout.addWidget(path_label)

        actions = qtwidgets.QHBoxLayout()
        for label in ["Details", "Print", "Download", "Delete"]:
            button = qtwidgets.QPushButton(label)
            if label == "Delete":
                button.setObjectName("danger")
            connect_stub_action(button, f"{label} for {file_item.name}")
            actions.addWidget(button)

        if file_item.name.lower().endswith(".pwmb"):
            view_button = qtwidgets.QPushButton("Open 3D Viewer")
            if self._on_open_viewer is not None:
                view_button.clicked.connect(lambda _checked=False, item=file_item: self._open_viewer_for_file(item))
            else:
                connect_stub_action(view_button, f"Open 3D Viewer for {file_item.name}")
            actions.addWidget(view_button)

        actions.addStretch(1)
        right_layout.addLayout(actions)
        card_layout.addWidget(right, 1)
        return card

    def _open_viewer_for_file(self, file_item: FileItem) -> None:
        if self._on_open_viewer is None:
            return
        try:
            self._on_open_viewer(file_item)
        except TypeError:
            # Backward compatibility: existing callback may not accept file argument.
            self._on_open_viewer()

    def _build_thumbnail(self, file_item: FileItem, parent):
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
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        image_label = qtwidgets.QLabel(frame)
        image_label.setAlignment(qtcore.Qt.AlignmentFlag.AlignCenter)
        image_label.setFixedSize(92, 92)

        pixmap = self._load_thumbnail_pixmap(file_item.thumbnail_url)
        if pixmap is not None:
            image_label.setPixmap(
                pixmap.scaled(
                    92,
                    92,
                    qtcore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    qtcore.Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            ext = file_item.name.split(".")[-1].upper()
            image_label.setText(f"{ext}\n100x100")
            image_label.setStyleSheet("font-size: 13px; font-weight: 600;")

        layout.addWidget(image_label, 1)
        return frame

    def _load_thumbnail_pixmap(self, thumbnail_url: str | None):
        if not thumbnail_url:
            return None
        url = thumbnail_url.strip()
        if not url:
            return None
        if url in self._thumbnail_cache:
            return self._thumbnail_cache[url]
        if url in self._thumbnail_failed:
            return None

        try:
            response = httpx.get(url, timeout=5.0, follow_redirects=True)
        except Exception as exc:
            self._thumbnail_failed.add(url)
            self._logger.debug("Thumbnail fetch failed url=%s error=%s", url, exc)
            return None

        try:
            if response.status_code not in (200, 201):
                self._thumbnail_failed.add(url)
                return None
            payload = response.content
        finally:
            response.close()

        try:
            qtgui = _require_qt_gui()
            pixmap = qtgui.QPixmap()
            if not pixmap.loadFromData(payload):
                self._thumbnail_failed.add(url)
                return None
            self._thumbnail_cache[url] = pixmap
            return pixmap
        except Exception as exc:
            self._thumbnail_failed.add(url)
            self._logger.debug("Thumbnail decode failed url=%s error=%s", url, exc)
            return None

    def _selected_page_size(self) -> int:
        if not hasattr(self, "_page_size_filter"):
            return 20
        text = self._page_size_filter.currentText().strip().split(" ", 1)[0]
        try:
            value = int(text)
        except ValueError:
            return 20
        return max(1, min(500, value))

    @staticmethod
    def _matches_filters(file_item: FileItem, *, search: str, status: str) -> bool:
        if search:
            haystack = " ".join(
                filter(
                    None,
                    [
                        file_item.name,
                        file_item.file_id,
                        file_item.machine_name or "",
                        file_item.object_path or "",
                    ],
                )
            ).lower()
            if search not in haystack:
                return False

        if status != "all status":
            normalized = (file_item.status or "").lower()
            if status == "ready" and normalized != "ready":
                return False
            if status == "printing" and normalized != "printing":
                return False
            if status == "queued" and normalized != "queued":
                return False
            if status == "error" and normalized != "error":
                return False
        return True

    @staticmethod
    def _sort_key(file_item: FileItem, *, sort_label: str):
        if sort_label == "largest first":
            return file_item.size_bytes
        if sort_label == "name a-z":
            return file_item.name.lower()
        if sort_label == "oldest first":
            return file_item.updated_at or file_item.created_at or ""
        return file_item.updated_at or file_item.created_at or ""

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
