from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future
from contextlib import nullcontext
from dataclasses import dataclass
import logging
import math
import os
import queue
from pathlib import Path
from time import perf_counter

import numpy as np

from accloud_core.logging_contract import emit_event, operation_context
from app_gui_qt.qt_compat import require_qt
from app_gui_qt.widgets import make_panel
from pwmb_core import open_layer_blob_reader, read_pwmb_document
from pwmb_core.decode_pws import select_pws_convention
from render3d_core import (
    BuildCache,
    BuildMetrics,
    GEOM_BACKEND_ENV,
    GpuMetrics,
    build_geometry_pipeline,
    get_geometry_backend,
)
from render3d_core.task_runner import CancellationToken, CancelledError, TaskRunner
from render3d_core.types import LayerRange, PwmbContourGeometry


GL_FLOAT = 0x1406
GL_TRIANGLES = 0x0004
GL_LINES = 0x0001
GL_POINTS = 0x0000
GL_COLOR_BUFFER_BIT = 0x00004000
GL_DEPTH_BUFFER_BIT = 0x00000100
GL_DEPTH_TEST = 0x0B71
GL_BLEND = 0x0BE2
GL_SRC_ALPHA = 0x0302
GL_ONE_MINUS_SRC_ALPHA = 0x0303
LOGGER_GUI = logging.getLogger("app.gui")
LOGGER_BUILD = logging.getLogger("render3d.build")
LOGGER_GPU = logging.getLogger("render3d.gpu")
_VIEWER_BUILD_CACHE = BuildCache()

_STAGE_LABELS = {
    "read": "Reading PWMB file...",
    "decode": "Decoding layer rasters...",
    "contours": "Extracting contours...",
    "geometry": "Building triangulation buffers...",
    "cache": "Using/refreshing geometry cache...",
    "upload": "Uploading buffers to GPU...",
    "done": "Build completed.",
}
_PHASE_LABELS = {
    "contours": "Pass 1/2 (contours)",
    "fill": "Pass 2/2 (fill)",
}
_POOL_KIND_ENV = "RENDER3D_POOL_KIND"
_POOL_WORKERS_ENV = "RENDER3D_POOL_WORKERS"
_VALID_POOL_KINDS = {"auto", "threads", "processes"}
_DEFAULT_POOL_WORKERS = 2
_VIEWER_SETTINGS_ORG = "accloud"
_VIEWER_SETTINGS_APP = "pwmb3d_viewer"
_VIEWER_SETTINGS_PREFIX = "viewer"


@dataclass(slots=True)
class _BuildJobResult:
    geometry: PwmbContourGeometry
    built_layer_ids: list[int]
    document_layer_count: int
    source_path: str
    phase: str
    include_fill: bool
    backend_name: str
    xy_stride: int
    z_stride: int
    metrics: BuildMetrics
    contour_cache_hit: bool
    geometry_cache_hit: bool


@dataclass(slots=True)
class _RunnerStrategy:
    pool_kind: str
    workers: int
    reason: str


def _coerce_pool_workers(raw_value: str | None) -> int:
    if raw_value is None or str(raw_value).strip() == "":
        return _DEFAULT_POOL_WORKERS
    try:
        parsed = int(str(raw_value).strip())
    except Exception:
        return _DEFAULT_POOL_WORKERS
    cpu_cap = max(1, int(os.cpu_count() or 1))
    return max(1, min(parsed, cpu_cap))


def _resolve_runner_strategy(*, backend_name: str) -> _RunnerStrategy:
    requested_raw = os.getenv(_POOL_KIND_ENV, "auto")
    requested = str(requested_raw).strip().lower() or "auto"
    workers = _coerce_pool_workers(os.getenv(_POOL_WORKERS_ENV))
    if requested not in _VALID_POOL_KINDS:
        requested = "auto"
    if requested == "threads":
        return _RunnerStrategy(
            pool_kind="threads",
            workers=workers,
            reason=f"{_POOL_KIND_ENV}=threads",
        )
    if requested == "processes":
        return _RunnerStrategy(
            pool_kind="threads",
            workers=workers,
            reason=f"{_POOL_KIND_ENV}=processes requested but viewer uses threads for cooperative cancellation",
        )
    if backend_name == "cpp":
        return _RunnerStrategy(
            pool_kind="threads",
            workers=workers,
            reason="auto: cpp backend uses native sections (GIL-released), threads selected",
        )
    return _RunnerStrategy(
        pool_kind="threads",
        workers=workers,
        reason="auto: python backend fallback keeps threads for viewer cancellation/progress",
    )


def _raise_if_cancelled(cancel_token: object | None) -> None:
    if cancel_token is None:
        return
    checker = getattr(cancel_token, "raise_if_cancelled", None)
    if callable(checker):
        checker()


def _select_preview_xy_stride(*, width: int, height: int) -> int:
    pixels = max(0, int(width)) * max(0, int(height))
    if pixels >= 24_000_000:
        base_stride = 6
    elif pixels >= 12_000_000:
        base_stride = 4
    elif pixels >= 6_000_000:
        base_stride = 3
    elif pixels >= 2_500_000:
        base_stride = 2
    else:
        base_stride = 1
    return base_stride


def _select_preview_xy_stride_for_complexity(*, width: int, height: int, layer_count: int) -> int:
    stride = _select_preview_xy_stride(width=width, height=height)
    complexity = max(0, int(width)) * max(0, int(height)) * max(1, int(layer_count))
    if complexity >= 11_000_000_000:
        return min(6, stride + 2)
    if complexity >= 9_000_000_000:
        return min(6, stride + 1)
    return stride


def _select_preview_z_stride(
    *,
    layer_count: int,
    width: int | None = None,
    height: int | None = None,
    target_layers: int = 600,
) -> int:
    layers = max(1, int(layer_count))
    target = max(8, int(target_layers))
    if width is not None and height is not None:
        complexity = max(0, int(width)) * max(0, int(height)) * layers
        if complexity >= 11_000_000_000:
            target = min(target, 200)
        elif complexity >= 9_000_000_000:
            target = min(target, 300)
    return max(1, int(math.ceil(float(layers) / float(target))))


def _select_preview_max_vertices(*, width: int, height: int, layer_count: int) -> int:
    complexity = max(0, int(width)) * max(0, int(height)) * max(1, int(layer_count))
    if complexity >= 11_000_000_000:
        return 1_200_000
    return 1_200_000


