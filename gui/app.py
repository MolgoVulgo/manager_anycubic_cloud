from __future__ import annotations

import faulthandler
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import sys

from accloud.api import AnycubicCloudApi
from accloud.client import CloudHttpClient
from accloud.config import AppConfig
from accloud.models import FileItem, Quota, SessionData
from accloud.session_store import extract_tokens_from_har, load_session, merge_sessions, save_session
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
    root_logger = logging.getLogger()
    level = getattr(logging, config.log_level, logging.INFO)
    root_logger.setLevel(level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    config.http_log_path.parent.mkdir(parents=True, exist_ok=True)
    http_file_handler = TimedRotatingFileHandler(
        filename=str(config.http_log_path),
        when="midnight",
        interval=1,
        backupCount=config.http_log_retention_days,
        encoding="utf-8",
    )
    http_file_handler.setLevel(logging.DEBUG)
    http_file_handler.setFormatter(formatter)

    http_logger = logging.getLogger("accloud.http")
    http_logger.setLevel(logging.DEBUG)
    for handler in list(http_logger.handlers):
        http_logger.removeHandler(handler)
        handler.close()
    http_logger.addHandler(http_file_handler)
    http_logger.propagate = True


def _enable_fault_handler(config: AppConfig) -> None:
    if not config.enable_fault_handler:
        return
    fault_path = Path(config.fault_log_path)
    fault_path.parent.mkdir(parents=True, exist_ok=True)
    handle = fault_path.open("a", encoding="utf-8")
    faulthandler.enable(file=handle)


def _install_theme(app, theme: Theme) -> None:
    app.setStyle("Fusion")
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
    client: CloudHttpClient,
    api: AnycubicCloudApi,
    logger: logging.Logger,
) -> ImportHarCallback:
    def _import_har(har_path: Path, session_path: Path) -> tuple[bool, str]:
        previous_session = client.session_data
        try:
            incoming = extract_tokens_from_har(har_path)
            if not incoming.tokens:
                return False, "No token found in HAR file for Anycubic endpoints."
            current = client.session_data
            merged = merge_sessions(current, incoming)
            save_session(session_path, merged)
            client.update_session(merged)

            valid, validation_msg = _validate_connection(api=api, logger=logger)
            if not valid:
                # Roll back to the previous in-memory session when imported tokens are invalid.
                client.update_session(previous_session)
                save_session(session_path, previous_session)
                return False, f"HAR import completed but token validation failed: {validation_msg}"

            logger.info("Session token import valid tokens=%s", len(merged.tokens))
            return True, f"Session imported and validated from {har_path.name}"
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


def _validate_connection(
    *,
    api: AnycubicCloudApi,
    logger: logging.Logger,
) -> tuple[bool, str]:
    try:
        api.get_quota()
        api.list_files(page=1, page_size=1)
        return True, "Connection validated."
    except Exception as exc:
        logger.warning("Connection validation failed: %s", exc)
        return False, str(exc)


def _ensure_session_ready(
    *,
    config: AppConfig,
    client: CloudHttpClient,
    api: AnycubicCloudApi,
    logger: logging.Logger,
) -> bool:
    has_session_file = config.session_path.exists()
    has_token = bool(client.session_data.tokens)

    if has_session_file and has_token:
        valid, _msg = _validate_connection(api=api, logger=logger)
        if valid:
            return True
        logger.info("Session file exists but token is invalid. Opening HAR import dialog.")
    else:
        logger.info("No valid token in session file. Opening HAR import dialog.")

    import_cb = _make_session_import_callback(client=client, api=api, logger=logger)
    _open_session_settings_dialog(None, config=config, on_import_har=import_cb)

    # Re-check after dialog close (user may have imported a valid HAR token).
    has_token_after = bool(client.session_data.tokens)
    if not has_token_after:
        return False
    valid_after, _msg_after = _validate_connection(api=api, logger=logger)
    return valid_after


def build_main_window(
    *,
    config: AppConfig,
    client: CloudHttpClient,
    api: AnycubicCloudApi,
    auto_refresh_on_start: bool,
):
    _qtcore, qtwidgets = require_qt()
    logger = logging.getLogger("gui.app")
    session_import_cb = _make_session_import_callback(client=client, api=api, logger=logger)
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
            auto_refresh=auto_refresh_on_start,
        ),
        "Files",
    )
    tabs.addTab(build_printer_tab(window), "Printer")
    tabs.addTab(build_log_tab(window, log_path=config.http_log_path), "Log")
    root_layout.addWidget(tabs, 1)
    return window


def main(argv: list[str] | None = None) -> int:
    config = AppConfig.from_env()
    _configure_logging(config)
    _enable_fault_handler(config)
    logger = logging.getLogger("gui.app")

    try:
        qtcore, qtwidgets = require_qt()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 2

    qtcore.QCoreApplication.setAttribute(
        qtcore.Qt.ApplicationAttribute.AA_DontUseNativeDialogs,
        True,
    )

    client = _create_cloud_client(config, logger)
    api = AnycubicCloudApi(client)

    app = qtwidgets.QApplication(argv or sys.argv)
    app.aboutToQuit.connect(client.close)
    _install_theme(app, Theme())

    session_ready = _ensure_session_ready(config=config, client=client, api=api, logger=logger)

    window = build_main_window(
        config=config,
        client=client,
        api=api,
        auto_refresh_on_start=session_ready,
    )
    window.show()
    logger.info("GUI started in phase-3 cloud mode")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
