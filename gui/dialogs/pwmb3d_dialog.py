from __future__ import annotations

from gui.qt_compat import require_qt


def build_pwmb3d_dialog(parent=None):
    _qtcore, qtwidgets = require_qt()
    dialog = qtwidgets.QDialog(parent)
    dialog.setWindowTitle("PWMB 3D Viewer")
    dialog.resize(760, 520)

    layout = qtwidgets.QVBoxLayout(dialog)
    layout.addWidget(
        qtwidgets.QLabel(
            "Phase 1 skeleton: OpenGL renderer and async build pipeline will be implemented in phase 3."
        )
    )
    layout.addWidget(qtwidgets.QLabel("Viewer controls (placeholder): cutoff, stride, contour-only"))

    buttons = qtwidgets.QDialogButtonBox(qtwidgets.QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)
    return dialog

