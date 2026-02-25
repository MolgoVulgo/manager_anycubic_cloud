from __future__ import annotations

import importlib
import logging
import os
from dataclasses import dataclass
from types import ModuleType
from typing import Protocol, runtime_checkable

from pwmb_core.types import PwmbDocument
from render3d_core.contours import build_contour_stack
from render3d_core.geometry_v2 import build_geometry_v2
from render3d_core.perf import BuildMetrics
from render3d_core.types import PwmbContourGeometry, PwmbContourStack


LOGGER_BACKEND = logging.getLogger("render3d.backend")
GEOM_BACKEND_ENV = "GEOM_BACKEND"


@runtime_checkable
class GeometryBackend(Protocol):
    @property
    def name(self) -> str:
        ...

    def build_contours(
        self,
        document: PwmbDocument,
        *,
        threshold: int,
        binarization_mode: str,
        xy_stride: int,
        metrics: BuildMetrics | None = None,
    ) -> PwmbContourStack:
        ...

    def build_geometry(
        self,
        contour_stack: PwmbContourStack,
        *,
        max_layers: int | None,
        max_vertices: int | None,
        max_xy_stride: int,
        include_fill: bool = True,
        metrics: BuildMetrics | None = None,
    ) -> PwmbContourGeometry:
        ...


@dataclass(slots=True)
class PythonGeometryBackend:
    _name: str = "python"

    @property
    def name(self) -> str:
        return self._name

    def build_contours(
        self,
        document: PwmbDocument,
        *,
        threshold: int,
        binarization_mode: str,
        xy_stride: int,
        metrics: BuildMetrics | None = None,
    ) -> PwmbContourStack:
        return build_contour_stack(
            document=document,
            threshold=threshold,
            binarization_mode=binarization_mode,
            xy_stride=xy_stride,
            metrics=metrics,
        )

    def build_geometry(
        self,
        contour_stack: PwmbContourStack,
        *,
        max_layers: int | None,
        max_vertices: int | None,
        max_xy_stride: int,
        include_fill: bool = True,
        metrics: BuildMetrics | None = None,
    ) -> PwmbContourGeometry:
        return build_geometry_v2(
            contour_stack,
            max_layers=max_layers,
            max_vertices=max_vertices,
            max_xy_stride=max_xy_stride,
            include_fill=include_fill,
            metrics=metrics,
        )


@dataclass(slots=True)
class CppGeometryBackend:
    module: ModuleType
    _name: str = "cpp"

    @property
    def name(self) -> str:
        return self._name

    def build_contours(
        self,
        document: PwmbDocument,
        *,
        threshold: int,
        binarization_mode: str,
        xy_stride: int,
        metrics: BuildMetrics | None = None,
    ) -> PwmbContourStack:
        if not hasattr(self.module, "build_contours"):
            raise RuntimeError("pwmb_geom backend missing build_contours")
        return self.module.build_contours(  # type: ignore[no-any-return]
            document=document,
            threshold=threshold,
            binarization_mode=binarization_mode,
            xy_stride=xy_stride,
            metrics=metrics,
        )

    def build_geometry(
        self,
        contour_stack: PwmbContourStack,
        *,
        max_layers: int | None,
        max_vertices: int | None,
        max_xy_stride: int,
        include_fill: bool = True,
        metrics: BuildMetrics | None = None,
    ) -> PwmbContourGeometry:
        if not hasattr(self.module, "build_geometry"):
            raise RuntimeError("pwmb_geom backend missing build_geometry")
        return self.module.build_geometry(  # type: ignore[no-any-return]
            contour_stack=contour_stack,
            max_layers=max_layers,
            max_vertices=max_vertices,
            max_xy_stride=max_xy_stride,
            include_fill=include_fill,
            metrics=metrics,
        )


def resolve_geometry_backend(*, preferred: str | None = None) -> GeometryBackend:
    selected_raw = preferred if preferred is not None else os.getenv(GEOM_BACKEND_ENV, "auto")
    selected = (selected_raw or "auto").strip().lower()

    if selected in {"auto", ""}:
        cpp = _try_load_cpp_backend()
        if cpp is not None:
            return cpp
        return PythonGeometryBackend()

    if selected == "cpp":
        cpp = _try_load_cpp_backend()
        if cpp is not None:
            return cpp
        LOGGER_BACKEND.warning("GEOM_BACKEND=cpp requested but pwmb_geom is unavailable, fallback to python")

    if selected != "python":
        LOGGER_BACKEND.warning("Unknown GEOM_BACKEND=%s, fallback to python", selected)
    return PythonGeometryBackend()


def get_geometry_backend() -> GeometryBackend:
    return resolve_geometry_backend()


def _try_load_cpp_backend() -> CppGeometryBackend | None:
    try:
        module = importlib.import_module("pwmb_geom")
    except Exception:
        return None
    if not hasattr(module, "build_contours") or not hasattr(module, "build_geometry"):
        return None
    return CppGeometryBackend(module=module)
