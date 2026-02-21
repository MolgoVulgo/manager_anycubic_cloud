from __future__ import annotations

from gui.qt_compat import require_qt


def build_log_tab(parent=None):
    _qtcore, qtwidgets = require_qt()
    widget = qtwidgets.QWidget(parent)
    layout = qtwidgets.QVBoxLayout(widget)

    title = qtwidgets.QLabel("Log")
    title.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title)

    text = qtwidgets.QPlainTextEdit()
    text.setReadOnly(True)
    text.setPlainText("Phase 1 skeleton: log tail will be implemented in phase 5.")
    layout.addWidget(text)
    return widget

