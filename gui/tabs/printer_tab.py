from __future__ import annotations

from gui.qt_compat import require_qt


def build_printer_tab(parent=None):
    _qtcore, qtwidgets = require_qt()
    widget = qtwidgets.QWidget(parent)
    layout = qtwidgets.QVBoxLayout(widget)

    title = qtwidgets.QLabel("Printer")
    title.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title)
    layout.addWidget(
        qtwidgets.QLabel("Phase 1 skeleton: printer list and print workflow are not wired yet.")
    )

    action_bar = qtwidgets.QHBoxLayout()
    refresh_button = qtwidgets.QPushButton("Refresh printers")
    refresh_button.setEnabled(False)
    action_bar.addWidget(refresh_button)
    action_bar.addStretch(1)
    layout.addLayout(action_bar)
    layout.addStretch(1)
    return widget

