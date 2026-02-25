from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from dataclasses import dataclass

from pwmb_core.types import PwmbDocument
from render3d_core.backend import GeometryBackend, get_geometry_backend
from render3d_core.cache import BuildCache, CacheKey, compute_file_signature, make_cache_key
from render3d_core.perf import BuildMetrics
from render3d_core.types import PwmbContourGeometry, PwmbContourStack


@dataclass(slots=True)
class GeometryBuildResult:
    contour_stack: PwmbContourStack
    geometry: PwmbContourGeometry
    backend_name: str
    file_signature: str
    contour_key: CacheKey
    geometry_key: CacheKey
    contour_cache_hit: bool
    geometry_cache_hit: bool


def build_geometry_pipeline(
    document: PwmbDocument,
    *,
    threshold: int,
    bin_mode: str,
    xy_stride: int,
    max_layers: int | None = None,
    max_vertices: int | None = None,
    max_xy_stride: int = 1,
    z_stride: int = 1,
    include_fill: bool = True,
    simplify_epsilon: float = 0.0,
    file_signature: str | None = None,
    backend: GeometryBackend | None = None,
    cache: BuildCache | None = None,
    metrics: BuildMetrics | None = None,
    stage_cb: Callable[[str], None] | None = None,
) -> GeometryBuildResult:
    selected_backend = backend or get_geometry_backend()
    effective_z_stride = max(1, int(z_stride))
    contour_document = _sample_document_layers(document, z_stride=effective_z_stride)
    signature = file_signature or compute_file_signature(document.path)
    contour_key = make_cache_key(
        document,
        threshold=threshold,
        bin_mode=bin_mode,
        xy_stride=xy_stride,
        z_stride=effective_z_stride,
        simplify_epsilon=simplify_epsilon,
        max_layers=max_layers,
        max_vertices=max_vertices,
        render_mode="contours",
        file_signature=signature,
    )
    geometry_render_mode = "fill" if include_fill else "contours_only"
    geometry_key = make_cache_key(
        document,
        threshold=threshold,
        bin_mode=bin_mode,
        xy_stride=xy_stride,
        z_stride=effective_z_stride,
        simplify_epsilon=simplify_epsilon,
        max_layers=max_layers,
        max_vertices=max_vertices,
        render_mode=geometry_render_mode,
        file_signature=signature,
    )

    contour_stack: PwmbContourStack | None = None
    contour_cache_hit = False
    if cache is not None:
        if stage_cb is not None:
            stage_cb("cache_contours_lookup")
        contour_stack = cache.get_contours(contour_key)
        contour_cache_hit = contour_stack is not None
        if contour_cache_hit and stage_cb is not None:
            stage_cb("cache_contours_hit")
    if contour_stack is None:
        if stage_cb is not None:
            stage_cb("decode")
            stage_cb("contours")
        contour_stack = selected_backend.build_contours(
            contour_document,
            threshold=threshold,
            binarization_mode=bin_mode,
            xy_stride=xy_stride,
            metrics=metrics,
        )
        if cache is not None:
            cache.set_contours(contour_key, contour_stack)

    geometry: PwmbContourGeometry | None = None
    geometry_cache_hit = False
    if cache is not None:
        if stage_cb is not None:
            stage_cb("cache_geometry_lookup")
        geometry = cache.get_geometry(geometry_key)
        geometry_cache_hit = geometry is not None
        if geometry_cache_hit and stage_cb is not None:
            stage_cb("cache_geometry_hit")
    if geometry is None:
        if stage_cb is not None:
            stage_cb("geometry")
        geometry = selected_backend.build_geometry(
            contour_stack,
            max_layers=max_layers,
            max_vertices=max_vertices,
            max_xy_stride=max_xy_stride,
            include_fill=include_fill,
            metrics=metrics,
        )
        if cache is not None:
            cache.set_geometry(geometry_key, geometry)

    return GeometryBuildResult(
        contour_stack=contour_stack,
        geometry=geometry,
        backend_name=selected_backend.name,
        file_signature=signature,
        contour_key=contour_key,
        geometry_key=geometry_key,
        contour_cache_hit=contour_cache_hit,
        geometry_cache_hit=geometry_cache_hit,
    )


def _sample_document_layers(document: PwmbDocument, *, z_stride: int) -> PwmbDocument:
    stride = max(1, int(z_stride))
    if stride <= 1 or len(document.layers) <= 1:
        return document
    sampled_layers = document.layers[::stride]
    if not sampled_layers:
        sampled_layers = document.layers[:1]
    return replace(document, layers=sampled_layers)
