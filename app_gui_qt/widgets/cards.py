from __future__ import annotations

from app_gui_qt.qt_compat import require_qt


def make_panel(parent=None, object_name: str = "panel"):
    _qtcore, qtwidgets = require_qt()
    frame = qtwidgets.QFrame(parent)
    frame.setObjectName(object_name)
    return frame


def make_metric_card(title: str, value: str, hint: str = "", parent=None):
    _qtcore, qtwidgets = require_qt()
    card = make_panel(parent=parent, object_name="card")
    layout = qtwidgets.QVBoxLayout(card)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(4)

    label = qtwidgets.QLabel(title)
    label.setObjectName("metricLabel")
    layout.addWidget(label)

    value_label = qtwidgets.QLabel(value)
    value_label.setObjectName("metricValue")
    layout.addWidget(value_label)

    hint_label = qtwidgets.QLabel(hint)
    hint_label.setObjectName("subtitle")
    layout.addWidget(hint_label)
    return card


def make_badge(text: str, badge_kind: str = "ok", parent=None):
    _qtcore, qtwidgets = require_qt()
    label = qtwidgets.QLabel(text, parent)
    if badge_kind == "warn":
        label.setObjectName("badgeWarn")
    elif badge_kind == "danger":
        label.setObjectName("badgeDanger")
    else:
        label.setObjectName("badgeOk")
    return label

