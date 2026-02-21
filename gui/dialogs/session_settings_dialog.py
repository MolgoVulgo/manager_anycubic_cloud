from __future__ import annotations

from gui.qt_compat import require_qt
from gui.widgets import connect_stub_action, make_panel


def build_session_settings_dialog(parent=None):
    _qtcore, qtwidgets = require_qt()
    dialog = qtwidgets.QDialog(parent)
    dialog.setWindowTitle("Session Settings")
    dialog.resize(700, 440)

    layout = qtwidgets.QVBoxLayout(dialog)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(12)

    title = qtwidgets.QLabel("Session Settings")
    title.setObjectName("title")
    title.setStyleSheet("font-size: 24px;")
    subtitle = qtwidgets.QLabel("Design preview only. Session behavior will be wired in phase 3.")
    subtitle.setObjectName("subtitle")
    layout.addWidget(title)
    layout.addWidget(subtitle)

    import_panel = make_panel(parent=dialog, object_name="panel")
    import_layout = qtwidgets.QFormLayout(import_panel)
    import_layout.setContentsMargins(12, 12, 12, 12)
    import_layout.setSpacing(10)

    har_path = qtwidgets.QLineEdit()
    har_path.setPlaceholderText("/path/to/session.har")
    import_layout.addRow("HAR file", har_path)

    session_path = qtwidgets.QLineEdit(".accloud/session.json")
    import_layout.addRow("Session target", session_path)

    strategy = qtwidgets.QComboBox()
    strategy.addItems(["Merge cookies + tokens", "Replace session only"])
    import_layout.addRow("Import strategy", strategy)
    layout.addWidget(import_panel)

    info_panel = make_panel(parent=dialog, object_name="cardAlt")
    info_layout = qtwidgets.QVBoxLayout(info_panel)
    info_layout.setContentsMargins(12, 12, 12, 12)
    info_layout.setSpacing(6)
    info_layout.addWidget(qtwidgets.QLabel("Security reminders"))
    info_layout.addWidget(qtwidgets.QLabel("- Never expose Authorization, cookies, or signed URLs in logs."))
    info_layout.addWidget(qtwidgets.QLabel("- Session file permissions are expected to be 0600."))
    layout.addWidget(info_panel)

    buttons = qtwidgets.QHBoxLayout()
    browse = qtwidgets.QPushButton("Browse HAR")
    import_btn = qtwidgets.QPushButton("Import HAR")
    import_btn.setObjectName("primary")
    close = qtwidgets.QPushButton("Close")

    connect_stub_action(browse, "Browse HAR file")
    connect_stub_action(import_btn, "Import HAR session")
    close.clicked.connect(dialog.reject)

    buttons.addWidget(browse)
    buttons.addStretch(1)
    buttons.addWidget(close)
    buttons.addWidget(import_btn)
    layout.addLayout(buttons)
    return dialog

