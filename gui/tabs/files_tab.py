from __future__ import annotations

from gui.qt_compat import require_qt
from gui.widgets import apply_fade_in, connect_stub_action, make_badge, make_metric_card, make_panel


def _build_toolbar(parent=None):
    _qtcore, qtwidgets = require_qt()
    row = qtwidgets.QHBoxLayout()
    row.setSpacing(8)

    import_button = qtwidgets.QPushButton("Import HAR")
    refresh_button = qtwidgets.QPushButton("Refresh")
    upload_button = qtwidgets.QPushButton("Upload .pwmb")
    upload_button.setObjectName("primary")
    open_3d_button = qtwidgets.QPushButton("Open 3D Viewer")

    for widget, label in [
        (import_button, "Import HAR"),
        (refresh_button, "Refresh files"),
        (upload_button, "Upload"),
        (open_3d_button, "Open 3D viewer"),
    ]:
        connect_stub_action(widget, label)
        row.addWidget(widget)

    row.addStretch(1)
    return row


def _build_filters(parent=None):
    _qtcore, qtwidgets = require_qt()
    panel = make_panel(parent=parent, object_name="panel")
    layout = qtwidgets.QHBoxLayout(panel)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(10)

    search = qtwidgets.QLineEdit()
    search.setPlaceholderText("Search file by name, machine, or profile")
    layout.addWidget(search, 3)

    status = qtwidgets.QComboBox()
    status.addItems(["All status", "Ready", "Printing", "Error"])
    layout.addWidget(status, 1)

    page_size = qtwidgets.QComboBox()
    page_size.addItems(["20 rows", "50 rows", "100 rows"])
    layout.addWidget(page_size, 1)

    sort = qtwidgets.QComboBox()
    sort.addItems(["Newest first", "Oldest first", "Largest first", "Name A-Z"])
    layout.addWidget(sort, 1)

    return panel


def _file_cards(parent=None):
    _qtcore, qtwidgets = require_qt()
    files = [
        {
            "name": "tower_calibration_v517.pwmb",
            "size": "112 MB",
            "updated": "2026-02-20 22:14",
            "status": ("Ready", "ok"),
            "machine": "Photon Mono M7",
        },
        {
            "name": "resin_benchmark_a2.pwmb",
            "size": "87 MB",
            "updated": "2026-02-20 09:52",
            "status": ("Printing", "warn"),
            "machine": "Photon Mono 4",
        },
        {
            "name": "prototype_shell_v08.pwmb",
            "size": "142 MB",
            "updated": "2026-02-19 17:03",
            "status": ("Error", "danger"),
            "machine": "M5S Pro",
        },
    ]

    wrapper = make_panel(parent=parent, object_name="panel")
    outer_layout = qtwidgets.QVBoxLayout(wrapper)
    outer_layout.setContentsMargins(8, 8, 8, 8)
    outer_layout.setSpacing(8)

    scroller = qtwidgets.QScrollArea(wrapper)
    scroller.setWidgetResizable(True)
    scroller.setFrameShape(qtwidgets.QFrame.Shape.NoFrame)
    outer_layout.addWidget(scroller)

    container = qtwidgets.QWidget()
    scroller.setWidget(container)
    layout = qtwidgets.QVBoxLayout(container)
    layout.setContentsMargins(2, 2, 2, 2)
    layout.setSpacing(10)

    for file_info in files:
        card = make_panel(parent=container, object_name="cardAlt")
        card_layout = qtwidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        top = qtwidgets.QHBoxLayout()
        name = qtwidgets.QLabel(file_info["name"])
        name.setObjectName("title")
        name.setStyleSheet("font-size: 18px; font-weight: 650;")
        top.addWidget(name, 1)
        top.addWidget(make_badge(file_info["status"][0], file_info["status"][1]))
        card_layout.addLayout(top)

        meta = qtwidgets.QLabel(
            f'Size: {file_info["size"]}   |   Updated: {file_info["updated"]}   |   Machine: {file_info["machine"]}'
        )
        meta.setObjectName("subtitle")
        card_layout.addWidget(meta)

        actions = qtwidgets.QHBoxLayout()
        for label in ["Details", "Print", "Download", "Delete", "Preview"]:
            button = qtwidgets.QPushButton(label)
            if label == "Delete":
                button.setObjectName("danger")
            connect_stub_action(button, f'{label} for {file_info["name"]}')
            actions.addWidget(button)
        actions.addStretch(1)
        card_layout.addLayout(actions)

        layout.addWidget(card)

    layout.addStretch(1)
    return wrapper


def build_files_tab(parent=None):
    _qtcore, qtwidgets = require_qt()
    root = qtwidgets.QWidget(parent)
    root.setObjectName("tabRoot")
    layout = qtwidgets.QVBoxLayout(root)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(14)

    title = qtwidgets.QLabel("Cloud Files")
    title.setObjectName("title")
    subtitle = qtwidgets.QLabel(
        "Visual shell only. API actions are placeholders for phase 3."
    )
    subtitle.setObjectName("subtitle")
    layout.addWidget(title)
    layout.addWidget(subtitle)
    layout.addLayout(_build_toolbar(root))

    metrics = qtwidgets.QHBoxLayout()
    metrics.setSpacing(10)
    metrics.addWidget(make_metric_card("Total", "250 GB", "Account quota", parent=root), 1)
    metrics.addWidget(make_metric_card("Used", "183 GB", "73.2% consumed", parent=root), 1)
    metrics.addWidget(make_metric_card("Free", "67 GB", "Available now", parent=root), 1)
    metrics.addWidget(make_metric_card("Files", "1,248", "Paged result set", parent=root), 1)
    layout.addLayout(metrics)

    layout.addWidget(_build_filters(root))
    layout.addWidget(_file_cards(root), 1)

    apply_fade_in(root)
    return root

