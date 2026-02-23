from __future__ import annotations

from collections.abc import Callable
import logging
import queue
import threading

import httpx

from accloud_core.cache_store import CacheStore
from accloud_core.models import FileItem, Quota
from accloud_core.utils import format_bytes
from app_gui_qt.qt_compat import require_qt
from app_gui_qt.widgets import apply_fade_in, connect_stub_action, make_panel


RefreshCallback = Callable[[], tuple[Quota | None, list[FileItem], str | None]]


def _require_qt_gui():
    try:
        from PySide6 import QtGui  # type: ignore
    except ImportError as exc:  # pragma: no cover - runtime env path
        raise RuntimeError(
            "PySide6 is required to run the GUI. Install dependencies from pyproject.toml."
        ) from exc
    return QtGui


class FilesTab:
    def __init__(
        self,
        parent=None,
        *,
        on_open_viewer: Callable | None = None,
        on_refresh: RefreshCallback | None = None,
        cache_store: CacheStore | None = None,
        thumbnail_ttl_s: int = 0,
    ) -> None:
        qtcore, qtwidgets = require_qt()
        self._qtcore = qtcore
        self._qtwidgets = qtwidgets
        self._logger = logging.getLogger("app_gui_qt.files")
        self._on_open_viewer = on_open_viewer
        self._on_refresh = on_refresh
        self._cache_store = cache_store
        self._thumbnail_ttl_s = max(0, int(thumbnail_ttl_s))
        self._files: list[FileItem] = []
        self._quota: Quota | None = None
        self._thumbnail_cache: dict[str, object] = {}
        self._thumbnail_failed: set[str] = set()
        self._thumbnail_inflight: set[str] = set()
        self._thumbnail_done_queue: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._thumbnail_semaphore = threading.BoundedSemaphore(4)
        self._refresh_timer: object | None = None
        self._refresh_thread: threading.Thread | None = None
        self._refresh_result: dict[str, object] = {}

        self.root = qtwidgets.QWidget(parent)
        self.root.setObjectName("tabRoot")
        self.root.setMinimumHeight(280)

        layout = qtwidgets.QVBoxLayout(self.root)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = qtwidgets.QLabel("Cloud Files")
        title.setObjectName("title")
        subtitle = qtwidgets.QLabel("Vue condensee: quota, fichiers et miniatures (100x100).")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        layout.addLayout(self._build_toolbar())
        layout.addWidget(self._build_quota_summary())

        self._status_label = qtwidgets.QLabel("")
        self._status_label.setObjectName("subtitle")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._cards_panel = make_panel(parent=self.root, object_name="panel")
        cards_layout = qtwidgets.QVBoxLayout(self._cards_panel)
        cards_layout.setContentsMargins(6, 6, 6, 6)
        cards_layout.setSpacing(6)
        self._cards_scroll = qtwidgets.QScrollArea(self._cards_panel)
        self._cards_scroll.setWidgetResizable(True)
        self._cards_scroll.setFrameShape(qtwidgets.QFrame.Shape.NoFrame)
        self._cards_scroll.setVerticalScrollBarPolicy(self._qtcore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._cards_scroll.setHorizontalScrollBarPolicy(self._qtcore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        cards_layout.addWidget(self._cards_scroll)
        layout.addWidget(self._cards_panel, 1)

        self._thumbnail_timer = qtcore.QTimer(self.root)
        self._thumbnail_timer.setInterval(180)
        self._thumbnail_timer.timeout.connect(self._drain_thumbnail_updates)
        self._thumbnail_timer.start()

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

    def _build_quota_summary(self):
        qtwidgets = self._qtwidgets
        panel = make_panel(parent=self.root, object_name="card")
        row = qtwidgets.QHBoxLayout(panel)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(8)
        self._quota_summary_label = qtwidgets.QLabel("Quota: - | Files: 0")
        self._quota_summary_label.setObjectName("subtitle")
        self._quota_summary_label.setWordWrap(True)
        row.addWidget(self._quota_summary_label, 1)
        return panel

    def set_loading(self, loading: bool, message: str | None = None) -> None:
        self._refresh_button.setEnabled(not loading)
        if message is not None:
            self._status_label.setText(message)

    def refresh(self) -> None:
        if self._on_refresh is None:
            self._status_label.setText("No cloud refresh callback configured.")
            return
        if self._refresh_thread is not None and self._refresh_thread.is_alive():
            return

        self.set_loading(True, "Loading cloud data...")
        self._refresh_result = {}

        def _worker() -> None:
            try:
                quota, files, error_message = self._on_refresh()
                self._refresh_result["quota"] = quota
                self._refresh_result["files"] = files
                self._refresh_result["error_message"] = error_message
            except Exception as exc:
                self._refresh_result["exception"] = str(exc)

        self._refresh_thread = threading.Thread(target=_worker, daemon=True, name="files-refresh")
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
            self.set_loading(False, f"Refresh failed: {exception}")
            return

        quota = self._refresh_result.get("quota")
        files = self._refresh_result.get("files")
        error_message = self._refresh_result.get("error_message")
        self.apply_refresh_result(
            quota=quota if isinstance(quota, Quota) else None,
            files=files if isinstance(files, list) else [],
            error_message=error_message if isinstance(error_message, str) else None,
        )

    def apply_refresh_result(
        self,
        *,
        quota: Quota | None,
        files: list[FileItem],
        error_message: str | None,
    ) -> None:
        if quota is not None:
            self.set_quota(quota)
        self.render_files(files)
        self.set_loading(False)
        if error_message:
            self._status_label.setText(error_message)
        elif files:
            self._status_label.setText(f"Loaded {len(files)} files from cloud API.")
        else:
            self._status_label.setText("No file returned by cloud API.")

    def set_quota(self, quota: Quota) -> None:
        self._quota = quota
        self._update_quota_summary()

    def render_files(self, files: list[FileItem]) -> None:
        self._files = list(files)
        self._update_quota_summary()
        self._render_file_cards(self._files)

    def _update_quota_summary(self) -> None:
        if self._quota is None:
            self._quota_summary_label.setText(f"Quota: - | Files: {len(self._files)}")
            return

        used = format_bytes(self._quota.used_bytes)
        total = format_bytes(self._quota.total_bytes)
        free = format_bytes(self._quota.free_bytes)
        self._quota_summary_label.setText(
            f"Quota: {used} / {total} ({self._quota.used_percent:.1f}%) | Free: {free} | Files: {len(self._files)}"
        )

    def _render_file_cards(self, files: list[FileItem]) -> None:
        qtwidgets = self._qtwidgets
        container = qtwidgets.QWidget()
        layout = qtwidgets.QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(8)

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
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(10)

        card_layout.addWidget(self._build_thumbnail(file_item, parent=card), 0)

        right = qtwidgets.QWidget(card)
        right_layout = qtwidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        top = qtwidgets.QHBoxLayout()
        name = qtwidgets.QLabel(file_item.name)
        name.setObjectName("title")
        name.setStyleSheet("font-size: 16px; font-weight: 650;")
        name.setWordWrap(True)
        top.addWidget(name, 1)

        delete_button = qtwidgets.QPushButton("Delete")
        delete_button.setObjectName("danger")
        connect_stub_action(delete_button, f"Delete for {file_item.name}")
        top.addWidget(delete_button, 0)
        right_layout.addLayout(top)

        details = [
            f"Layers: {file_item.layer_count if file_item.layer_count is not None else '-'}",
            f"Print: {_format_print_time(file_item.print_time_s)}",
            f"Upload: {file_item.upload_time or file_item.created_at or '-'}",
            f"Thickness: {_format_thickness(file_item.layer_thickness_mm)}",
        ]
        details_label = qtwidgets.QLabel(" | ".join(details))
        details_label.setObjectName("subtitle")
        details_label.setWordWrap(True)
        right_layout.addWidget(details_label)

        extra_info: list[str] = []
        if file_item.material_name:
            extra_info.append(f"Material: {file_item.material_name}")
        if file_item.machine_name:
            extra_info.append(f"Machine: {file_item.machine_name}")
        resin_text = _format_resin_usage(file_item.resin_usage_ml)
        if resin_text != "-":
            extra_info.append(f"Resin: {resin_text}")
        dims_text = _format_dimensions(file_item)
        if dims_text != "-":
            extra_info.append(f"Size XYZ: {dims_text}")
        if extra_info:
            extra_label = qtwidgets.QLabel(" | ".join(extra_info))
            extra_label.setObjectName("subtitle")
            extra_label.setWordWrap(True)
            right_layout.addWidget(extra_label)

        meta = qtwidgets.QLabel(
            f"Size: {format_bytes(file_item.size_bytes)} | Id: {file_item.file_id} | "
            f"Status: {file_item.status or '-'}"
        )
        meta.setObjectName("subtitle")
        meta.setWordWrap(True)
        right_layout.addWidget(meta)

        actions = qtwidgets.QHBoxLayout()
        details_button = qtwidgets.QPushButton("Details")
        details_button.clicked.connect(
            lambda _checked=False, item=file_item: self._show_file_details(item)
        )
        actions.addWidget(details_button)

        for label in ["Print", "Download"]:
            button = qtwidgets.QPushButton(label)
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
            self._on_open_viewer()

    def _show_file_details(self, file_item: FileItem) -> None:
        _qtcore, qtwidgets = require_qt()
        printers = ", ".join(file_item.printer_names) if file_item.printer_names else "-"
        lines = [
            "[General]",
            f"Name: {file_item.name}",
            f"File ID: {file_item.file_id}",
            f"Extension: {file_item.file_extension or '-'}",
            f"Size: {format_bytes(file_item.size_bytes)} ({file_item.size_bytes} bytes)",
            f"Gcode ID: {file_item.gcode_id or '-'}",
            f"Status: {file_item.status or '-'}",
            f"Status code: {file_item.status_code if file_item.status_code is not None else '-'}",
            "",
            "[Slicing]",
            f"Print time: {_format_print_time(file_item.print_time_s)}",
            f"Layers: {file_item.layer_count if file_item.layer_count is not None else '-'}",
            f"Layer thickness: {_format_thickness(file_item.layer_thickness_mm)}",
            f"Machine: {file_item.machine_name or '-'}",
            f"Material: {file_item.material_name or '-'}",
            f"Resin usage: {_format_resin_usage(file_item.resin_usage_ml)}",
            f"Dimensions (X/Y/Z): {_format_dimensions(file_item)}",
            f"Bottom layers: {file_item.bottom_layers if file_item.bottom_layers is not None else '-'}",
            f"Exposure time: {_format_seconds(file_item.exposure_time_s)}",
            f"Off time: {_format_seconds(file_item.off_time_s)}",
            f"Printers: {printers}",
            f"MD5: {file_item.md5 or '-'}",
            "",
            "[Cloud]",
            f"Upload time: {file_item.upload_time or '-'}",
            f"Created at: {file_item.created_at or '-'}",
            f"Updated at: {file_item.updated_at or '-'}",
            f"Thumbnail URL: {file_item.thumbnail_url or '-'}",
            f"Download URL: {file_item.download_url or '-'}",
            f"Region: {file_item.region or '-'}",
            f"Bucket: {file_item.bucket or '-'}",
            f"Path: {file_item.object_path or '-'}",
        ]

        dialog = qtwidgets.QDialog(self.root)
        dialog.setWindowTitle("File Details")
        dialog.resize(760, 460)
        dialog.setMinimumSize(620, 360)

        layout = qtwidgets.QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = qtwidgets.QLabel(file_item.name)
        title.setObjectName("title")
        title.setWordWrap(True)
        layout.addWidget(title)

        body = qtwidgets.QPlainTextEdit(dialog)
        body.setReadOnly(True)
        body.setObjectName("monoBlock")
        body.setPlainText("\n".join(lines))
        layout.addWidget(body, 1)

        buttons = qtwidgets.QDialogButtonBox(qtwidgets.QDialogButtonBox.StandardButton.Close, dialog)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        dialog.exec()

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

        payload: bytes | None = None
        if self._cache_store is not None:
            payload = self._cache_store.load_thumbnail(url, max_age_s=self._thumbnail_ttl_s)

        if payload is not None:
            pixmap = self._pixmap_from_bytes(url, payload)
            if pixmap is not None:
                return pixmap

        self._schedule_thumbnail_download(url)
        return None

    def _schedule_thumbnail_download(self, url: str) -> None:
        if url in self._thumbnail_inflight or url in self._thumbnail_failed:
            return
        self._thumbnail_inflight.add(url)

        def _worker() -> None:
            try:
                with self._thumbnail_semaphore:
                    response = httpx.get(url, timeout=5.0, follow_redirects=True)
                    try:
                        if response.status_code not in (200, 201):
                            self._thumbnail_failed.add(url)
                            return
                        payload = response.content
                    finally:
                        response.close()

                if self._cache_store is not None:
                    self._cache_store.save_thumbnail(url, payload)
            except Exception as exc:
                self._thumbnail_failed.add(url)
                self._logger.debug("Thumbnail fetch failed url=%s error=%s", url, exc)
            finally:
                self._thumbnail_inflight.discard(url)
                self._thumbnail_done_queue.put(url)

        thread = threading.Thread(target=_worker, daemon=True, name="thumbnail-fetch")
        thread.start()

    def _drain_thumbnail_updates(self) -> None:
        has_update = False
        while True:
            try:
                _ = self._thumbnail_done_queue.get_nowait()
            except queue.Empty:
                break
            has_update = True

        if has_update and self._files:
            self._render_file_cards(self._files)

    def _pixmap_from_bytes(self, url: str, payload: bytes):
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


def _format_print_time(value: int | None) -> str:
    if value is None or value <= 0:
        return "-"
    total = int(value)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _format_thickness(value: float | None) -> str:
    if value is None or value <= 0:
        return "-"
    return f"{value:.3f} mm"


def _format_resin_usage(value: float | None) -> str:
    if value is None or value <= 0:
        return "-"
    return f"{value:.2f} ml"


def _format_seconds(value: float | None) -> str:
    if value is None or value < 0:
        return "-"
    return f"{value:.3g} s"


def _format_dimensions(file_item: FileItem) -> str:
    x = file_item.size_x_mm
    y = file_item.size_y_mm
    z = file_item.size_z_mm
    if x is None and y is None and z is None:
        return "-"
    return f"{_fmt_dim(x)} / {_fmt_dim(y)} / {_fmt_dim(z)} mm"


def _fmt_dim(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.3g}"


def build_files_tab(
    parent=None,
    on_open_viewer=None,
    on_refresh: RefreshCallback | None = None,
    auto_refresh: bool = False,
    cache_store: CacheStore | None = None,
    thumbnail_ttl_s: int = 0,
):
    tab = FilesTab(
        parent=parent,
        on_open_viewer=on_open_viewer,
        on_refresh=on_refresh,
        cache_store=cache_store,
        thumbnail_ttl_s=thumbnail_ttl_s,
    )
    if auto_refresh:
        tab.refresh()
    tab.root._files_tab_controller = tab  # type: ignore[attr-defined]
    return tab.root
