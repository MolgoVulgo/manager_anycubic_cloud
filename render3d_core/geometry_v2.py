from __future__ import annotations

from render3d_core.types import PwmbContourGeometry, PwmbContourStack


def build_geometry_v2(
    stack: PwmbContourStack,
    *,
    max_layers: int | None = None,
    max_vertices: int | None = None,
    max_xy_stride: int = 1,
) -> PwmbContourGeometry:
    _ = (stack, max_layers, max_vertices, max_xy_stride)
    raise NotImplementedError("Phase 1 skeleton: implement in phase 3")

