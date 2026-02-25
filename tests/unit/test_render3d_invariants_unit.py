from __future__ import annotations

import pytest

from render3d_core.geometry_v2 import build_geometry_v2
from render3d_core.invariants import (
    build_invariant_snapshot,
    contour_area_mm2,
    contour_bbox,
    degenerate_triangle_count,
    mesh_area_mm2,
    mesh_bbox,
)
from render3d_core.types import LayerLoops, PwmbContourGeometry, PwmbContourStack


def test_contour_area_and_bbox() -> None:
    stack = PwmbContourStack(
        pitch_x_mm=0.1,
        pitch_y_mm=0.1,
        pitch_z_mm=0.05,
        layers={
            0: LayerLoops(
                outer=[[(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]],
                holes=[[(0.5, 0.5), (1.5, 0.5), (1.5, 1.5), (0.5, 1.5)]],
            )
        },
    )
    assert contour_area_mm2(stack) == pytest.approx(3.0, rel=1e-6)
    assert contour_bbox(stack) == (0.0, 0.0, 2.0, 2.0)


def test_mesh_area_bbox_and_degenerate_triangle_count() -> None:
    geometry = PwmbContourGeometry(
        triangle_vertices=[
            (0.0, 0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 0.0, 1.0),
            (0.0, 0.0, 0.0, 1.0),
            (0.0, 0.0, 0.0, 1.0),
        ],
        line_vertices=[(2.0, 2.0, 3.0, 0.0)],
        point_vertices=[(-1.0, -2.0, -3.0, 0.0)],
    )
    assert mesh_area_mm2(geometry) == pytest.approx(0.5, rel=1e-6)
    assert degenerate_triangle_count(geometry) == 1
    assert mesh_bbox(geometry) == (-1.0, -2.0, -3.0, 2.0, 2.0, 3.0)


def test_invariant_snapshot_matches_simple_square_mesh() -> None:
    stack = PwmbContourStack(
        pitch_x_mm=0.1,
        pitch_y_mm=0.1,
        pitch_z_mm=0.1,
        layers={
            0: LayerLoops(
                outer=[[(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]],
                holes=[],
            )
        },
    )
    geometry = build_geometry_v2(stack)
    snapshot = build_invariant_snapshot(stack, geometry)
    assert snapshot.contour_area_mm2 == pytest.approx(4.0, rel=1e-6)
    assert snapshot.mesh_area_mm2 == pytest.approx(4.0, rel=1e-6)
    assert snapshot.degenerate_triangles == 0
    assert snapshot.triangle_count == 2
