from __future__ import annotations

from gui.qt_compat import require_qt
from gui.widgets import apply_fade_in, connect_stub_action, make_badge, make_metric_card, make_panel


def _build_toolbar(parent=None):
    _qtcore, qtwidgets = require_qt()
    row = qtwidgets.QHBoxLayout()
    row.setSpacing(8)

    refresh_button = qtwidgets.QPushButton("Refresh")
    upload_button = qtwidgets.QPushButton("Upload .pwmb")
    upload_button.setObjectName("primary")

    for widget, label in [
        (refresh_button, "Refresh files"),
        (upload_button, "Upload"),
    ]:
        connect_stub_action(widget, label)
        row.addWidget(widget)

    row.addStretch(1)
    return row


def _make_thumbnail(file_name: str, parent=None):
    _qtcore, qtwidgets = require_qt()
    frame = make_panel(parent=parent, object_name="card")
    frame.setFixedSize(100, 100)
    frame.setStyleSheet(
        frame.styleSheet()
        + """
        QFrame#card {
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 #dfe8d7, stop:0.5 #bfd3bd, stop:1 #93b39f
            );
            border: 1px solid #7f9b85;
            border-radius: 10px;
        }
        QLabel {
            color: #1f3527;
        }
        """
    )
    layout = qtwidgets.QVBoxLayout(frame)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(2)

    ext = file_name.split(".")[-1].upper()
    ext_label = qtwidgets.QLabel(ext)
    ext_label.setAlignment(_qtcore.Qt.AlignmentFlag.AlignCenter)
    ext_label.setStyleSheet("font-size: 22px; font-weight: 700;")

    size_label = qtwidgets.QLabel("100x100")
    size_label.setAlignment(_qtcore.Qt.AlignmentFlag.AlignCenter)
    size_label.setStyleSheet("font-size: 11px;")

    layout.addStretch(1)
    layout.addWidget(ext_label)
    layout.addWidget(size_label)
    layout.addStretch(1)
    return frame


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


def _file_cards(parent=None, on_open_viewer=None):
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
        card_layout = qtwidgets.QHBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(12)

        card_layout.addWidget(_make_thumbnail(file_info["name"], parent=card), 0)

        right = qtwidgets.QWidget(card)
        right_layout = qtwidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        top = qtwidgets.QHBoxLayout()
        name = qtwidgets.QLabel(file_info["name"])
        name.setObjectName("title")
        name.setStyleSheet("font-size: 18px; font-weight: 650;")
        top.addWidget(name, 1)
        top.addWidget(make_badge(file_info["status"][0], file_info["status"][1]))
        right_layout.addLayout(top)

        meta = qtwidgets.QLabel(
            f'Size: {file_info["size"]}   |   Updated: {file_info["updated"]}   |   Machine: {file_info["machine"]}'
        )
        meta.setObjectName("subtitle")
        right_layout.addWidget(meta)

        actions = qtwidgets.QHBoxLayout()
        for label in ["Details", "Print", "Download", "Delete", "Open 3D Viewer"]:
            button = qtwidgets.QPushButton(label)
            if label == "Delete":
                button.setObjectName("danger")
            if label == "Open 3D Viewer" and on_open_viewer is not None:
                button.clicked.connect(on_open_viewer)
            else:
                connect_stub_action(button, f'{label} for {file_info["name"]}')
            actions.addWidget(button)
        actions.addStretch(1)
        right_layout.addLayout(actions)
        card_layout.addWidget(right, 1)

        layout.addWidget(card)

    layout.addStretch(1)
    return wrapper


def build_files_tab(parent=None, on_open_viewer=None):
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
    layout.addWidget(_file_cards(root, on_open_viewer=on_open_viewer), 1)

    apply_fade_in(root)
    return root
