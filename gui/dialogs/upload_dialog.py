from __future__ import annotations

from gui.qt_compat import require_qt


def build_upload_dialog(parent=None):
    _qtcore, qtwidgets = require_qt()
    dialog = qtwidgets.QDialog(parent)
    dialog.setWindowTitle("Upload .pwmb")
    dialog.resize(480, 220)

    layout = qtwidgets.QVBoxLayout(dialog)
    layout.addWidget(qtwidgets.QLabel("Phase 1 skeleton: upload flow will be wired in phase 3."))
    layout.addWidget(qtwidgets.QCheckBox("Print after upload"))
    layout.addWidget(qtwidgets.QCheckBox("Delete after print"))

    buttons = qtwidgets.QDialogButtonBox(qtwidgets.QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)
    return dialog

