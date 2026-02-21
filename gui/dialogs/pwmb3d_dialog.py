from __future__ import annotations

from gui.qt_compat import require_qt
from gui.widgets import connect_stub_action, make_panel


def _build_viewport_placeholder(parent=None):
    _qtcore, qtwidgets = require_qt()
    viewport = make_panel(parent=parent, object_name="cardAlt")
    viewport.setStyleSheet(
        viewport.styleSheet()
        + """
        QFrame#cardAlt {
            background: qradialgradient(
                cx: 0.5, cy: 0.5, radius: 0.8,
                fx: 0.4, fy: 0.35,
                stop: 0 #2f5f5a,
                stop: 0.55 #21433f,
                stop: 1 #172f2c
            );
            border: 1px solid #0f2422;
            border-radius: 12px;
        }
        QLabel {
            color: #dff2ef;
        }
        """
    )

    layout = qtwidgets.QVBoxLayout(viewport)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(10)
    overlay = qtwidgets.QLabel("3D viewport placeholder")
    overlay.setStyleSheet("font-size: 22px; font-weight: 650;")
    helper = qtwidgets.QLabel("OpenGL renderer and mesh upload are intentionally disabled in phase 2.")
    layout.addWidget(overlay)
    layout.addWidget(helper)
    layout.addStretch(1)
    return viewport


def build_pwmb3d_dialog(parent=None):
    qtcore, qtwidgets = require_qt()
    dialog = qtwidgets.QDialog(parent)
    dialog.setWindowTitle("PWMB 3D Viewer")
    dialog.resize(960, 620)

    layout = qtwidgets.QVBoxLayout(dialog)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(12)

    title = qtwidgets.QLabel("PWMB 3D Viewer")
    title.setObjectName("title")
    title.setStyleSheet("font-size: 24px;")
    subtitle = qtwidgets.QLabel("Design-only shell with controls and viewport composition.")
    subtitle.setObjectName("subtitle")
    layout.addWidget(title)
    layout.addWidget(subtitle)

    split = qtwidgets.QHBoxLayout()
    split.setSpacing(10)
    layout.addLayout(split, 1)

    controls = make_panel(parent=dialog, object_name="panel")
    controls.setMinimumWidth(260)
    form = qtwidgets.QFormLayout(controls)
    form.setContentsMargins(12, 12, 12, 12)
    form.setSpacing(10)

    cutoff = qtwidgets.QSlider(qtcore.Qt.Orientation.Horizontal)
    cutoff.setRange(0, 100)
    cutoff.setValue(80)
    form.addRow("Layer cutoff", cutoff)

    stride = qtwidgets.QSlider(qtcore.Qt.Orientation.Horizontal)
    stride.setRange(1, 12)
    stride.setValue(3)
    form.addRow("Stride Z", stride)

    quality = qtwidgets.QComboBox()
    quality.addItems(["Interactive", "Balanced", "Full quality"])
    form.addRow("Quality", quality)

    contour_only = qtwidgets.QCheckBox("Contour only")
    form.addRow("", contour_only)

    split.addWidget(controls, 2)
    split.addWidget(_build_viewport_placeholder(dialog), 5)

    buttons = qtwidgets.QHBoxLayout()
    for label in ["Rebuild preview", "Reset camera", "Export screenshot"]:
        button = qtwidgets.QPushButton(label)
        connect_stub_action(button, label)
        buttons.addWidget(button)
    buttons.addStretch(1)
    close = qtwidgets.QPushButton("Close")
    close.clicked.connect(dialog.reject)
    buttons.addWidget(close)
    layout.addLayout(buttons)
    return dialog
