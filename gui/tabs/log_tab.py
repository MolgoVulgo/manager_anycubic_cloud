from __future__ import annotations

from gui.qt_compat import require_qt
from gui.widgets import apply_fade_in, connect_stub_action, make_metric_card, make_panel


_SAMPLE_LOGS = """\
2026-02-21 16:42:13 INFO  gui.app        GUI started in phase-2 design mode
2026-02-21 16:42:14 INFO  accloud.http   GET /files?page=1 status=200 elapsed=248ms
2026-02-21 16:42:14 WARN  pwmb.decode    layer=17 fallback=threshold mode=index_strict
2026-02-21 16:42:15 INFO  pwmb3d.build   stage=contours percent=42 layers=88/210
2026-02-21 16:42:15 INFO  pwmb3d.draw    mode=fill visible_layers=102 draw_ms=4.18
2026-02-21 16:42:16 ERROR accloud.http   POST /print/orders status=503 retry=1 delay_s=0.50
"""


def build_log_tab(parent=None):
    _qtcore, qtwidgets = require_qt()
    root = qtwidgets.QWidget(parent)
    root.setObjectName("tabRoot")
    layout = qtwidgets.QVBoxLayout(root)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(14)

    title = qtwidgets.QLabel("Runtime Logs")
    title.setObjectName("title")
    subtitle = qtwidgets.QLabel("Design shell for log viewer. Tail/poll/rotation will be implemented in phase 5.")
    subtitle.setObjectName("subtitle")
    layout.addWidget(title)
    layout.addWidget(subtitle)

    top_row = qtwidgets.QHBoxLayout()
    for text in ["Reload view", "Pause stream", "Export safe snippet"]:
        button = qtwidgets.QPushButton(text)
        connect_stub_action(button, text)
        top_row.addWidget(button)
    top_row.addStretch(1)
    layout.addLayout(top_row)

    metrics = qtwidgets.QHBoxLayout()
    metrics.addWidget(make_metric_card("Current level", "INFO", "UI filter only", parent=root), 1)
    metrics.addWidget(make_metric_card("HTTP lines", "4,122", "demo counter", parent=root), 1)
    metrics.addWidget(make_metric_card("Errors", "03", "last 60 min", parent=root), 1)
    metrics.addWidget(make_metric_card("Log file", "accloud_http.log", "tail preview", parent=root), 1)
    layout.addLayout(metrics)

    toolbar = make_panel(parent=root, object_name="panel")
    toolbar_layout = qtwidgets.QHBoxLayout(toolbar)
    toolbar_layout.setContentsMargins(12, 10, 12, 10)
    toolbar_layout.setSpacing(10)
    layout.addWidget(toolbar)

    level = qtwidgets.QComboBox()
    level.addItems(["DEBUG+", "INFO+", "WARNING+", "ERROR+"])
    toolbar_layout.addWidget(level, 1)

    module = qtwidgets.QComboBox()
    module.addItems(["All modules", "accloud.http", "pwmb.decode", "pwmb3d.draw", "gui.app"])
    toolbar_layout.addWidget(module, 1)

    query = qtwidgets.QLineEdit()
    query.setPlaceholderText("Filter by text, request id, layer index...")
    toolbar_layout.addWidget(query, 3)

    clear_btn = qtwidgets.QPushButton("Clear")
    connect_stub_action(clear_btn, "Clear log viewport")
    toolbar_layout.addWidget(clear_btn)

    panel = make_panel(parent=root, object_name="cardAlt")
    panel_layout = qtwidgets.QVBoxLayout(panel)
    panel_layout.setContentsMargins(10, 10, 10, 10)
    panel_layout.setSpacing(8)

    log_view = qtwidgets.QPlainTextEdit()
    log_view.setReadOnly(True)
    log_view.setObjectName("monoBlock")
    log_view.setPlainText(_SAMPLE_LOGS)
    panel_layout.addWidget(log_view, 1)

    tail_info = qtwidgets.QLabel(
        "Tail mode: ON (design preview). Poll interval and rotation handling will be wired in phase 5."
    )
    tail_info.setObjectName("subtitle")
    panel_layout.addWidget(tail_info)

    layout.addWidget(panel, 1)
    apply_fade_in(root)
    return root