def _build_geometry_job(
    *,
    source_path: str,
    threshold: int,
    bin_mode: str,
    phase: str,
    include_fill: bool,
    op_id: str,
    pool_kind: str,
    workers: int,
    cancel_token: object | None = None,
    progress_cb: Callable[[str, int, str], None] | None = None,
) -> _BuildJobResult:
    metrics = BuildMetrics(pool_kind=str(pool_kind), workers=max(1, int(workers)))
    backend = get_geometry_backend()

    def _stage(percent: int, stage: str) -> None:
        pct = max(0, min(100, int(percent)))
        if progress_cb is not None:
            progress_cb(phase, pct, stage)
        LOGGER_BUILD.info("PWMB build phase=%s stage=%s percent=%d", phase, stage, pct)

    with operation_context(op_id):
        try:
            _raise_if_cancelled(cancel_token)
            _stage(5, "read")
            parse_start = perf_counter()
            document = read_pwmb_document(source_path)
            _raise_if_cancelled(cancel_token)
            _ensure_pws_convention(document, cancel_token=cancel_token)
            _raise_if_cancelled(cancel_token)
            metrics.parse_ms = (perf_counter() - parse_start) * 1000.0
            layer_count = len(document.layers)
            xy_stride = _select_preview_xy_stride_for_complexity(
                width=document.width,
                height=document.height,
                layer_count=layer_count,
            )
            z_stride = _select_preview_z_stride(
                layer_count=layer_count,
                width=document.width,
                height=document.height,
            )
            max_vertices_profile = _select_preview_max_vertices(
                width=document.width,
                height=document.height,
                layer_count=layer_count,
            )
            # Progressive mode must preserve full Z coverage. A hard global vertex budget
            # truncates the tail layers on dense models (e.g. raven_skull), so we disable
            # it for viewer builds and rely on XY/Z sampling for performance.
            max_vertices: int | None = None

            emit_event(
                LOGGER_BUILD,
                logging.INFO,
                event="build.profile",
                msg="PWMB viewer build profile selected",
                component="render3d.build",
                op_id=op_id,
                data={
                    "pwmb": {"W": document.width, "H": document.height},
                    "render3d": {
                        "xy_stride": xy_stride,
                        "z_stride": z_stride,
                        "max_vertices_profile": max_vertices_profile,
                        "max_vertices_applied": max_vertices,
                        "geom_backend": backend.name,
                        "phase": phase,
                        "include_fill": bool(include_fill),
                    },
                },
            )

            stage_map = {
                "cache_contours_lookup": (12, "cache"),
                "cache_contours_hit": (25, "cache"),
                "decode": (22, "decode"),
                "contours": (46, "contours"),
                "cache_geometry_lookup": (58, "cache"),
                "cache_geometry_hit": (78, "cache"),
                "geometry": (72, "geometry"),
            }

            def _pipeline_stage_cb(stage: str) -> None:
                progress = stage_map.get(stage)
                if progress is None:
                    return
                _stage(progress[0], progress[1])

            _raise_if_cancelled(cancel_token)
            pipeline_result = build_geometry_pipeline(
                document,
                threshold=threshold,
                bin_mode=bin_mode,
                xy_stride=xy_stride,
                z_stride=z_stride,
                max_layers=None,
                max_vertices=max_vertices,
                max_xy_stride=1,
                include_fill=include_fill,
                backend=backend,
                cache=_VIEWER_BUILD_CACHE,
                metrics=metrics,
                stage_cb=_pipeline_stage_cb,
                cancel_token=cancel_token,
            )
            _raise_if_cancelled(cancel_token)
            contour_stack = pipeline_result.contour_stack
            geometry = pipeline_result.geometry
            contour_cache_hit = pipeline_result.contour_cache_hit
            geometry_cache_hit = pipeline_result.geometry_cache_hit

            _stage(90, "upload")
            _stage(100, "done")

            emit_event(
                LOGGER_BUILD,
                logging.INFO,
                event="build.metrics",
                msg="PWMB geometry build metrics",
                component="render3d.build",
                op_id=op_id,
                data={
                    "render3d": {
                        **metrics.as_log_data(),
                        "geom_backend": backend.name,
                        "geom_backend_env": GEOM_BACKEND_ENV,
                        "xy_stride": xy_stride,
                        "z_stride": z_stride,
                        "max_vertices_profile": max_vertices_profile,
                        "max_vertices_applied": max_vertices,
                        "phase": phase,
                        "include_fill": bool(include_fill),
                        "contour_cache_hit": contour_cache_hit,
                        "geometry_cache_hit": geometry_cache_hit,
                    }
                },
            )
            LOGGER_BUILD.info(
                "PWMB geometry build_ms=%.3f triangles=%d lines=%d points=%d",
                metrics.triangulation_ms_total,
                len(geometry.triangle_vertices) // 3,
                len(geometry.line_vertices) // 2,
                len(geometry.point_vertices),
            )
            return _BuildJobResult(
                geometry=geometry,
                built_layer_ids=sorted(contour_stack.layers.keys()),
                document_layer_count=len(document.layers),
                source_path=source_path,
                phase=phase,
                include_fill=bool(include_fill),
                backend_name=pipeline_result.backend_name,
                xy_stride=xy_stride,
                z_stride=z_stride,
                metrics=metrics,
                contour_cache_hit=contour_cache_hit,
                geometry_cache_hit=geometry_cache_hit,
            )
        except CancelledError as exc:
            emit_event(
                LOGGER_BUILD,
                logging.WARNING,
                event="build.cancelled",
                msg="PWMB geometry build cancelled",
                component="render3d.build",
                op_id=op_id,
                data={"render3d": {"phase": phase, "include_fill": bool(include_fill)}},
                error={"type": type(exc).__name__, "message": str(exc)},
            )
            raise


def _ensure_pws_convention(document, *, cancel_token: object | None = None) -> None:
    _raise_if_cancelled(cancel_token)
    if "pws" not in document.machine.layer_image_format.lower():
        return
    if document.pws_convention:
        return
    width = document.width
    height = document.height
    aa = max(1, int(document.header.anti_aliasing))
    reader_context: object
    try:
        reader_context = open_layer_blob_reader(document)
    except Exception:
        reader_context = nullcontext(None)
    with reader_context as reader:
        for layer in document.layers:
            _raise_if_cancelled(cancel_token)
            if layer.data_length <= 0:
                continue
            try:
                if reader is not None:
                    blob = reader.read(layer.data_address, layer.data_length)
                else:
                    with document.path.open("rb") as handle:
                        handle.seek(layer.data_address)
                        blob = handle.read(layer.data_length)
            except Exception:
                continue
            if not blob:
                continue
            try:
                convention = select_pws_convention(
                    blob=blob,
                    width=width,
                    height=height,
                    anti_aliasing=aa,
                )
            except Exception:
                continue
            document.pws_convention = convention.value
            return


