from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from pwmb_core.types import HeaderInfo, LayerDef, MachineInfo, PwmbDocument
from render3d_core.backend import GEOM_BACKEND_ENV, resolve_geometry_backend
from render3d_core.perf import BuildMetrics
from render3d_core.task_runner import CancellationToken
from render3d_core.types import LayerLoops, PwmbContourGeometry, PwmbContourStack


def _document() -> PwmbDocument:
    return PwmbDocument(
        path=Path("synthetic.pwmb"),
        version=516,
        file_size=0,
        header=HeaderInfo(
            pixel_size_um=50.0,
            layer_height_mm=0.05,
            anti_aliasing=1,
            resolution_x=2,
            resolution_y=2,
        ),
        machine=MachineInfo(machine_name="M", layer_image_format="pw0Img"),
        layers=[LayerDef(index=0, data_address=0, data_length=0)],
    )


def test_resolve_geometry_backend_defaults_to_python_when_cpp_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_name: str):
        raise ModuleNotFoundError("pwmb_geom missing")

    monkeypatch.delenv(GEOM_BACKEND_ENV, raising=False)
    monkeypatch.setattr("render3d_core.backend.importlib.import_module", _raise)
    backend = resolve_geometry_backend()
    assert backend.name == "python"


def test_resolve_geometry_backend_auto_prefers_cpp_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    module = SimpleNamespace(
        build_contours=lambda **_kwargs: PwmbContourStack(pitch_x_mm=0.1, pitch_y_mm=0.1, pitch_z_mm=0.05),
        build_geometry=lambda **_kwargs: PwmbContourGeometry(),
    )
    monkeypatch.delenv(GEOM_BACKEND_ENV, raising=False)
    monkeypatch.setattr("render3d_core.backend.importlib.import_module", lambda _name: module)
    backend = resolve_geometry_backend()
    assert backend.name == "cpp"


def test_resolve_geometry_backend_cpp_falls_back_if_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_name: str):
        raise ModuleNotFoundError("pwmb_geom missing")

    monkeypatch.setattr("render3d_core.backend.importlib.import_module", _raise)
    backend = resolve_geometry_backend(preferred="cpp")
    assert backend.name == "python"


def test_resolve_geometry_backend_cpp_when_module_is_available(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_stack = PwmbContourStack(
        pitch_x_mm=0.1,
        pitch_y_mm=0.1,
        pitch_z_mm=0.05,
        layers={0: LayerLoops(outer=[[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]], holes=[])},
    )
    fake_geometry = PwmbContourGeometry(
        triangle_vertices=[(0.0, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0)],
    )

    module = SimpleNamespace(
        build_contours=lambda **_kwargs: fake_stack,
        build_geometry=lambda **_kwargs: fake_geometry,
    )
    monkeypatch.setattr("render3d_core.backend.importlib.import_module", lambda _name: module)
    backend = resolve_geometry_backend(preferred="cpp")

    assert backend.name == "cpp"
    stack = backend.build_contours(
        _document(),
        threshold=1,
        binarization_mode="index_strict",
        xy_stride=1,
        metrics=BuildMetrics(),
    )
    geometry = backend.build_geometry(
        stack,
        max_layers=None,
        max_vertices=None,
        max_xy_stride=1,
        include_fill=True,
        metrics=BuildMetrics(),
    )
    assert stack is fake_stack
    assert geometry is fake_geometry


def test_cpp_backend_fallback_when_module_lacks_cancel_token(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_stack = PwmbContourStack(pitch_x_mm=0.1, pitch_y_mm=0.1, pitch_z_mm=0.05)
    fake_geometry = PwmbContourGeometry()

    def _build_contours_legacy(*, document, threshold, binarization_mode, xy_stride, metrics):  # type: ignore[no-untyped-def]
        _ = (document, threshold, binarization_mode, xy_stride, metrics)
        return fake_stack

    def _build_geometry_legacy(
        *,
        contour_stack,
        max_layers,
        max_vertices,
        max_xy_stride,
        include_fill,
        metrics,
    ):  # type: ignore[no-untyped-def]
        _ = (contour_stack, max_layers, max_vertices, max_xy_stride, include_fill, metrics)
        return fake_geometry

    module = SimpleNamespace(
        build_contours=_build_contours_legacy,
        build_geometry=_build_geometry_legacy,
    )
    token = CancellationToken()
    monkeypatch.setattr("render3d_core.backend.importlib.import_module", lambda _name: module)
    backend = resolve_geometry_backend(preferred="cpp")

    stack = backend.build_contours(
        _document(),
        threshold=1,
        binarization_mode="index_strict",
        xy_stride=1,
        metrics=BuildMetrics(),
        cancel_token=token,
    )
    geometry = backend.build_geometry(
        stack,
        max_layers=None,
        max_vertices=None,
        max_xy_stride=1,
        include_fill=True,
        metrics=BuildMetrics(),
        cancel_token=token,
    )

    assert stack is fake_stack
    assert geometry is fake_geometry
