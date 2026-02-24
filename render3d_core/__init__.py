"""3D geometry and renderer support package."""

from render3d_core.cache import BuildCache, CacheKey, compute_file_signature, make_cache_key
from render3d_core.contours import build_contour_stack
from render3d_core.geometry_v2 import build_geometry_v2
from render3d_core.perf import BuildMetrics, GpuMetrics
from render3d_core.types import LayerRange, PwmbContourGeometry, PwmbContourStack

__all__ = [
    "BuildCache",
    "BuildMetrics",
    "CacheKey",
    "GpuMetrics",
    "LayerRange",
    "PwmbContourGeometry",
    "PwmbContourStack",
    "build_contour_stack",
    "build_geometry_v2",
    "compute_file_signature",
    "make_cache_key",
]
