from __future__ import annotations

from gui.qt_compat import require_qt


def build_files_tab(parent=None):
    _qtcore, qtwidgets = require_qt()
    widget = qtwidgets.QWidget(parent)
    layout = qtwidgets.QVBoxLayout(widget)

    title = qtwidgets.QLabel("Files")
    title.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title)
    layout.addWidget(
        qtwidgets.QLabel("Phase 1 skeleton: cloud quota, list, and actions will be wired in phase 3.")
    )

    buttons = qtwidgets.QHBoxLayout()
    for label in ["Refresh", "Details", "Print", "Download", "Delete", "Upload"]:
        button = qtwidgets.QPushButton(label)
        button.setEnabled(False)
        buttons.addWidget(button)
    layout.addLayout(buttons)
    layout.addStretch(1)
    return widget

