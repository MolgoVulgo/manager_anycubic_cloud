from __future__ import annotations

import os
from pathlib import Path
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_ = pytest.importorskip("PySide6")
from PySide6 import QtCore, QtWidgets  # type: ignore

from app_gui_qt.dialogs import pwmb3d_dialog as dialog_mod
from render3d_core.perf import BuildMetrics
from render3d_core.types import LayerRange, PwmbContourGeometry


def _app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _wait_until(predicate, *, timeout_s: float = 5.0) -> None:
    app = _app()
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for UI condition")


def _button(dialog: QtWidgets.QDialog, text: str) -> QtWidgets.QPushButton:
    for button in dialog.findChildren(QtWidgets.QPushButton):
        if button.text().strip() == text:
            return button
    raise AssertionError(f"Button not found: {text}")


def _slider(dialog: QtWidgets.QDialog, *, minimum: int) -> QtWidgets.QSlider:
    for item in dialog.findChildren(QtWidgets.QSlider):
        if int(item.minimum()) == int(minimum):
            return item
    raise AssertionError(f"Slider with minimum={minimum} not found")


def _combo_with_items(dialog: QtWidgets.QDialog, *, count: int) -> QtWidgets.QComboBox:
    for item in dialog.findChildren(QtWidgets.QComboBox):
        if int(item.count()) == int(count):
            return item
    raise AssertionError(f"ComboBox with {count} items not found")


def _first_label_containing(dialog: QtWidgets.QDialog, needle: str) -> QtWidgets.QLabel:
    for label in dialog.findChildren(QtWidgets.QLabel):
        if needle in label.text():
            return label
    raise AssertionError(f"Label containing '{needle}' not found")


def _make_result(*, source_path: str, phase: str, include_fill: bool) -> dialog_mod._BuildJobResult:
    geometry = PwmbContourGeometry(
        triangle_vertices=[
            (0.0, 0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
        ],
        line_vertices=[
            (0.0, 0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0, 0.0),
        ],
        point_vertices=[(0.0, 0.0, 0.0, 0.0)],
        tri_range={0: LayerRange(start=0, count=3), 1: LayerRange(start=0, count=0), 2: LayerRange(start=0, count=0)},
        line_range={0: LayerRange(start=0, count=2), 1: LayerRange(start=0, count=0), 2: LayerRange(start=0, count=0)},
        point_range={0: LayerRange(start=0, count=1), 1: LayerRange(start=0, count=0), 2: LayerRange(start=0, count=0)},
    )
    return dialog_mod._BuildJobResult(
        geometry=geometry,
        built_layer_ids=[0, 1, 2],
        document_layer_count=3,
        source_path=source_path,
        phase=phase,
        include_fill=include_fill,
        backend_name="python",
        xy_stride=1,
        z_stride=1,
        metrics=BuildMetrics(),
        contour_cache_hit=False,
        geometry_cache_hit=False,
    )


class _FakeViewport(QtWidgets.QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.geometry_calls: list[tuple[PwmbContourGeometry, list[int]]] = []
        self.last_cutoff = 0
        self.last_stride = 1
        self.force_full = False
        self.contour_only = False
        self.palette_label = ""
        self._renderer_error: str | None = None

    def set_geometry(self, geometry: PwmbContourGeometry, *, layer_ids: list[int]) -> None:
        self.geometry_calls.append((geometry, list(layer_ids)))

    def set_layer_cutoff(self, value: int) -> None:
        self.last_cutoff = int(value)

    def set_stride_z(self, value: int) -> None:
        self.last_stride = int(value)

    def set_force_full_quality(self, enabled: bool) -> None:
        self.force_full = bool(enabled)

    def set_contour_only(self, enabled: bool) -> None:
        self.contour_only = bool(enabled)

    def set_render_palette(self, label: str) -> None:
        self.palette_label = str(label)

    def reset_camera(self) -> None:
        return None

    def renderer_error_message(self) -> str | None:
        return self._renderer_error


def test_viewer_dialog_build_async_updates_ranges_and_controls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _ = _app()
    sample = tmp_path / "sample.pwmb"
    sample.write_bytes(b"pwmb")

    viewports: list[_FakeViewport] = []
    calls: list[tuple[str, bool, float]] = []

    def _fake_make_viewport(parent=None):
        viewport = _FakeViewport(parent=parent)
        viewports.append(viewport)
        return viewport, _FakeViewport

    def _fake_build_job(*, source_path: str, phase: str, include_fill: bool, **_kwargs):
        calls.append((phase, include_fill, float(_kwargs.get("quality_ratio", 0.0))))
        return _make_result(source_path=source_path, phase=phase, include_fill=include_fill)

    monkeypatch.setattr(dialog_mod, "_make_viewport", _fake_make_viewport)
    monkeypatch.setattr(dialog_mod, "_build_geometry_job", _fake_build_job)

    dialog = dialog_mod.build_pwmb3d_dialog(None, pwmb_path=sample)
    dialog.show()
    try:
        _wait_until(lambda: any(label.text().startswith("Loaded ") for label in dialog.findChildren(QtWidgets.QLabel)))
        assert calls[0][0:2] == ("contours", False)
        assert calls[1][0:2] == ("fill", True)
        assert calls[0][2] == pytest.approx(0.66, rel=1e-6)
        assert calls[1][2] == pytest.approx(0.66, rel=1e-6)
        assert len(viewports) == 1
        assert len(viewports[0].geometry_calls) == 2

        cutoff_slider = _slider(dialog, minimum=0)
        quality_combo = _combo_with_items(dialog, count=len(dialog_mod._QUALITY_PRESETS))
        palette_combo = _combo_with_items(dialog, count=len(dialog_mod._RENDER_PALETTES))
        assert cutoff_slider.maximum() == 2
        assert cutoff_slider.value() == 2

        cutoff_slider.setValue(1)
        quality_combo.setCurrentIndex(2)
        palette_combo.setCurrentIndex(2)
        _app().processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)
        assert viewports[0].last_cutoff == 1
        assert viewports[0].palette_label == palette_combo.currentText()
        assert _first_label_containing(dialog, "L1 / 2").text() == "L1 / 2"

        rebuild_btn = _button(dialog, "Rebuild preview")
        rebuild_btn.click()
        _wait_until(lambda: len(calls) >= 4)
        assert calls[2][0:2] == ("contours", False)
        assert calls[3][0:2] == ("fill", True)
        assert calls[2][2] == pytest.approx(0.33, rel=1e-6)
        assert calls[3][2] == pytest.approx(0.33, rel=1e-6)
    finally:
        dialog.reject()
        _app().processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)