def _camera_pose_for_orbit(
    *,
    center: tuple[float, float, float],
    distance: float,
    yaw_deg: float,
    pitch_deg: float,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    yaw = math.radians(float(yaw_deg))
    pitch = math.radians(float(pitch_deg))
    d = max(0.001, float(distance))
    cp = math.cos(pitch)
    sp = math.sin(pitch)
    cy = math.cos(yaw)
    sy = math.sin(yaw)
    offset_x = -sy * cp * d
    offset_y = sp * d
    offset_z = cy * cp * d
    camera_pos = (
        float(center[0] + offset_x),
        float(center[1] + offset_y),
        float(center[2] + offset_z),
    )
    to_center = (
        float(center[0] - camera_pos[0]),
        float(center[1] - camera_pos[1]),
        float(center[2] - camera_pos[2]),
    )
    length = math.sqrt(to_center[0] * to_center[0] + to_center[1] * to_center[1] + to_center[2] * to_center[2])
    if length <= 1e-12:
        forward = (0.0, 0.0, -1.0)
    else:
        inv = 1.0 / length
        forward = (to_center[0] * inv, to_center[1] * inv, to_center[2] * inv)
    return camera_pos, forward


def _sort_layers_back_to_front(
    *,
    layer_ids: list[int],
    layer_z: dict[int, float],
    center: tuple[float, float, float],
    distance: float,
    yaw_deg: float,
    pitch_deg: float,
) -> list[int]:
    camera_pos, forward = _camera_pose_for_orbit(
        center=center,
        distance=distance,
        yaw_deg=yaw_deg,
        pitch_deg=pitch_deg,
    )

    def _depth(layer_id: int) -> float:
        p = (float(center[0]), float(center[1]), float(layer_z.get(layer_id, 0.0)))
        vx = p[0] - camera_pos[0]
        vy = p[1] - camera_pos[1]
        vz = p[2] - camera_pos[2]
        return (vx * forward[0]) + (vy * forward[1]) + (vz * forward[2])

    return sorted(layer_ids, key=lambda layer_id: (-_depth(layer_id), layer_id))


def _build_viewport_placeholder(parent=None, *, message: str = "OpenGL renderer is unavailable."):
    _qtcore, qtwidgets = require_qt()
    viewport = make_panel(parent=parent, object_name="cardAlt")
    viewport.setStyleSheet(
        viewport.styleSheet()
        + """
        QFrame#cardAlt {
            background: qradialgradient(
                cx: 0.5, cy: 0.5, radius: 0.9,
                fx: 0.35, fy: 0.3,
                stop: 0 #2f5f5a,
                stop: 0.65 #1f403c,
                stop: 1 #112826
            );
            border: 1px solid #0f2422;
            border-radius: 12px;
        }
        QLabel {
            color: #dff2ef;
        }
        """
    )
    layout = qtwidgets.QVBoxLayout(viewport)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(10)
    title = qtwidgets.QLabel("3D viewport unavailable")
    title.setStyleSheet("font-size: 20px; font-weight: 650;")
    body = qtwidgets.QLabel(message)
    body.setWordWrap(True)
    layout.addWidget(title)
    layout.addWidget(body)
    layout.addStretch(1)
    return viewport


def _make_viewport(parent=None):
    qtcore, qtwidgets = require_qt()
    try:
        from PySide6 import QtGui, QtOpenGL, QtOpenGLWidgets  # type: ignore
    except ImportError:
        try:
            from PySide6 import QtGui, QtOpenGLWidgets  # type: ignore
        except ImportError:
            return _build_viewport_placeholder(parent=parent), None
        QtOpenGL = None  # type: ignore[assignment]

    qopengl_buffer = getattr(QtGui, "QOpenGLBuffer", None)
    qopengl_shader_program = getattr(QtGui, "QOpenGLShaderProgram", None)
    qopengl_shader = getattr(QtGui, "QOpenGLShader", None)
    if qopengl_buffer is None or qopengl_shader_program is None or qopengl_shader is None:
        if QtOpenGL is None:
            return _build_viewport_placeholder(
                parent=parent,
                message="OpenGL classes are unavailable in this PySide6 build.",
            ), None
        qopengl_buffer = getattr(QtOpenGL, "QOpenGLBuffer", None)
        qopengl_shader_program = getattr(QtOpenGL, "QOpenGLShaderProgram", None)
        qopengl_shader = getattr(QtOpenGL, "QOpenGLShader", None)
        if qopengl_buffer is None or qopengl_shader_program is None or qopengl_shader is None:
            return _build_viewport_placeholder(
                parent=parent,
                message="OpenGL classes are unavailable in this PySide6 build.",
            ), None

    class PwmbOpenGLViewport(QtOpenGLWidgets.QOpenGLWidget):  # type: ignore[misc]
        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self.setObjectName("pwmbViewport")
            self.setMinimumSize(480, 360)
            self.setMouseTracking(True)
            self._program = None
            self._funcs = None
            self._shader_error: str | None = None
            self._renderer_error: str | None = None

            self._vbo_tri = qopengl_buffer(qopengl_buffer.Type.VertexBuffer)
            self._vbo_line = qopengl_buffer(qopengl_buffer.Type.VertexBuffer)
            self._vbo_point = qopengl_buffer(qopengl_buffer.Type.VertexBuffer)

            self._geometry = PwmbContourGeometry()
            self._gpu_dirty = True
            self._layer_ids: list[int] = []
            self._layer_z: dict[int, float] = {}
            self._layer_cutoff = 0
            self._stride_z = 1
            self._force_full_quality = False
            self._contour_only = False

            self._yaw_deg = -35.0
            self._pitch_deg = 28.0
            self._distance = 6.0
            self._center = QtGui.QVector3D(0.0, 0.0, 0.0)
            self._last_pos = qtcore.QPoint()
            self._gpu_metrics = GpuMetrics()
            self._log_next_draw = False

        def initializeGL(self) -> None:  # noqa: N802
            try:
                context = self.context()
                if context is None:
                    self._set_renderer_error("OpenGL context is unavailable.")
                    return
                self._funcs = context.functions()
                if self._funcs is None:
                    self._set_renderer_error("OpenGL functions are unavailable.")
                    return
                self._funcs.glEnable(GL_DEPTH_TEST)
                self._funcs.glEnable(GL_BLEND)
                self._funcs.glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

                program = qopengl_shader_program(self)
                vertex_shader = """
                    attribute vec4 a_data;
                    uniform mat4 u_mvp;
                    void main() {
                        gl_Position = u_mvp * vec4(a_data.xyz, 1.0);
                    }
                """
                fragment_shader = """
                    uniform vec4 u_color;
                    void main() {
                        gl_FragColor = u_color;
                    }
                """
                if not program.addShaderFromSourceCode(qopengl_shader.ShaderTypeBit.Vertex, vertex_shader):
                    self._shader_error = program.log()
                    self._set_renderer_error(f"OpenGL vertex shader compilation failed: {self._shader_error}")
                    return
                if not program.addShaderFromSourceCode(qopengl_shader.ShaderTypeBit.Fragment, fragment_shader):
                    self._shader_error = program.log()
                    self._set_renderer_error(f"OpenGL fragment shader compilation failed: {self._shader_error}")
                    return
                if not program.link():
                    self._shader_error = program.log()
                    self._set_renderer_error(f"OpenGL shader program linking failed: {self._shader_error}")
                    return
                self._program = program

                self._vbo_tri.create()
                self._vbo_line.create()
                self._vbo_point.create()
                self._gpu_dirty = True
            except Exception as exc:
                self._set_renderer_error("OpenGL initialization failed.", error=exc)

        def resizeGL(self, width: int, height: int) -> None:  # noqa: N802
            if self._funcs is not None:
                self._funcs.glViewport(0, 0, max(1, width), max(1, height))

        def paintGL(self) -> None:  # noqa: N802
            if self._funcs is None:
                return
            self._funcs.glClearColor(0.05, 0.11, 0.10, 1.0)
            self._funcs.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            if self._renderer_error is not None:
                return
            if self._shader_error or self._program is None:
                return

            try:
                if self._gpu_dirty:
                    self._upload_gpu_buffers()
                    self._gpu_dirty = False

                mvp = self._make_mvp()
                draw_layers = self._compute_visible_layers()
                self._gpu_metrics.visible_layers_count = len(draw_layers)
                if not draw_layers:
                    return

                self._program.bind()
                self._program.setUniformValue("u_mvp", mvp)

                tri_ms = 0.0
                if not self._contour_only:
                    self._program.setUniformValue("u_color", QtGui.QVector4D(0.23, 0.85, 0.70, 0.52))
                    tri_ms = self._draw_buffer(
                        vbo=self._vbo_tri,
                        mode=GL_TRIANGLES,
                        ranges=self._geometry.tri_range,
                        layers=draw_layers,
                    )

                self._program.setUniformValue("u_color", QtGui.QVector4D(0.05, 0.95, 0.85, 1.0))
                line_ms = self._draw_buffer(
                    vbo=self._vbo_line,
                    mode=GL_LINES,
                    ranges=self._geometry.line_range,
                    layers=draw_layers,
                )
                self._program.setUniformValue("u_color", QtGui.QVector4D(0.95, 0.95, 0.95, 1.0))
                point_ms = self._draw_buffer(
                    vbo=self._vbo_point,
                    mode=GL_POINTS,
                    ranges=self._geometry.point_range,
                    layers=draw_layers,
                )
                self._program.release()

                self._gpu_metrics.draw_ms_tri = tri_ms
                self._gpu_metrics.draw_ms_line = line_ms
                self._gpu_metrics.draw_ms_point = point_ms
                if self._log_next_draw:
                    LOGGER_GPU.info(
                        "PWMB draw mode=%s visible_layers=%d cutoff_layer=%d",
                        "contours" if self._contour_only else "fill",
                        len(draw_layers),
                        int(self._layer_cutoff),
                    )
                    gpu_data = self._gpu_metrics.as_log_data()
                    gpu_data["layer_cutoff"] = int(self._layer_cutoff)
                    emit_event(
                        LOGGER_GPU,
                        logging.INFO,
                        event="gpu.draw",
                        msg="PWMB GPU draw metrics",
                        component="render3d.gpu",
                        data={"render3d": gpu_data},
                    )
                    self._log_next_draw = False
            except Exception as exc:
                self._set_renderer_error("OpenGL draw/upload failed.", error=exc)

        def _upload_gpu_buffers(self) -> None:
            start = perf_counter()
            tri_bytes = self._upload_single_buffer(self._vbo_tri, self._geometry.triangle_vertices)
            line_bytes = self._upload_single_buffer(self._vbo_line, self._geometry.line_vertices)
            point_bytes = self._upload_single_buffer(self._vbo_point, self._geometry.point_vertices)
            self._layer_z = self._build_layer_z_map()
            self._fit_camera_to_geometry()

            self._gpu_metrics.upload_ms = (perf_counter() - start) * 1000.0
            self._gpu_metrics.vbo_bytes_tri = tri_bytes
            self._gpu_metrics.vbo_bytes_line = line_bytes
            self._gpu_metrics.vbo_bytes_point = point_bytes
            emit_event(
                LOGGER_GPU,
                logging.INFO,
                event="gpu.upload",
                msg="PWMB GPU upload metrics",
                component="render3d.gpu",
                data={"render3d": self._gpu_metrics.as_log_data()},
            )

        def _as_vertices_array(self, vertices: object) -> np.ndarray:
            if isinstance(vertices, np.ndarray):
                if vertices.size == 0:
                    return np.zeros((0, 4), dtype=np.float32)
                arr = vertices
            else:
                if not vertices:
                    return np.zeros((0, 4), dtype=np.float32)
                arr = np.asarray(vertices, dtype=np.float32)
            arr = np.asarray(arr, dtype=np.float32)
            if arr.ndim == 1:
                arr = arr.reshape((-1, 4))
            elif arr.ndim != 2 or arr.shape[1] != 4:
                arr = arr.reshape((-1, 4))
            return np.ascontiguousarray(arr, dtype=np.float32)

        def _upload_single_buffer(self, vbo, vertices: object) -> int:
            if not vbo.isCreated():
                vbo.create()
            array = self._as_vertices_array(vertices)
            payload = array.tobytes()
            vbo.bind()
            try:
                vbo.allocate(payload, int(len(payload)))
            finally:
                vbo.release()
            return int(len(payload))

        def _draw_buffer(
            self,
            *,
            vbo,
            mode: int,
            ranges: dict[int, LayerRange],
            layers: list[int],
        ) -> float:
            if self._funcs is None or self._program is None:
                return 0.0
            start = perf_counter()
            vbo.bind()
            self._program.enableAttributeArray(0)
            self._program.setAttributeBuffer(0, GL_FLOAT, 0, 4, 16)
            if mode == GL_LINES:
                line_width = getattr(self._funcs, "glLineWidth", None)
                if callable(line_width):
                    line_width(1.0)
            elif mode == GL_POINTS:
                point_size = getattr(self._funcs, "glPointSize", None)
                if callable(point_size):
                    point_size(2.0)
            for layer_id in layers:
                layer_range = ranges.get(layer_id)
                if layer_range is None or layer_range.count <= 0:
                    continue
                self._funcs.glDrawArrays(mode, layer_range.start, layer_range.count)
            self._program.disableAttributeArray(0)
            vbo.release()
            return (perf_counter() - start) * 1000.0

        def _make_mvp(self):
            from PySide6 import QtGui  # type: ignore

            aspect = max(1.0, float(self.width()) / float(max(1, self.height())))
            proj = QtGui.QMatrix4x4()
            proj.perspective(45.0, aspect, 0.01, 5000.0)

            view = QtGui.QMatrix4x4()
            view.translate(0.0, 0.0, -self._distance)
            view.rotate(self._pitch_deg, 1.0, 0.0, 0.0)
            view.rotate(self._yaw_deg, 0.0, 1.0, 0.0)
            view.translate(-self._center.x(), -self._center.y(), -self._center.z())
            return proj * view

        def _compute_visible_layers(self) -> list[int]:
            layers = [layer_id for layer_id in self._layer_ids if layer_id <= self._layer_cutoff]
            stride = 1 if self._force_full_quality else max(1, self._stride_z)
            if stride > 1:
                layers = layers[::stride]
            return _sort_layers_back_to_front(
                layer_ids=layers,
                layer_z=self._layer_z,
                center=(self._center.x(), self._center.y(), self._center.z()),
                distance=self._distance,
                yaw_deg=self._yaw_deg,
                pitch_deg=self._pitch_deg,
            )

        def _build_layer_z_map(self) -> dict[int, float]:
            layer_z: dict[int, float] = {}
            for layer_id in self._layer_ids:
                z_value: float | None = self._pick_range_z(layer_id, self._geometry.tri_range, self._geometry.triangle_vertices)
                if z_value is None:
                    z_value = self._pick_range_z(layer_id, self._geometry.line_range, self._geometry.line_vertices)
                if z_value is None:
                    z_value = self._pick_range_z(layer_id, self._geometry.point_range, self._geometry.point_vertices)
                if z_value is None:
                    z_value = 0.0
                layer_z[layer_id] = z_value
            return layer_z

        def _pick_range_z(
            self,
            layer_id: int,
            ranges: dict[int, LayerRange],
            vertices: object,
        ) -> float | None:
            layer_range = ranges.get(layer_id)
            if layer_range is None or layer_range.count <= 0:
                return None
            if layer_range.start < 0 or layer_range.start >= len(vertices):
                return None
            return float(vertices[layer_range.start][2])

        def _fit_camera_to_geometry(self) -> None:
            tri = self._as_vertices_array(self._geometry.triangle_vertices)
            line = self._as_vertices_array(self._geometry.line_vertices)
            point = self._as_vertices_array(self._geometry.point_vertices)
            arrays = [arr for arr in (tri, line, point) if arr.shape[0] > 0]
            if not arrays:
                self._center = QtGui.QVector3D(0.0, 0.0, 0.0)
                self._distance = 6.0
                return
            arr = arrays[0] if len(arrays) == 1 else np.concatenate(arrays, axis=0)
            mins = arr[:, :3].min(axis=0)
            maxs = arr[:, :3].max(axis=0)
            center = (mins + maxs) * 0.5
            extent = np.max(maxs - mins)
            self._center = QtGui.QVector3D(float(center[0]), float(center[1]), float(center[2]))
            self._distance = max(2.0, float(extent) * 2.5 + 1.0)

        def set_geometry(self, geometry: PwmbContourGeometry, *, layer_ids: list[int]) -> None:
            self._geometry = geometry
            self._layer_ids = sorted(layer_ids)
            self._layer_cutoff = self._layer_ids[-1] if self._layer_ids else 0
            self._gpu_dirty = True
            self._log_next_draw = True
            self.update()

        def set_layer_cutoff(self, value: int) -> None:
            self._layer_cutoff = int(value)
            self._log_next_draw = True
            self.update()

        def set_stride_z(self, value: int) -> None:
            self._stride_z = max(1, int(value))
            self._log_next_draw = True
            self.update()

        def set_force_full_quality(self, enabled: bool) -> None:
            self._force_full_quality = bool(enabled)
            self._log_next_draw = True
            self.update()

        def set_contour_only(self, enabled: bool) -> None:
            self._contour_only = bool(enabled)
            self._log_next_draw = True
            self.update()

        def reset_camera(self) -> None:
            self._yaw_deg = -35.0
            self._pitch_deg = 28.0
            self._fit_camera_to_geometry()
            self._log_next_draw = True
            self.update()

        def renderer_error_message(self) -> str | None:
            return self._renderer_error

        def _set_renderer_error(self, message: str, *, error: Exception | None = None) -> None:
            if self._renderer_error is not None:
                return
            self._renderer_error = str(message).strip() or "OpenGL renderer failure."
            if error is None:
                emit_event(
                    LOGGER_GPU,
                    logging.ERROR,
                    event="gpu.renderer_fail",
                    msg=self._renderer_error,
                    component="render3d.gpu",
                )
            else:
                emit_event(
                    LOGGER_GPU,
                    logging.ERROR,
                    event="gpu.renderer_fail",
                    msg=self._renderer_error,
                    component="render3d.gpu",
                    error={"type": type(error).__name__, "message": str(error)},
                )

        def mousePressEvent(self, event) -> None:  # noqa: N802
            self._last_pos = event.position().toPoint()
            super().mousePressEvent(event)

        def mouseMoveEvent(self, event) -> None:  # noqa: N802
            pos = event.position().toPoint()
            dx = pos.x() - self._last_pos.x()
            dy = pos.y() - self._last_pos.y()
            self._last_pos = pos
            if event.buttons() & qtcore.Qt.MouseButton.LeftButton:
                self._yaw_deg += dx * 0.35
                self._pitch_deg = max(-89.0, min(89.0, self._pitch_deg + dy * 0.35))
                self._log_next_draw = True
                self.update()
            super().mouseMoveEvent(event)

        def wheelEvent(self, event) -> None:  # noqa: N802
            delta = event.angleDelta().y()
            factor = 0.9 if delta > 0 else 1.1
            self._distance = max(0.25, min(5000.0, self._distance * factor))
            self._log_next_draw = True
            self.update()
            super().wheelEvent(event)

    return PwmbOpenGLViewport(parent=parent), PwmbOpenGLViewport


def build_pwmb3d_dialog(
    parent=None,
    *,
    pwmb_path: str | Path | None = None,
    file_label: str | None = None,
    resolve_pwmb_path: Callable[[], Path | None] | None = None,
):
    qtcore, qtwidgets = require_qt()
    dialog = qtwidgets.QDialog(parent)
    dialog.setWindowTitle("PWMB 3D Viewer")
    dialog.resize(1120, 700)
    dialog.setMinimumSize(860, 560)

    initial_backend = get_geometry_backend()
    runner_strategy = _resolve_runner_strategy(backend_name=initial_backend.name)
    runner = TaskRunner(pool_kind=runner_strategy.pool_kind, workers=runner_strategy.workers)
    progress_queue: queue.SimpleQueue[tuple[str, int, str]] = queue.SimpleQueue()
    build_future: Future[_BuildJobResult] | None = None
    resolve_future: Future[Path | None] | None = None
    build_cancel_token: CancellationToken | None = None
    build_op_id: str | None = None
    build_source: Path | None = None
    contour_preview_ready = False
    restart_after_cancel = False
    last_error_text: str | None = None
    poll_timer = qtcore.QTimer(dialog)
    poll_timer.setInterval(80)
    settings = qtcore.QSettings(_VIEWER_SETTINGS_ORG, _VIEWER_SETTINGS_APP)

    emit_event(
        LOGGER_BUILD,
        logging.INFO,
        event="build.runner_strategy",
        msg="PWMB viewer runner strategy selected",
        component="render3d.build",
        data={
            "render3d": {
                "pool_kind": runner_strategy.pool_kind,
                "workers": int(runner_strategy.workers),
                "reason": runner_strategy.reason,
                "backend": initial_backend.name,
            }
        },
    )

    root = qtwidgets.QVBoxLayout(dialog)
    root.setContentsMargins(16, 16, 16, 16)
    root.setSpacing(10)

    title = qtwidgets.QLabel("PWMB 3D Viewer")
    title.setObjectName("title")
    subtitle = qtwidgets.QLabel("OpenGL viewport + progressive CPU build (contours first, fill pass second).")
    subtitle.setObjectName("subtitle")
    root.addWidget(title)
    root.addWidget(subtitle)

    split = qtwidgets.QHBoxLayout()
    split.setSpacing(10)
    root.addLayout(split, 1)

    controls = make_panel(parent=dialog, object_name="panel")
    controls.setMinimumWidth(320)
    form = qtwidgets.QFormLayout(controls)
    form.setContentsMargins(12, 12, 12, 12)
    form.setSpacing(10)

    source_row = qtwidgets.QHBoxLayout()
    source_edit = qtwidgets.QLineEdit()
    source_edit.setPlaceholderText("Select a local .pwmb file")
    source_row.addWidget(source_edit, 1)
    browse_btn = qtwidgets.QPushButton("Browse")
    source_row.addWidget(browse_btn)
    source_box = qtwidgets.QWidget()
    source_box.setLayout(source_row)
    form.addRow("PWMB file", source_box)

    threshold_spin = qtwidgets.QSpinBox()
    threshold_spin.setRange(0, 255)
    threshold_spin.setValue(1)
    form.addRow("Threshold", threshold_spin)

    bin_mode = qtwidgets.QComboBox()
    bin_mode.addItems(["index_strict", "threshold"])
    form.addRow("Binarization", bin_mode)

    cutoff_slider = qtwidgets.QSlider(qtcore.Qt.Orientation.Horizontal)
    cutoff_slider.setRange(0, 100)
    cutoff_slider.setValue(100)
    cutoff_value = qtwidgets.QLabel("L100 / 100")
    cutoff_value.setMinimumWidth(96)
    cutoff_value.setAlignment(qtcore.Qt.AlignmentFlag.AlignRight | qtcore.Qt.AlignmentFlag.AlignVCenter)
    cutoff_row = qtwidgets.QHBoxLayout()
    cutoff_row.setContentsMargins(0, 0, 0, 0)
    cutoff_row.setSpacing(8)
    cutoff_row.addWidget(cutoff_slider, 1)
    cutoff_row.addWidget(cutoff_value, 0)
    cutoff_box = qtwidgets.QWidget()
    cutoff_box.setLayout(cutoff_row)
    form.addRow("Layer cutoff", cutoff_box)

    stride_slider = qtwidgets.QSlider(qtcore.Qt.Orientation.Horizontal)
    stride_slider.setRange(1, 16)
    stride_slider.setValue(1)
    form.addRow("Stride Z", stride_slider)

    quality = qtwidgets.QComboBox()
    quality.addItems(["Interactive", "Balanced", "Full quality"])
    form.addRow("Quality", quality)

    contour_only = qtwidgets.QCheckBox("Contour only")
    form.addRow("", contour_only)

    info_label = qtwidgets.QLabel("Idle.")
    info_label.setObjectName("subtitle")
    info_label.setWordWrap(True)
    form.addRow("", info_label)

    progress = qtwidgets.QProgressBar()
    progress.setRange(0, 100)
    progress.setValue(0)
    progress.hide()
    form.addRow("Build", progress)

    split.addWidget(controls, 0)
    viewport_widget, viewport_type = _make_viewport(dialog)
    split.addWidget(viewport_widget, 1)

    buttons = qtwidgets.QHBoxLayout()
    rebuild_btn = qtwidgets.QPushButton("Rebuild preview")
    retry_btn = qtwidgets.QPushButton("Retry last build")
    retry_btn.setEnabled(False)
    cancel_btn = qtwidgets.QPushButton("Cancel build")
    cancel_btn.setEnabled(False)
    reset_btn = qtwidgets.QPushButton("Reset camera")
    export_btn = qtwidgets.QPushButton("Export screenshot")
    close_btn = qtwidgets.QPushButton("Close")
    close_btn.clicked.connect(dialog.reject)

    buttons.addWidget(rebuild_btn)
    buttons.addWidget(retry_btn)
    buttons.addWidget(cancel_btn)
    buttons.addWidget(reset_btn)
    buttons.addWidget(export_btn)
    buttons.addStretch(1)
    buttons.addWidget(close_btn)
    root.addLayout(buttons)

    def _set_busy(busy: bool, message: str | None = None) -> None:
        rebuild_btn.setEnabled(not busy)
        retry_btn.setEnabled(bool((not busy) and last_error_text))
        cancel_btn.setEnabled(bool(busy and build_future is not None and not build_future.done()))
        threshold_spin.setEnabled(not busy)
        bin_mode.setEnabled(not busy)
        progress.setVisible(busy)
        if not busy:
            progress.setValue(0)
        if message is not None:
            info_label.setText(message)

    def _read_setting_int(key: str, default: int) -> int:
        raw = settings.value(f"{_VIEWER_SETTINGS_PREFIX}/{key}", default)
        try:
            return int(raw)
        except Exception:
            return int(default)

    def _read_setting_bool(key: str, default: bool) -> bool:
        raw = settings.value(f"{_VIEWER_SETTINGS_PREFIX}/{key}", default)
        if isinstance(raw, bool):
            return raw
        text = str(raw).strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
        return bool(default)

    def _load_viewer_settings() -> None:
        threshold_spin.setValue(max(0, min(255, _read_setting_int("threshold", 1))))
        saved_bin_mode = str(settings.value(f"{_VIEWER_SETTINGS_PREFIX}/bin_mode", "index_strict")).strip()
        bin_index = max(0, bin_mode.findText(saved_bin_mode))
        bin_mode.setCurrentIndex(bin_index)
        stride_slider.setValue(max(1, min(16, _read_setting_int("stride_z", 1))))
        quality_index = max(0, min(quality.count() - 1, _read_setting_int("quality_index", 0)))
        quality.setCurrentIndex(quality_index)
        contour_only.setChecked(_read_setting_bool("contour_only", False))

    def _save_viewer_settings() -> None:
        settings.setValue(f"{_VIEWER_SETTINGS_PREFIX}/threshold", int(threshold_spin.value()))
        settings.setValue(f"{_VIEWER_SETTINGS_PREFIX}/bin_mode", bin_mode.currentText().strip())
        settings.setValue(f"{_VIEWER_SETTINGS_PREFIX}/stride_z", int(stride_slider.value()))
        settings.setValue(f"{_VIEWER_SETTINGS_PREFIX}/quality_index", int(quality.currentIndex()))
        settings.setValue(f"{_VIEWER_SETTINGS_PREFIX}/contour_only", bool(contour_only.isChecked()))
        settings.sync()

    def _format_build_error(exc: Exception) -> str:
        text = str(exc).strip()
        lowered = text.lower()
        if "opengl" in lowered or "gpu" in lowered or "shader" in lowered:
            return f"OpenGL renderer error: {text or type(exc).__name__}. Click Retry last build."
        if "decode" in lowered or "pw0" in lowered or "pws" in lowered:
            return f"PWMB decode error: {text or type(exc).__name__}. Click Retry last build."
        if "signature" in lowered or "table" in lowered or "file" in lowered or "parse" in lowered:
            return f"PWMB parse/open error: {text or type(exc).__name__}. Click Retry last build."
        return f"Build failed: {text or type(exc).__name__}. Click Retry last build."

    def _path_from_input() -> Path | None:
        text = source_edit.text().strip()
        if not text:
            return None
        return Path(text).expanduser()

    def _normalize_progress(*, phase: str, phase_percent: int) -> int:
        pct = max(0, min(100, int(phase_percent)))
        if phase == "contours":
            return max(0, min(45, int(round(pct * 0.45))))
        if phase == "fill":
            return max(45, min(100, 45 + int(round(pct * 0.55))))
        return pct

    def _apply_stage(phase: str, percent: int, stage: str) -> None:
        phase_pct = max(0, min(100, int(percent)))
        pct = _normalize_progress(phase=phase, phase_percent=phase_pct)
        label = _STAGE_LABELS.get(stage, f"Stage: {stage}")
        phase_label = _PHASE_LABELS.get(phase, phase)
        progress.setValue(pct)
        info_label.setText(f"{phase_label} - {label} ({pct}%)")
        emit_event(
            LOGGER_BUILD,
            logging.INFO,
            event="build.progressive",
            msg=f"PWMB build phase={phase} stage={stage} percent={pct}",
            component="render3d.build",
            op_id=build_op_id,
            data={"render3d": {"phase": phase, "stage": stage, "phase_percent": phase_pct, "percent": pct}},
        )

    def _drain_stage_updates() -> None:
        while True:
            try:
                phase, percent, stage = progress_queue.get_nowait()
            except queue.Empty:
                break
            _apply_stage(phase, percent, stage)

    def _apply_viewport_controls() -> None:
        if viewport_type is None:
            return
        force_full = quality.currentText().strip().lower().startswith("full")
        stride_value = max(1, stride_slider.value())
        if quality.currentText().strip().lower().startswith("balanced"):
            stride_value = max(1, stride_value // 2)

        viewport_widget.set_stride_z(stride_value)
        viewport_widget.set_force_full_quality(force_full)
        viewport_widget.set_contour_only(contour_only.isChecked())
        viewport_widget.set_layer_cutoff(cutoff_slider.value())

    def _refresh_cutoff_label() -> None:
        current = int(cutoff_slider.value())
        maximum = int(cutoff_slider.maximum())
        cutoff_value.setText(f"L{current} / {maximum}")

    def _ensure_polling() -> None:
        if not poll_timer.isActive():
            poll_timer.start()

    def _stop_polling_if_idle() -> None:
        if build_future is None and resolve_future is None and poll_timer.isActive():
            poll_timer.stop()

    def _apply_runner_strategy_for_backend(backend_name: str) -> None:
        nonlocal runner, runner_strategy
        strategy = _resolve_runner_strategy(backend_name=backend_name)
        if strategy.pool_kind == runner_strategy.pool_kind and strategy.workers == runner_strategy.workers:
            return
        if build_future is not None and not build_future.done():
            return
        if resolve_future is not None and not resolve_future.done():
            return
        runner.shutdown(wait=False, cancel_futures=False)
        runner = TaskRunner(pool_kind=strategy.pool_kind, workers=strategy.workers)
        runner_strategy = strategy
        emit_event(
            LOGGER_BUILD,
            logging.INFO,
            event="build.runner_strategy",
            msg="PWMB viewer runner strategy updated",
            component="render3d.build",
            data={
                "render3d": {
                    "pool_kind": runner_strategy.pool_kind,
                    "workers": int(runner_strategy.workers),
                    "reason": runner_strategy.reason,
                    "backend": backend_name,
                }
            },
        )

    def _cancel_current_build(*, restart: bool, message: str) -> bool:
        nonlocal restart_after_cancel
        if build_future is None or build_future.done():
            if not restart:
                restart_after_cancel = False
            return False
        restart_after_cancel = bool(restart)
        cancelled_before_start = build_future.cancel()
        if build_cancel_token is not None:
            build_cancel_token.cancel()
        emit_event(
            LOGGER_GUI,
            logging.WARNING,
            event="ui.cancel",
            msg="3D build cancellation requested",
            component="app.gui",
            op_id=build_op_id,
            data={
                "action": "viewer3d.cancel",
                "restart_after_cancel": bool(restart),
                "cancelled_before_start": bool(cancelled_before_start),
                "pool_kind": runner_strategy.pool_kind,
            },
        )
        _set_busy(True, message)
        cancel_btn.setEnabled(False)
        _ensure_polling()
        return True

    def _submit_build_phase(*, source: Path, phase: str, include_fill: bool) -> None:
        nonlocal build_future
        if build_op_id is None:
            raise RuntimeError("missing build operation id")
        if build_cancel_token is None and runner_strategy.pool_kind != "processes":
            raise RuntimeError("missing build cancellation token")
        progress_cb: Callable[[str, int, str], None] | None
        cancel_token_arg: object | None = build_cancel_token
        if runner_strategy.pool_kind == "processes":
            progress_cb = None
            cancel_token_arg = None
        else:
            progress_cb = lambda job_phase, percent, stage: progress_queue.put((job_phase, percent, stage))
        build_future = runner.submit(
            _build_geometry_job,
            source_path=str(source),
            threshold=int(threshold_spin.value()),
            bin_mode=bin_mode.currentText().strip(),
            phase=str(phase),
            include_fill=bool(include_fill),
            op_id=build_op_id,
            pool_kind=runner_strategy.pool_kind,
            workers=runner_strategy.workers,
            cancel_token=cancel_token_arg,
            progress_cb=progress_cb,
        )
        cancel_btn.setEnabled(True)
        _ensure_polling()

    def _start_build() -> None:
        nonlocal build_op_id, build_source, contour_preview_ready, build_cancel_token, restart_after_cancel, last_error_text
        source = _path_from_input()
        if source is None:
            info_label.setText("Select a .pwmb file first.")
            return
        if not source.exists() or not source.is_file():
            info_label.setText(f"File not found: {source}")
            return
        if source.suffix.lower() != ".pwmb":
            info_label.setText("Only .pwmb files are supported.")
            return
        if build_future is not None and not build_future.done():
            _cancel_current_build(
                restart=True,
                message="Cancelling current build before restart...",
            )
            return

        selected_backend = get_geometry_backend()
        _apply_runner_strategy_for_backend(selected_backend.name)
        build_source = source
        contour_preview_ready = False
        restart_after_cancel = False
        last_error_text = None
        retry_btn.setEnabled(False)
        _save_viewer_settings()
        build_cancel_token = CancellationToken() if runner_strategy.pool_kind == "threads" else None
        with operation_context() as op_id:
            build_op_id = op_id
            emit_event(
                LOGGER_GUI,
                logging.INFO,
                event="ui.action",
                msg="3D rebuild requested",
                component="app.gui",
                op_id=op_id,
                data={
                    "action": "viewer3d.rebuild",
                    "file_name": source.name,
                    "threshold": int(threshold_spin.value()),
                    "bin_mode": bin_mode.currentText().strip(),
                    "backend": selected_backend.name,
                    "pool_kind": runner_strategy.pool_kind,
                    "workers": int(runner_strategy.workers),
                },
            )
        if build_op_id is None:
            info_label.setText("Cannot start build: missing operation id.")
            return

        _set_busy(True, f"{_PHASE_LABELS['contours']} - {_STAGE_LABELS['read']}")
        progress.setValue(0)
        _submit_build_phase(source=source, phase="contours", include_fill=False)

    def _start_resolve() -> None:
        nonlocal resolve_future
        if resolve_pwmb_path is None:
            return
        if resolve_future is not None and not resolve_future.done():
            return
        _set_busy(True, "Resolving cloud file path...")
        progress.setValue(0)
        resolve_future = runner.submit(resolve_pwmb_path)
        _ensure_polling()

    def _handle_resolve_done() -> None:
        nonlocal resolve_future
        if resolve_future is None or not resolve_future.done():
            return
        future = resolve_future
        resolve_future = None
        try:
            resolved = future.result()
        except Exception as exc:
            _set_busy(False, f"Unable to prepare cloud file: {exc}")
            _stop_polling_if_idle()
            return
        if resolved is None:
            _set_busy(False, "Unable to locate cloud file locally. Use Browse to select a .pwmb file.")
            _stop_polling_if_idle()
            return
        source_edit.setText(str(resolved))
        _set_busy(False, f"Resolved file: {resolved.name}")
        _start_build()

    def _handle_build_done() -> None:
        nonlocal build_future, build_op_id, contour_preview_ready, build_source, build_cancel_token, restart_after_cancel, last_error_text
        if build_future is None or not build_future.done():
            return
        future = build_future
        build_future = None
        _drain_stage_updates()
        try:
            result = future.result()
        except CancelledError as exc:
            emit_event(
                LOGGER_GUI,
                logging.WARNING,
                event="ui.cancelled",
                msg="3D build cancelled",
                component="app.gui",
                op_id=build_op_id,
                error={"type": type(exc).__name__, "message": str(exc)},
            )
            should_restart = bool(restart_after_cancel)
            restart_after_cancel = False
            build_op_id = None
            build_source = None
            build_cancel_token = None
            if should_restart:
                contour_preview_ready = False
                _set_busy(False, "Previous build cancelled, restarting...")
                qtcore.QTimer.singleShot(0, _start_build)
            elif contour_preview_ready:
                _set_busy(False, "Contours preview kept, fill pass cancelled.")
            else:
                _set_busy(False, "Build cancelled.")
            _stop_polling_if_idle()
            return
        except Exception as exc:
            emit_event(
                LOGGER_GUI,
                logging.ERROR,
                event="ui.error",
                msg="3D build failed",
                component="app.gui",
                op_id=build_op_id,
                error={"type": type(exc).__name__, "message": str(exc)},
            )
            error_text = _format_build_error(exc)
            if contour_preview_ready:
                error_text = (
                    "Contours preview kept; fill pass failed. "
                    + _format_build_error(exc)
                )
            last_error_text = error_text
            _set_busy(False, error_text)
            build_op_id = None
            build_source = None
            build_cancel_token = None
            restart_after_cancel = False
            _stop_polling_if_idle()
            return

        if viewport_type is not None:
            viewport_widget.set_geometry(result.geometry, layer_ids=result.built_layer_ids)
            cutoff_max = max(result.document_layer_count - 1, result.built_layer_ids[-1] if result.built_layer_ids else 0)
            cutoff_slider.setRange(0, max(0, cutoff_max))
            cutoff_slider.setValue(cutoff_max)
            _refresh_cutoff_label()
            _apply_viewport_controls()
            renderer_error = viewport_widget.renderer_error_message()
            if renderer_error:
                last_error_text = f"OpenGL renderer error: {renderer_error}. Click Retry last build."
                _set_busy(False, last_error_text)
                build_op_id = None
                build_source = None
                build_cancel_token = None
                restart_after_cancel = False
                _stop_polling_if_idle()
                return
        _apply_stage(result.phase, 90, "upload")
        _apply_stage(result.phase, 100, "done")

        if build_cancel_token is not None and build_cancel_token.is_cancelled():
            should_restart = bool(restart_after_cancel)
            restart_after_cancel = False
            build_op_id = None
            build_source = None
            build_cancel_token = None
            if should_restart:
                contour_preview_ready = False
                _set_busy(False, "Previous build cancelled, restarting...")
                qtcore.QTimer.singleShot(0, _start_build)
            elif contour_preview_ready:
                _set_busy(False, "Contours preview kept, fill pass cancelled.")
            else:
                _set_busy(False, "Build cancelled.")
            _stop_polling_if_idle()
            return

        if not result.include_fill:
            contour_preview_ready = True
            last_error_text = None
            info_label.setText(
                "Contours ready "
                f"({Path(result.source_path).name}, layers={len(result.built_layer_ids)}/{result.document_layer_count}, "
                f"xy_stride={result.xy_stride}, z_stride={result.z_stride}) - triangulating fill pass..."
            )
            source = build_source or Path(result.source_path)
            _submit_build_phase(source=source, phase="fill", include_fill=True)
            return

        contour_preview_ready = False
        restart_after_cancel = False
        last_error_text = None
        _set_busy(False)
        info_label.setText(
            "Loaded "
            f"{Path(result.source_path).name} | "
            f"backend={result.backend_name} | "
            f"phase=progressive(contours->fill) | "
            f"layers={len(result.built_layer_ids)}/{result.document_layer_count} | "
            f"xy_stride={result.xy_stride} | "
            f"z_stride={result.z_stride} | "
            f"tris={len(result.geometry.triangle_vertices) // 3} | "
            f"cache(contours={result.contour_cache_hit}, geometry={result.geometry_cache_hit})"
        )
        build_op_id = None
        build_source = None
        build_cancel_token = None
        _stop_polling_if_idle()

    def _poll_async() -> None:
        _drain_stage_updates()
        _handle_resolve_done()
        _handle_build_done()
        _stop_polling_if_idle()

    def _browse_source() -> None:
        selected, _flt = qtwidgets.QFileDialog.getOpenFileName(
            dialog,
            "Select PWMB file",
            str(Path.home() / "Downloads"),
            "PWMB files (*.pwmb);;All files (*)",
        )
        if not selected:
            return
        source_edit.setText(selected)
        _set_busy(False, f"Selected file: {Path(selected).name}")

    def _reset_camera() -> None:
        if viewport_type is None:
            return
        viewport_widget.reset_camera()

    def _export_screenshot() -> None:
        if viewport_type is None:
            qtwidgets.QMessageBox.information(dialog, "Screenshot", "OpenGL viewport is unavailable.")
            return
        image = viewport_widget.grabFramebuffer()
        if image.isNull():
            qtwidgets.QMessageBox.warning(dialog, "Screenshot", "Failed to capture framebuffer.")
            return
        default_name = "pwmb_viewer.png"
        selected, _flt = qtwidgets.QFileDialog.getSaveFileName(
            dialog,
            "Export screenshot",
            str(Path.home() / "Downloads" / default_name),
            "PNG image (*.png)",
        )
        if not selected:
            return
        if not image.save(selected):
            qtwidgets.QMessageBox.warning(dialog, "Screenshot", f"Cannot save screenshot:\n{selected}")
            return
        info_label.setText(f"Screenshot exported to {selected}")

    def _cancel_build() -> None:
        _cancel_current_build(restart=False, message="Build cancellation requested...")

    def _retry_last_build() -> None:
        if build_future is not None and not build_future.done():
            _cancel_current_build(
                restart=True,
                message="Cancelling current build before retry...",
            )
            return
        if not last_error_text:
            info_label.setText("No failed build to retry.")
            return
        _start_build()

    def _cleanup() -> None:
        nonlocal build_cancel_token
        if poll_timer.isActive():
            poll_timer.stop()
        _save_viewer_settings()
        if build_cancel_token is not None:
            build_cancel_token.cancel()
            build_cancel_token = None
        runner.shutdown(wait=False, cancel_futures=True)

    _load_viewer_settings()
    _apply_viewport_controls()
    browse_btn.clicked.connect(_browse_source)
    rebuild_btn.clicked.connect(_start_build)
    retry_btn.clicked.connect(_retry_last_build)
    cancel_btn.clicked.connect(_cancel_build)
    reset_btn.clicked.connect(_reset_camera)
    export_btn.clicked.connect(_export_screenshot)
    poll_timer.timeout.connect(_poll_async)
    cutoff_slider.valueChanged.connect(lambda _v: (_refresh_cutoff_label(), _apply_viewport_controls()))
    stride_slider.valueChanged.connect(lambda _v: (_apply_viewport_controls(), _save_viewer_settings()))
    quality.currentIndexChanged.connect(lambda _i: (_apply_viewport_controls(), _save_viewer_settings()))
    contour_only.stateChanged.connect(lambda _v: (_apply_viewport_controls(), _save_viewer_settings()))
    threshold_spin.valueChanged.connect(lambda _v: _save_viewer_settings())
    bin_mode.currentTextChanged.connect(lambda _text: _save_viewer_settings())
    dialog.finished.connect(lambda _code: _cleanup())

    if pwmb_path is not None:
        source_edit.setText(str(Path(pwmb_path).expanduser()))
    elif file_label:
        source_edit.setPlaceholderText(f"No local file for {file_label}. Use Browse to open one.")

    if pwmb_path is not None:
        qtcore.QTimer.singleShot(0, _start_build)
    elif resolve_pwmb_path is not None:
        qtcore.QTimer.singleShot(0, _start_resolve)
    else:
        if file_label:
            info_label.setText(f"Open 3D viewer for {file_label}. Select a local .pwmb file to render.")
        else:
            info_label.setText("Select a local .pwmb file then click Rebuild preview.")
    _refresh_cutoff_label()
    return dialog
