"""3D geometry and renderer support package."""

from render3d_core.cache import BuildCache, CacheKey
from render3d_core.contours import build_contour_stack
from render3d_core.geometry_v2 import build_geometry_v2
from render3d_core.types import LayerRange, PwmbContourGeometry, PwmbContourStack

__all__ = [
    "BuildCache",
    "CacheKey",
    "LayerRange",
    "PwmbContourGeometry",
    "PwmbContourStack",
    "build_contour_stack",
    "build_geometry_v2",
]