def test_viewer_dialog_parse_error_enables_retry_and_retry_succeeds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _ = _app()
    sample = tmp_path / "sample_retry.pwmb"
    sample.write_bytes(b"pwmb")

    calls = {"count": 0}

    def _fake_make_viewport(parent=None):
        return _FakeViewport(parent=parent), _FakeViewport

    def _fake_build_job(*, source_path: str, phase: str, include_fill: bool, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise ValueError("Invalid PWMB signature")
        return _make_result(source_path=source_path, phase=phase, include_fill=include_fill)

    monkeypatch.setattr(dialog_mod, "_make_viewport", _fake_make_viewport)
    monkeypatch.setattr(dialog_mod, "_build_geometry_job", _fake_build_job)

    dialog = dialog_mod.build_pwmb3d_dialog(None, pwmb_path=sample)
    dialog.show()
    try:
        retry_btn = _button(dialog, "Retry last build")
        _wait_until(lambda: retry_btn.isEnabled())
        parse_error = _first_label_containing(dialog, "PWMB parse/open error")
        assert "Retry last build" in parse_error.text()

        retry_btn.click()
        _wait_until(lambda: any(label.text().startswith("Loaded ") for label in dialog.findChildren(QtWidgets.QLabel)))
        assert calls["count"] >= 3
        assert retry_btn.isEnabled() is False
    finally:
        dialog.reject()
        _app().processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)


def test_viewer_dialog_renderer_failure_surfaces_retry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _ = _app()
    sample = tmp_path / "sample_gl_fail.pwmb"
    sample.write_bytes(b"pwmb")

    class _FailOnceViewport(_FakeViewport):
        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self._should_fail = True

        def set_geometry(self, geometry: PwmbContourGeometry, *, layer_ids: list[int]) -> None:
            super().set_geometry(geometry, layer_ids=layer_ids)
            if self._should_fail:
                self._renderer_error = "mock context lost"
                self._should_fail = False

    def _fake_make_viewport(parent=None):
        return _FailOnceViewport(parent=parent), _FailOnceViewport

    def _fake_build_job(*, source_path: str, phase: str, include_fill: bool, **_kwargs):
        return _make_result(source_path=source_path, phase=phase, include_fill=include_fill)

    monkeypatch.setattr(dialog_mod, "_make_viewport", _fake_make_viewport)
    monkeypatch.setattr(dialog_mod, "_build_geometry_job", _fake_build_job)

    dialog = dialog_mod.build_pwmb3d_dialog(None, pwmb_path=sample)
    dialog.show()
    try:
        retry_btn = _button(dialog, "Retry last build")
        _wait_until(lambda: retry_btn.isEnabled())
        gl_error = _first_label_containing(dialog, "OpenGL renderer error")
        assert "mock context lost" in gl_error.text()
    finally:
        dialog.reject()
        _app().processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)
