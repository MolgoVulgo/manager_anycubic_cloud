from __future__ import annotations

import faulthandler
import logging
from pathlib import Path
import sys

from accloud.api import AnycubicCloudApi
from accloud.client import CloudHttpClient
from accloud.config import AppConfig
from accloud.models import FileItem, Quota, SessionData
from accloud.session_store import extract_session_from_har, load_session, merge_sessions, save_session
from gui.dialogs.print_dialog import build_print_dialog
from gui.dialogs.pwmb3d_dialog import build_pwmb3d_dialog
from gui.dialogs.session_settings_dialog import ImportHarCallback, build_session_settings_dialog
from gui.dialogs.upload_dialog import build_upload_dialog
from gui.qt_compat import require_qt
from gui.tabs.files_tab import build_files_tab
from gui.tabs.log_tab import build_log_tab
from gui.tabs.printer_tab import build_printer_tab
from gui.theme import Theme


def _configure_logging(config: AppConfig) -> None:
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _enable_fault_handler(config: AppConfig) -> None:
    if not config.enable_fault_handler:
        return
    fault_path = Path(config.fault_log_path)
    fault_path.parent.mkdir(parents=True, exist_ok=True)
    handle = fault_path.open("a", encoding="utf-8")
    faulthandler.enable(file=handle)


def _install_theme(app, theme: Theme) -> None:
    app.setStyleSheet(theme.style_sheet())


def _open_upload_dialog(owner) -> None:
    dialog = build_upload_dialog(owner)
    dialog.exec()


def _open_print_dialog(owner) -> None:
    dialog = build_print_dialog(owner)
    dialog.exec()


def _open_viewer_dialog(owner) -> None:
    dialog = build_pwmb3d_dialog(owner)
    dialog.exec()


def _make_session_import_callback(
    *,
    config: AppConfig,
    client: CloudHttpClient,
    logger: logging.Logger,
) -> ImportHarCallback:
    def _import_har(har_path: Path, session_path: Path, mode: str) -> tuple[bool, str]:
        try:
            incoming = extract_session_from_har(har_path)
            current = client.session_data
            merged = merge_sessions(current, incoming) if mode == "merge" else incoming
            save_session(session_path, merged)
            client.update_session(merged)
            logger.info(
                "Session imported from HAR mode=%s cookies=%s tokens=%s",
                mode,
                len(merged.cookies),
                len(merged.tokens),
            )
            return True, f"Session imported from {har_path.name} to {session_path}"
        except Exception as exc:  # pragma: no cover - runtime safety path
            logger.exception("HAR import failed: %s", exc)
            return False, f"HAR import failed: {exc}"

    return _import_har


def _open_session_settings_dialog(owner, *, config: AppConfig, on_import_har: ImportHarCallback) -> None:
    dialog = build_session_settings_dialog(
        owner,
        default_session_path=str(config.session_path),
        on_import_har=on_import_har,
    )
    dialog.exec()


def _create_cloud_client(config: AppConfig, logger: logging.Logger) -> CloudHttpClient:
    if config.session_path.exists():
        try:
            session = load_session(config.session_path)
            logger.info(
                "Loaded session cookies=%s tokens=%s from %s",
                len(session.cookies),
                len(session.tokens),
                config.session_path,
            )
        except Exception as exc:
            logger.warning("Failed to load session file %s: %s", config.session_path, exc)
            session = SessionData()
    else:
        session = SessionData()
    return CloudHttpClient(config=config, session_data=session)


def _make_refresh_files_callback(
    *,
    api: AnycubicCloudApi,
    logger: logging.Logger,
):
    def _refresh() -> tuple[Quota | None, list[FileItem], str | None]:
        errors: list[str] = []
        quota: Quota | None = None
        files: list[FileItem] = []

        try:
            quota = api.get_quota()
        except Exception as exc:
            logger.warning("Quota refresh failed: %s", exc)
            errors.append(f"quota: {exc}")

        try:
            files = api.list_files(page=1, page_size=20)
        except Exception as exc:
            logger.warning("Files refresh failed: %s", exc)
            errors.append(f"files: {exc}")

        if errors:
            return quota, files, "Refresh partial failure: " + " | ".join(errors)
        return quota, files, None

    return _refresh


