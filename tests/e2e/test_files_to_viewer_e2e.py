from __future__ import annotations

import logging
import os
from pathlib import Path
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_ = pytest.importorskip("PySide6")
from PySide6 import QtCore, QtWidgets  # type: ignore

from accloud_core.config import AppConfig
from accloud_core.models import FileItem
from app_gui_qt import app as app_mod
from app_gui_qt.dialogs import pwmb3d_dialog as dialog_mod
from app_gui_qt.tabs.files_tab import FilesTab
from render3d_core.perf import BuildMetrics
from render3d_core.types import LayerRange, PwmbContourGeometry


class _FakeApi:
    pass


class _FakeViewport(QtWidgets.QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.last_cutoff = 0
        self.last_stride = 1

    def set_geometry(self, geometry: PwmbContourGeometry, *, layer_ids: list[int]) -> None:
        _ = (geometry, layer_ids)

    def set_layer_cutoff(self, value: int) -> None:
        self.last_cutoff = int(value)

    def set_stride_z(self, value: int) -> None:
        self.last_stride = int(value)

    def set_force_full_quality(self, enabled: bool) -> None:
        _ = enabled

    def set_contour_only(self, enabled: bool) -> None:
        _ = enabled

    def reset_camera(self) -> None:
        return None

    def renderer_error_message(self) -> str | None:
        return None


def _app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _wait_until(predicate, *, timeout_s: float = 6.0) -> None:
    app = _app()
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for UI condition")


def _button(widget: QtWidgets.QWidget, text: str) -> QtWidgets.QPushButton:
    for button in widget.findChildren(QtWidgets.QPushButton):
        if button.text().strip() == text:
            return button
    raise AssertionError(f"Button not found: {text}")


def _slider(dialog: QtWidgets.QDialog, *, minimum: int) -> QtWidgets.QSlider:
    for item in dialog.findChildren(QtWidgets.QSlider):
        if int(item.minimum()) == int(minimum):
            return item
    raise AssertionError(f"Slider with minimum={minimum} not found")


def _make_result(*, source_path: str, phase: str, include_fill: bool) -> dialog_mod._BuildJobResult:
    geometry = PwmbContourGeometry(
        triangle_vertices=[
            (0.0, 0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
        ],
        line_vertices=[(0.0, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0)],
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


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        session_path=tmp_path / "session.json",
        cache_dir=tmp_path / "cache",
        app_log_path=tmp_path / "app.log",
        http_log_path=tmp_path / "http.log",
        render3d_log_path=tmp_path / "render3d.log",
        fault_log_path=tmp_path / "fault.log",
    )


def test_files_to_viewer_rebuild_cutoff_stride_flow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _ = _app()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    sample = tmp_path / "from_files_tab.pwmb"
    sample.write_bytes(b"pwmb")

    viewports: list[_FakeViewport] = []
    build_calls: list[tuple[str, bool]] = []
    opened_dialog: dict[str, QtWidgets.QDialog] = {}

    def _fake_make_viewport(parent=None):
        viewport = _FakeViewport(parent=parent)
        viewports.append(viewport)
        return viewport, _FakeViewport

    def _fake_build_job(*, source_path: str, phase: str, include_fill: bool, **_kwargs):
        build_calls.append((phase, include_fill))
        return _make_result(source_path=source_path, phase=phase, include_fill=include_fill)

    def _fake_open_viewer_dialog(owner, **_kwargs) -> None:
        dialog = dialog_mod.build_pwmb3d_dialog(owner, pwmb_path=sample, file_label="demo.pwmb")
        opened_dialog["dialog"] = dialog
        dialog.show()

    monkeypatch.setattr(dialog_mod, "_make_viewport", _fake_make_viewport)
    monkeypatch.setattr(dialog_mod, "_build_geometry_job", _fake_build_job)
    monkeypatch.setattr(app_mod, "_open_viewer_dialog", _fake_open_viewer_dialog)

    callback = app_mod._make_open_viewer_callback(
        owner=None,
        api=_FakeApi(),  # type: ignore[arg-type]
        config=_config(tmp_path),
        logger=logging.getLogger("tests.e2e.viewer"),
    )
    tab = FilesTab(on_open_viewer=callback)
    tab.render_files([FileItem(file_id="42", name="demo.pwmb", size_bytes=123)])
    tab.root.show()

    try:
        open_btn = _button(tab.root, "Open 3D Viewer")
        open_btn.click()

        _wait_until(lambda: "dialog" in opened_dialog)
        dialog = opened_dialog["dialog"]
        _wait_until(lambda: any(label.text().startswith("Loaded ") for label in dialog.findChildren(QtWidgets.QLabel)))
        assert build_calls[:2] == [("contours", False), ("fill", True)]

        rebuild_btn = _button(dialog, "Rebuild preview")
        rebuild_btn.click()
        _wait_until(lambda: len(build_calls) >= 4)
        assert build_calls[2:4] == [("contours", False), ("fill", True)]

        cutoff_slider = _slider(dialog, minimum=0)
        stride_slider = _slider(dialog, minimum=1)
        cutoff_slider.setValue(1)
        stride_slider.setValue(3)
        _app().processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)
        assert len(viewports) == 1
        assert viewports[0].last_cutoff == 1
        assert viewports[0].last_stride == 3
    finally:
        if "dialog" in opened_dialog:
            opened_dialog["dialog"].reject()
            _app().processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)
        tab.root.close()
        _app().processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)
