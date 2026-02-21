from __future__ import annotations

from gui.qt_compat import require_qt
from gui.widgets import apply_fade_in, connect_stub_action, make_badge, make_metric_card, make_panel


def _printer_card(printer: dict[str, str], parent=None):
    _qtcore, qtwidgets = require_qt()
    card = make_panel(parent=parent, object_name="card")
    layout = qtwidgets.QVBoxLayout(card)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    top = qtwidgets.QHBoxLayout()
    name = qtwidgets.QLabel(printer["name"])
    name.setStyleSheet("font-size: 17px; font-weight: 650;")
    top.addWidget(name, 1)
    top.addWidget(make_badge(printer["status"], printer["status_kind"]))
    layout.addLayout(top)

    layout.addWidget(
        qtwidgets.QLabel(
            f'Location: {printer["location"]}   |   Resin profile: {printer["profile"]}'
        )
    )
    layout.addWidget(
        qtwidgets.QLabel(
            f'Last sync: {printer["last_sync"]}   |   Queue: {printer["queue_count"]}'
        )
    )

    actions = qtwidgets.QHBoxLayout()
    for label in ["Open print dialog", "Live status", "Details"]:
        button = qtwidgets.QPushButton(label)
        if label == "Open print dialog":
            button.setObjectName("primary")
        connect_stub_action(button, f'{label} for {printer["name"]}')
        actions.addWidget(button)
    actions.addStretch(1)
    layout.addLayout(actions)
    return card


def build_printer_tab(parent=None):
    _qtcore, qtwidgets = require_qt()
    root = qtwidgets.QWidget(parent)
    root.setObjectName("tabRoot")
    layout = qtwidgets.QVBoxLayout(root)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(14)

    title = qtwidgets.QLabel("Printers")
    title.setObjectName("title")
    subtitle = qtwidgets.QLabel("Station board with static data. Actions are non-functional for phase 2.")
    subtitle.setObjectName("subtitle")
    layout.addWidget(title)
    layout.addWidget(subtitle)

    toolbar = qtwidgets.QHBoxLayout()
    for label in ["Refresh printers", "Add filter", "Bulk print check"]:
        button = qtwidgets.QPushButton(label)
        connect_stub_action(button, label)
        toolbar.addWidget(button)
    toolbar.addStretch(1)
    layout.addLayout(toolbar)

    metrics = qtwidgets.QHBoxLayout()
    metrics.setSpacing(10)
    metrics.addWidget(make_metric_card("Online", "08", "Active now", parent=root), 1)
    metrics.addWidget(make_metric_card("Offline", "03", "Needs attention", parent=root), 1)
    metrics.addWidget(make_metric_card("Printing", "05", "Current jobs", parent=root), 1)
    metrics.addWidget(make_metric_card("Queued jobs", "14", "Awaiting start", parent=root), 1)
    layout.addLayout(metrics)

    board = make_panel(parent=root, object_name="panel")
    board_layout = qtwidgets.QHBoxLayout(board)
    board_layout.setContentsMargins(10, 10, 10, 10)
    board_layout.setSpacing(12)
    layout.addWidget(board, 1)

    left = qtwidgets.QWidget(board)
    left_layout = qtwidgets.QVBoxLayout(left)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(10)

    for printer in [
        {
            "name": "Photon Mono M7 - Lab A",
            "status": "ONLINE",
            "status_kind": "ok",
            "location": "Workshop A",
            "profile": "ABS-Like Grey",
            "last_sync": "2 min ago",
            "queue_count": "2 jobs",
        },
        {
            "name": "Photon Mono 4 - Rack 2",
            "status": "PRINTING",
            "status_kind": "warn",
            "location": "Workshop B",
            "profile": "Tough Resin",
            "last_sync": "30 sec ago",
            "queue_count": "1 job",
        },
        {
            "name": "M5S Pro - QA",
            "status": "OFFLINE",
            "status_kind": "danger",
            "location": "QA room",
            "profile": "Water Washable",
            "last_sync": "43 min ago",
            "queue_count": "0 job",
        },
    ]:
        left_layout.addWidget(_printer_card(printer, parent=left))
    left_layout.addStretch(1)

    right = make_panel(parent=board, object_name="cardAlt")
    right_layout = qtwidgets.QVBoxLayout(right)
    right_layout.setContentsMargins(14, 14, 14, 14)
    right_layout.setSpacing(8)
    side_title = qtwidgets.QLabel("Preview Payload")
    side_title.setStyleSheet("font-size: 16px; font-weight: 650;")
    right_layout.addWidget(side_title)

    preview = qtwidgets.QPlainTextEdit()
    preview.setReadOnly(True)
    preview.setObjectName("monoBlock")
    preview.setPlainText(
        "{\n"
        '  "file_id": "demo-file",\n'
        '  "printer_id": "printer-001",\n'
        '  "print_after_upload": false,\n'
        '  "delete_after_print": false\n'
        "}\n"
        "\n"
        "This JSON is visual only for phase 2.\n"
    )
    right_layout.addWidget(preview, 1)

    cta = qtwidgets.QPushButton("Open Print Dialog")
    cta.setObjectName("primary")
    connect_stub_action(cta, "Open Print Dialog")
    right_layout.addWidget(cta)

    board_layout.addWidget(left, 3)
    board_layout.addWidget(right, 2)

    apply_fade_in(root)
    return root

