from __future__ import annotations

from app_gui_qt.qt_compat import require_qt
from app_gui_qt.widgets import connect_stub_action, make_panel


def build_print_dialog(parent=None):
    _qtcore, qtwidgets = require_qt()
    dialog = qtwidgets.QDialog(parent)
    dialog.setWindowTitle("Send Print Order")
    dialog.resize(700, 460)

    layout = qtwidgets.QVBoxLayout(dialog)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(12)

    title = qtwidgets.QLabel("Print Order")
    title.setObjectName("title")
    title.setStyleSheet("font-size: 24px;")
    subtitle = qtwidgets.QLabel("Visual draft only. Payload and API call are deferred to phase 3.")
    subtitle.setObjectName("subtitle")
    layout.addWidget(title)
    layout.addWidget(subtitle)

    split = qtwidgets.QHBoxLayout()
    split.setSpacing(10)
    layout.addLayout(split, 1)

    left = make_panel(parent=dialog, object_name="panel")
    left_layout = qtwidgets.QVBoxLayout(left)
    left_layout.setContentsMargins(12, 12, 12, 12)
    left_layout.setSpacing(8)

    left_layout.addWidget(qtwidgets.QLabel("Available printers"))
    printers = qtwidgets.QListWidget()
    printers.addItems(
        [
            "Photon Mono M7 - ONLINE",
            "Photon Mono 4 - PRINTING",
            "M5S Pro - OFFLINE",
        ]
    )
    left_layout.addWidget(printers, 1)
    split.addWidget(left, 2)

    right = make_panel(parent=dialog, object_name="cardAlt")
    right_layout = qtwidgets.QFormLayout(right)
    right_layout.setContentsMargins(12, 12, 12, 12)
    right_layout.setSpacing(10)

    file_id = qtwidgets.QLineEdit("demo-file-id")
    right_layout.addRow("File id", file_id)

    copies = qtwidgets.QSpinBox()
    copies.setRange(1, 5)
    copies.setValue(1)
    right_layout.addRow("Copies", copies)

    priority = qtwidgets.QComboBox()
    priority.addItems(["Normal", "High"])
    right_layout.addRow("Priority", priority)

    dry_run = qtwidgets.QCheckBox("Dry run mode")
    right_layout.addRow("", dry_run)
    split.addWidget(right, 3)

    buttons = qtwidgets.QHBoxLayout()
    send = qtwidgets.QPushButton("Send order")
    send.setObjectName("primary")
    cancel = qtwidgets.QPushButton("Close")
    send_preview = qtwidgets.QPushButton("Preview payload")

    connect_stub_action(send, "Send print order")
    connect_stub_action(send_preview, "Preview print payload")
    cancel.clicked.connect(dialog.reject)

    buttons.addWidget(send_preview)
    buttons.addStretch(1)
    buttons.addWidget(cancel)
    buttons.addWidget(send)
    layout.addLayout(buttons)
    return dialog

