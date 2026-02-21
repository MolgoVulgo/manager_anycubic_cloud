from __future__ import annotations


def require_qt():
    try:
        from PySide6 import QtCore, QtWidgets  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PySide6 is required to run the GUI. Install dependencies from pyproject.toml."
        ) from exc
    return QtCore, QtWidgets

