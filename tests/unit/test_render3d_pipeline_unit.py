from __future__ import annotations

from pathlib import Path

from pwmb_core.types import HeaderInfo, LayerDef, MachineInfo, PwmbDocument
from render3d_core.cache import BuildCache, make_cache_key
from render3d_core.pipeline import build_geometry_pipeline
from render3d_core.types import LayerLoops, PwmbContourGeometry, PwmbContourStack


def _document(path: Path, *, layers: int = 1) -> PwmbDocument:
    return PwmbDocument(
        path=path,
        version=516,
        file_size=path.stat().st_size,
        header=HeaderInfo(
            pixel_size_um=50.0,
            layer_height_mm=0.05,
            anti_aliasing=1,
            resolution_x=8,
            resolution_y=8,
        ),
        machine=MachineInfo(machine_name="M", layer_image_format="pw0Img"),
        layers=[LayerDef(index=index, data_address=0, data_length=0) for index in range(max(1, int(layers)))],
        lut=[0, 64, 128, 255],
    )


def _stack() -> PwmbContourStack:
    return PwmbContourStack(
        pitch_x_mm=0.05,
        pitch_y_mm=0.05,
        pitch_z_mm=0.05,
        layers={0: LayerLoops(outer=[[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]], holes=[])},
    )


def _geometry() -> PwmbContourGeometry:
    return PwmbContourGeometry(
        triangle_vertices=[
            (0.0, 0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
        ]
    )


class _FakeBackend:
    name = "fake"

    def __init__(self, contour_stack: PwmbContourStack, geometry: PwmbContourGeometry) -> None:
        self._contour_stack = contour_stack
        self._geometry = geometry
        self.calls: list[str] = []
        self.contour_document_layer_counts: list[int] = []
        self.include_fill_values: list[bool] = []

    def build_contours(
        self,
        _document: PwmbDocument,
        *,
        threshold: int,
        binarization_mode: str,
        xy_stride: int,
        metrics=None,
    ) -> PwmbContourStack:
        _ = (threshold, binarization_mode, xy_stride, metrics)
        self.calls.append("contours")
        self.contour_document_layer_counts.append(len(_document.layers))
        return self._contour_stack

    def build_geometry(
        self,
        contour_stack: PwmbContourStack,
        *,
        max_layers: int | None,
        max_vertices: int | None,
        max_xy_stride: int,
        include_fill: bool = True,
        metrics=None,
    ) -> PwmbContourGeometry:
        _ = (max_layers, max_vertices, max_xy_stride, metrics)
        assert contour_stack is self._contour_stack
        self.calls.append("geometry")
        self.include_fill_values.append(bool(include_fill))
        return self._geometry


def test_build_geometry_pipeline_without_cache_uses_backend(tmp_path: Path) -> None:
    path = tmp_path / "sample.pwmb"
    path.write_bytes(b"pwmb")
    document = _document(path)
    stack = _stack()
    geometry = _geometry()
    backend = _FakeBackend(stack, geometry)
    stages: list[str] = []

    result = build_geometry_pipeline(
        document,
        threshold=1,
        bin_mode="index_strict",
        xy_stride=2,
        max_xy_stride=1,
        backend=backend,
        cache=None,
        stage_cb=stages.append,
    )

    assert backend.calls == ["contours", "geometry"]
    assert backend.include_fill_values == [True]
    assert result.contour_stack is stack
    assert result.geometry is geometry
    assert result.contour_cache_hit is False
    assert result.geometry_cache_hit is False
    assert stages == ["decode", "contours", "geometry"]


def test_build_geometry_pipeline_uses_cache_hits(tmp_path: Path) -> None:
    path = tmp_path / "sample.pwmb"
    path.write_bytes(b"pwmb")
    document = _document(path)
    stack = _stack()
    geometry = _geometry()
    backend = _FakeBackend(stack, geometry)
    cache = BuildCache()
    signature = "sig"
    contour_key = make_cache_key(
        document,
        threshold=1,
        bin_mode="index_strict",
        xy_stride=1,
        z_stride=1,
        simplify_epsilon=0.0,
        max_layers=None,
        max_vertices=None,
        render_mode="contours",
        file_signature=signature,
    )
    geometry_key = make_cache_key(
        document,
        threshold=1,
        bin_mode="index_strict",
        xy_stride=1,
        z_stride=1,
        simplify_epsilon=0.0,
        max_layers=None,
        max_vertices=None,
        render_mode="fill",
        file_signature=signature,
    )
    cache.set_contours(contour_key, stack)
    cache.set_geometry(geometry_key, geometry)
    stages: list[str] = []

    result = build_geometry_pipeline(
        document,
        threshold=1,
        bin_mode="index_strict",
        xy_stride=1,
        max_xy_stride=1,
        file_signature=signature,
        backend=backend,
        cache=cache,
        stage_cb=stages.append,
    )

    assert backend.calls == []
    assert result.contour_cache_hit is True
    assert result.geometry_cache_hit is True
    assert result.contour_stack is stack
    assert result.geometry is geometry
    assert stages == [
        "cache_contours_lookup",
        "cache_contours_hit",
        "cache_geometry_lookup",
        "cache_geometry_hit",
    ]


def test_build_geometry_pipeline_uses_contour_cache_then_builds_geometry(tmp_path: Path) -> None:
    path = tmp_path / "sample.pwmb"
    path.write_bytes(b"pwmb")
    document = _document(path)
    stack = _stack()
    geometry = _geometry()
    backend = _FakeBackend(stack, geometry)
    cache = BuildCache()
    signature = "sig"
    contour_key = make_cache_key(
        document,
        threshold=1,
        bin_mode="index_strict",
        xy_stride=1,
        z_stride=1,
        simplify_epsilon=0.0,
        max_layers=None,
        max_vertices=None,
        render_mode="contours",
        file_signature=signature,
    )
    cache.set_contours(contour_key, stack)
    stages: list[str] = []

    result = build_geometry_pipeline(
        document,
        threshold=1,
        bin_mode="index_strict",
        xy_stride=1,
        max_xy_stride=1,
        file_signature=signature,
        backend=backend,
        cache=cache,
        stage_cb=stages.append,
    )

    assert backend.calls == ["geometry"]
    assert backend.include_fill_values == [True]
    assert result.contour_cache_hit is True
    assert result.geometry_cache_hit is False
    assert result.contour_stack is stack
    assert result.geometry is geometry
    assert stages == [
        "cache_contours_lookup",
        "cache_contours_hit",
        "cache_geometry_lookup",
        "geometry",
    ]


def test_build_geometry_pipeline_applies_z_stride_before_contours(tmp_path: Path) -> None:
    path = tmp_path / "sample.pwmb"
    path.write_bytes(b"pwmb")
    document = _document(path, layers=7)
    stack = _stack()
    geometry = _geometry()
    backend = _FakeBackend(stack, geometry)

    _ = build_geometry_pipeline(
        document,
        threshold=1,
        bin_mode="index_strict",
        xy_stride=1,
        z_stride=3,
        max_xy_stride=1,
        backend=backend,
        cache=None,
    )

    assert backend.calls == ["contours", "geometry"]
    assert backend.contour_document_layer_counts == [3]


def test_build_geometry_pipeline_contours_only_uses_distinct_geometry_cache_key(tmp_path: Path) -> None:
    path = tmp_path / "sample.pwmb"
    path.write_bytes(b"pwmb")
    document = _document(path)
    stack = _stack()
    geometry = _geometry()
    backend = _FakeBackend(stack, geometry)
    signature = "sig"

    result = build_geometry_pipeline(
        document,
        threshold=1,
        bin_mode="index_strict",
        xy_stride=1,
        include_fill=False,
        max_xy_stride=1,
        file_signature=signature,
        backend=backend,
        cache=None,
    )

    expected_key = make_cache_key(
        document,
        threshold=1,
        bin_mode="index_strict",
        xy_stride=1,
        z_stride=1,
        simplify_epsilon=0.0,
        max_layers=None,
        max_vertices=None,
        render_mode="contours_only",
        file_signature=signature,
    )
    assert result.geometry_key == expected_key
    assert backend.include_fill_values == [False]
