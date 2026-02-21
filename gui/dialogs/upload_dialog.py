from __future__ import annotations

from gui.qt_compat import require_qt
from gui.widgets import connect_stub_action, make_panel


def build_upload_dialog(parent=None):
    _qtcore, qtwidgets = require_qt()
    dialog = qtwidgets.QDialog(parent)
    dialog.setWindowTitle("Upload .pwmb")
    dialog.resize(640, 420)

    layout = qtwidgets.QVBoxLayout(dialog)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(12)

    title = qtwidgets.QLabel("Upload Job")
    title.setObjectName("title")
    title.setStyleSheet("font-size: 24px;")
    subtitle = qtwidgets.QLabel("Design preview only. Upload pipeline is planned for phase 3.")
    subtitle.setObjectName("subtitle")
    layout.addWidget(title)
    layout.addWidget(subtitle)

    form_panel = make_panel(parent=dialog, object_name="panel")
    form = qtwidgets.QFormLayout(form_panel)
    form.setContentsMargins(12, 12, 12, 12)
    form.setSpacing(10)

    file_path = qtwidgets.QLineEdit()
    file_path.setPlaceholderText("/path/to/file.pwmb")
    form.addRow("File path", file_path)

    profile = qtwidgets.QComboBox()
    profile.addItems(["Default profile", "Fast profile", "High quality profile"])
    form.addRow("Upload profile", profile)

    printer = qtwidgets.QComboBox()
    printer.addItems(["No auto print", "Photon Mono M7", "Photon Mono 4"])
    form.addRow("Print target", printer)
    layout.addWidget(form_panel)

    options_panel = make_panel(parent=dialog, object_name="cardAlt")
    options_layout = qtwidgets.QVBoxLayout(options_panel)
    options_layout.setContentsMargins(12, 12, 12, 12)
    options_layout.setSpacing(8)
    options_layout.addWidget(qtwidgets.QCheckBox("Print after upload"))
    options_layout.addWidget(qtwidgets.QCheckBox("Delete after print"))
    options_layout.addWidget(qtwidgets.QCheckBox("Keep signed URL snapshot for audit"))
    layout.addWidget(options_panel)

    buttons = qtwidgets.QHBoxLayout()
    browse = qtwidgets.QPushButton("Browse")
    start = qtwidgets.QPushButton("Start upload")
    start.setObjectName("primary")
    close = qtwidgets.QPushButton("Close")

    connect_stub_action(browse, "Browse local file")
    connect_stub_action(start, "Start upload")
    close.clicked.connect(dialog.reject)

    buttons.addWidget(browse)
    buttons.addStretch(1)
    buttons.addWidget(close)
    buttons.addWidget(start)
    layout.addLayout(buttons)
    return dialog

