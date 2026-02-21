from __future__ import annotations

from gui.qt_compat import require_qt


def build_print_dialog(parent=None):
    _qtcore, qtwidgets = require_qt()
    dialog = qtwidgets.QDialog(parent)
    dialog.setWindowTitle("Print")
    dialog.resize(480, 220)

    layout = qtwidgets.QVBoxLayout(dialog)
    layout.addWidget(qtwidgets.QLabel("Phase 1 skeleton: print payload and async status are pending."))
    layout.addWidget(qtwidgets.QLabel("Available printers (placeholder):"))

    list_widget = qtwidgets.QListWidget()
    list_widget.addItem("No printer loaded yet")
    layout.addWidget(list_widget)

    buttons = qtwidgets.QDialogButtonBox(qtwidgets.QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)
    return dialog

