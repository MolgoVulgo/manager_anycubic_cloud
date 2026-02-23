from __future__ import annotations

from accloud_core.models import Printer
from app_gui_qt.tabs.printer_tab import _is_printing


def _printer(**kwargs) -> Printer:
    defaults: dict[str, object] = {
        "printer_id": "p1",
        "name": "P1",
        "online": True,
    }
    defaults.update(kwargs)
    return Printer(**defaults)  # type: ignore[arg-type]


def test_is_printing_uses_state_priority_over_stale_is_printing_flag() -> None:
    printer = _printer(state="finished", is_printing=2, print_status=2)
    assert _is_printing(printer) is False


def test_is_printing_true_when_state_printing() -> None:
    printer = _printer(state="printing", is_printing=0, print_status=0)
    assert _is_printing(printer) is True


def test_is_printing_uses_print_status_when_state_missing() -> None:
    active = _printer(state=None, print_status=1, is_printing=0)
    done = _printer(state=None, print_status=2, is_printing=2)
    assert _is_printing(active) is True
    assert _is_printing(done) is False
