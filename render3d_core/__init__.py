"""3D geometry and renderer support package."""

from render3d_core.backend import GEOM_BACKEND_ENV, get_geometry_backend, resolve_geometry_backend
from render3d_core.cache import BuildCache, CacheKey, compute_file_signature, make_cache_key
from render3d_core.contours import build_contour_stack
from render3d_core.geometry_v2 import build_geometry_v2
from render3d_core.invariants import GeometryInvariantSnapshot, build_invariant_snapshot
from render3d_core.pipeline import GeometryBuildResult, build_geometry_pipeline
from render3d_core.perf import BuildMetrics, GpuMetrics
from render3d_core.types import LayerRange, PwmbContourGeometry, PwmbContourStack

__all__ = [
    "BuildCache",
    "BuildMetrics",
    "CacheKey",
    "GEOM_BACKEND_ENV",
    "GeometryBuildResult",
    "GpuMetrics",
    "GeometryInvariantSnapshot",
    "LayerRange",
    "PwmbContourGeometry",
    "PwmbContourStack",
    "build_invariant_snapshot",
    "build_contour_stack",
    "build_geometry_pipeline",
    "build_geometry_v2",
    "compute_file_signature",
    "get_geometry_backend",
    "make_cache_key",
    "resolve_geometry_backend",
]
