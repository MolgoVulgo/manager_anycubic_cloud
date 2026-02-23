from __future__ import annotations

from collections.abc import Callable

from app_gui_qt.qt_compat import require_qt


def connect_stub_action(button, feature_name: str) -> None:
    _qtcore, qtwidgets = require_qt()

    def _show_stub_message() -> None:
        qtwidgets.QMessageBox.information(
            button,
            "Design only",
            f'"{feature_name}" is a UI stub for phase 2. '
            "Behavior will be implemented in phase 3.",
        )

    button.clicked.connect(_show_stub_message)


def make_stub_handler(owner, feature_name: str) -> Callable[[], None]:
    _qtcore, qtwidgets = require_qt()

    def _handler() -> None:
        qtwidgets.QMessageBox.information(
            owner,
            "Design only",
            f'"{feature_name}" is a UI stub for phase 2. '
            "Behavior will be implemented in phase 3.",
        )

    return _handler

