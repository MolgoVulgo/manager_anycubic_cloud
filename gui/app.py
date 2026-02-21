from __future__ import annotations

import faulthandler
import logging
from pathlib import Path
import sys

from accloud.config import AppConfig
from gui.qt_compat import require_qt
from gui.tabs.files_tab import build_files_tab
from gui.tabs.log_tab import build_log_tab
from gui.tabs.printer_tab import build_printer_tab


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


def build_main_window():
    _qtcore, qtwidgets = require_qt()
    window = qtwidgets.QMainWindow()
    window.setWindowTitle("Anycubic Cloud Client + PWMB Viewer (Phase 1)")
    window.resize(1200, 780)

    tabs = qtwidgets.QTabWidget()
    tabs.addTab(build_files_tab(window), "Files")
    tabs.addTab(build_printer_tab(window), "Printer")
    tabs.addTab(build_log_tab(window), "Log")
    window.setCentralWidget(tabs)
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
    window = build_main_window()
    window.show()
    logger.info("GUI started in phase-1 skeleton mode")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

