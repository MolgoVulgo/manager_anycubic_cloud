from __future__ import annotations

import faulthandler
import logging
from pathlib import Path
import sys

from accloud.config import AppConfig
from gui.dialogs.print_dialog import build_print_dialog
from gui.dialogs.pwmb3d_dialog import build_pwmb3d_dialog
from gui.dialogs.upload_dialog import build_upload_dialog
from gui.qt_compat import require_qt
from gui.tabs.files_tab import build_files_tab
from gui.tabs.log_tab import build_log_tab
from gui.tabs.printer_tab import build_printer_tab
from gui.theme import Theme
from gui.widgets import connect_stub_action


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


def build_main_window():
    _qtcore, qtwidgets = require_qt()
    window = qtwidgets.QMainWindow()
    window.setObjectName("mainWindow")
    window.setWindowTitle("Anycubic Cloud Client + PWMB Viewer (Phase 2 - Design)")
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
        "Phase 2 visual interface. Buttons intentionally use non-functional stubs."
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
    connect_stub_action(session_btn, "Session settings")

    for button in [session_btn, print_btn, view_btn, upload_btn]:
        header_layout.addWidget(button)

    root_layout.addWidget(header)

    tabs = qtwidgets.QTabWidget(root)
    tabs.addTab(build_files_tab(window), "Files")
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

    app = qtwidgets.QApplication(argv or sys.argv)
    _install_theme(app, Theme())
    window = build_main_window()
    window.show()
    logger.info("GUI started in phase-2 design mode")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

