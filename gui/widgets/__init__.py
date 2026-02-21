"""Reusable GUI widgets package."""

from gui.widgets.animation import apply_fade_in
from gui.widgets.cards import make_badge, make_metric_card, make_panel
from gui.widgets.stub_actions import connect_stub_action, make_stub_handler

__all__ = [
    "apply_fade_in",
    "connect_stub_action",
    "make_badge",
    "make_metric_card",
    "make_panel",
    "make_stub_handler",
]

