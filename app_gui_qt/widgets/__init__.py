"""Reusable GUI widgets package."""

from app_gui_qt.widgets.animation import apply_fade_in
from app_gui_qt.widgets.cards import make_badge, make_metric_card, make_panel
from app_gui_qt.widgets.stub_actions import connect_stub_action, make_stub_handler

__all__ = [
    "apply_fade_in",
    "connect_stub_action",
    "make_badge",
    "make_metric_card",
    "make_panel",
    "make_stub_handler",
]

