from __future__ import annotations

from gui.qt_compat import require_qt


def apply_fade_in(widget, duration_ms: int = 280) -> None:
    qtcore, qtwidgets = require_qt()
    effect = qtwidgets.QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)

    animation = qtcore.QPropertyAnimation(effect, b"opacity", widget)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setDuration(max(120, duration_ms))
    animation.setEasingCurve(qtcore.QEasingCurve.Type.OutCubic)
    animation.start()

    # Keep a reference on the widget to prevent early GC.
    widget._fade_animation = animation  # type: ignore[attr-defined]