def build_main_window(
    *,
    config: AppConfig,
    client: CloudHttpClient,
    api: AnycubicCloudApi,
):
    _qtcore, qtwidgets = require_qt()
    logger = logging.getLogger("gui.app")
    session_import_cb = _make_session_import_callback(config=config, client=client, logger=logger)
    refresh_cb = _make_refresh_files_callback(api=api, logger=logger)

    window = qtwidgets.QMainWindow()
    window.setObjectName("mainWindow")
    window.setWindowTitle("Anycubic Cloud Client + PWMB Viewer (Phase 3 - Cloud)")
    window.resize(1320, 860)

    root = qtwidgets.QWidget(window)
    root_layout = qtwidgets.QVBoxLayout(root)
    root_layout.setContentsMargins(18, 14, 18, 18)
    root_layout.setSpacing(10)
    window.setCentralWidget(root)

    header = qtwidgets.QFrame(root)
    header.setObjectName("panel")
    header_layout = qtwidgets.QHBoxLayout(header)
    header_layout.setContentsMargins(14, 12, 14, 12)
    header_layout.setSpacing(10)

    title_col = qtwidgets.QVBoxLayout()
    title = qtwidgets.QLabel("Anycubic Cloud Control Room")
    title.setObjectName("title")
    subtitle = qtwidgets.QLabel(
        "Phase 3 cloud baseline: HAR import and files refresh are active."
    )
    subtitle.setObjectName("subtitle")
    title_col.addWidget(title)
    title_col.addWidget(subtitle)
    header_layout.addLayout(title_col, 1)

    upload_btn = qtwidgets.QPushButton("Upload Dialog")
    upload_btn.setObjectName("primary")
    upload_btn.clicked.connect(lambda: _open_upload_dialog(window))

    print_btn = qtwidgets.QPushButton("Print Dialog")
    print_btn.clicked.connect(lambda: _open_print_dialog(window))

    view_btn = qtwidgets.QPushButton("3D Viewer Dialog")
    view_btn.clicked.connect(lambda: _open_viewer_dialog(window))

    session_btn = qtwidgets.QPushButton("Session Settings")
    session_btn.clicked.connect(
        lambda: _open_session_settings_dialog(
            window,
            config=config,
            on_import_har=session_import_cb,
        )
    )

    for button in [session_btn, print_btn, view_btn, upload_btn]:
        header_layout.addWidget(button)

    root_layout.addWidget(header)

    tabs = qtwidgets.QTabWidget(root)
    tabs.addTab(
        build_files_tab(
            window,
            on_open_viewer=lambda: _open_viewer_dialog(window),
            on_refresh=refresh_cb,
            auto_refresh=True,
        ),
        "Files",
    )
    tabs.addTab(build_printer_tab(window), "Printer")
    tabs.addTab(build_log_tab(window), "Log")
    root_layout.addWidget(tabs, 1)
    return window


def main(argv: list[str] | None = None) -> int:
    config = AppConfig.from_env()
    _configure_logging(config)
    _enable_fault_handler(config)
    logger = logging.getLogger("gui.app")

    try:
        _qtcore, qtwidgets = require_qt()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 2

    client = _create_cloud_client(config, logger)
    api = AnycubicCloudApi(client)

    app = qtwidgets.QApplication(argv or sys.argv)
    app.aboutToQuit.connect(client.close)
    _install_theme(app, Theme())

    window = build_main_window(config=config, client=client, api=api)
    window.show()
    logger.info("GUI started in phase-3 cloud mode")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
