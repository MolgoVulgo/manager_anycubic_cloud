from __future__ import annotations

import pytest

pwmb_geom = pytest.importorskip("pwmb_geom")

from render3d_core.invariants import build_invariant_snapshot
from render3d_core.types import LayerLoops, PwmbContourStack


def _signed_area(loop: list[tuple[float, float]]) -> float:
    area = 0.0
    for idx, (x1, y1) in enumerate(loop):
        x2, y2 = loop[(idx + 1) % len(loop)]
        area += (x1 * y2) - (x2 * y1)
    return 0.5 * area


def _triangle_area(tri: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]) -> float:
    a, b, c = tri
    return 0.5 * ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def test_native_triangulation_matches_polygon_area_and_has_no_degenerate_triangles() -> None:
    outer = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]
    holes = [[(1.0, 1.0), (1.0, 3.0), (3.0, 3.0), (3.0, 1.0)]]
    triangles = pwmb_geom._triangulate_native_polygon_with_holes(outer, holes)

    assert triangles
    expected_area = abs(_signed_area(outer)) - abs(_signed_area(holes[0]))
    filled_area = sum(abs(_triangle_area(tri)) for tri in triangles)
    assert filled_area == pytest.approx(expected_area, rel=1e-6)
    assert all(abs(_triangle_area(tri)) > 1e-12 for tri in triangles)


def test_native_triangulation_non_axis_aligned_holes_preserves_area() -> None:
    outer = [
        (-3.0, 0.0),
        (-1.0, -2.5),
        (2.5, -2.0),
        (4.5, 0.8),
        (3.8, 3.5),
        (1.2, 4.8),
        (-2.4, 3.7),
    ]
    holes = [
        [(0.2, -0.9), (1.4, -0.2), (0.9, 1.0), (-0.1, 0.2)],
        [(1.8, 1.1), (2.9, 1.7), (2.3, 2.8), (1.3, 2.1)],
    ]
    triangles = pwmb_geom._triangulate_native_polygon_with_holes(outer, holes)

    assert triangles
    expected_area = abs(_signed_area(outer)) - sum(abs(_signed_area(hole)) for hole in holes)
    filled_area = sum(abs(_triangle_area(tri)) for tri in triangles)
    assert filled_area == pytest.approx(expected_area, rel=1e-4)
    assert all(abs(_triangle_area(tri)) > 1e-12 for tri in triangles)


def test_build_geometry_native_triangulation_matches_python_triangulation(monkeypatch: pytest.MonkeyPatch) -> None:
    stack = PwmbContourStack(
        pitch_x_mm=0.1,
        pitch_y_mm=0.1,
        pitch_z_mm=0.05,
        layers={
            0: LayerLoops(
                outer=[[(-2.0, -2.0), (2.0, -2.0), (2.0, 2.0), (-2.0, 2.0)]],
                holes=[[(-1.0, -1.0), (-1.0, 1.0), (1.0, 1.0), (1.0, -1.0)]],
            )
        },
    )

    monkeypatch.setenv("GEOM_CPP_TRIANGULATION_IMPL", "native")
    native_geometry = pwmb_geom.build_geometry(
        contour_stack=stack,
        max_layers=None,
        max_vertices=None,
        max_xy_stride=1,
        include_fill=True,
        metrics=None,
    )
    monkeypatch.setenv("GEOM_CPP_TRIANGULATION_IMPL", "python")
    python_geometry = pwmb_geom.build_geometry(
        contour_stack=stack,
        max_layers=None,
        max_vertices=None,
        max_xy_stride=1,
        include_fill=True,
        metrics=None,
    )

    native_inv = build_invariant_snapshot(stack, native_geometry)
    python_inv = build_invariant_snapshot(stack, python_geometry)
    assert native_inv.mesh_area_mm2 == pytest.approx(python_inv.mesh_area_mm2, rel=1e-6)
    assert native_inv.degenerate_triangles == 0
    assert python_inv.degenerate_triangles == 0


def test_native_indexed_triangulation_payload_is_contiguous_when_available() -> None:
    if not hasattr(pwmb_geom, "_triangulate_native_polygon_with_holes_indexed"):
        pytest.skip("indexed triangulation wrapper unavailable")
    outer = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]
    holes = [[(1.0, 1.0), (1.0, 3.0), (3.0, 3.0), (3.0, 1.0)]]
    payload = pwmb_geom._triangulate_native_polygon_with_holes_indexed(outer, holes)

    assert isinstance(payload, dict)
    vertices = payload.get("vertices")
    indices = payload.get("indices")
    assert vertices is not None
    assert indices is not None
    assert vertices.dtype.name == "float32"
    assert indices.dtype.name == "uint32"
    assert vertices.flags["C_CONTIGUOUS"]
    assert indices.flags["C_CONTIGUOUS"]
