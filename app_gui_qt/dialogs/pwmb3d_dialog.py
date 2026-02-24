from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass
import logging
import queue
from pathlib import Path
from time import perf_counter

import numpy as np

from accloud_core.logging_contract import emit_event, operation_context
from app_gui_qt.qt_compat import require_qt
from app_gui_qt.widgets import make_panel
from pwmb_core import read_pwmb_document
from pwmb_core.decode_pws import select_pws_convention
from render3d_core import (
    BuildCache,
    BuildMetrics,
    GpuMetrics,
    build_contour_stack,
    build_geometry_v2,
    compute_file_signature,
    make_cache_key,
)
from render3d_core.task_runner import TaskRunner
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


@dataclass(slots=True)
class _BuildJobResult:
    geometry: PwmbContourGeometry
    built_layer_ids: list[int]
    document_layer_count: int
    source_path: str
    xy_stride: int
    metrics: BuildMetrics
    contour_cache_hit: bool
    geometry_cache_hit: bool


def _select_preview_xy_stride(*, width: int, height: int) -> int:
    pixels = max(0, int(width)) * max(0, int(height))
    if pixels >= 24_000_000:
        return 6
    if pixels >= 12_000_000:
        return 4
    if pixels >= 6_000_000:
        return 3
    if pixels >= 2_500_000:
        return 2
    return 1


def _build_geometry_job(
    *,
    source_path: str,
    threshold: int,
    bin_mode: str,
    op_id: str,
    progress_cb: Callable[[int, str], None] | None = None,
) -> _BuildJobResult:
    metrics = BuildMetrics(pool_kind="threads", workers=1)

    def _stage(percent: int, stage: str) -> None:
        pct = max(0, min(100, int(percent)))
        if progress_cb is not None:
            progress_cb(pct, stage)
        LOGGER_BUILD.info("PWMB build stage=%s percent=%d", stage, pct)

    with operation_context(op_id):
        _stage(5, "read")
        parse_start = perf_counter()
        document = read_pwmb_document(source_path)
        _ensure_pws_convention(document)
        metrics.parse_ms = (perf_counter() - parse_start) * 1000.0
        xy_stride = _select_preview_xy_stride(width=document.width, height=document.height)

        emit_event(
            LOGGER_BUILD,
            logging.INFO,
            event="build.profile",
            msg="PWMB viewer build profile selected",
            component="render3d.build",
            op_id=op_id,
            data={
                "pwmb": {"W": document.width, "H": document.height},
                "render3d": {"xy_stride": xy_stride},
            },
        )

        file_signature = compute_file_signature(source_path)
        contour_key = make_cache_key(
            document,
            threshold=threshold,
            bin_mode=bin_mode,
            xy_stride=xy_stride,
            z_stride=1,
            simplify_epsilon=0.0,
            max_layers=None,
            max_vertices=None,
            render_mode="contours",
            file_signature=file_signature,
        )
        geometry_key = make_cache_key(
            document,
            threshold=threshold,
            bin_mode=bin_mode,
            xy_stride=xy_stride,
            z_stride=1,
            simplify_epsilon=0.0,
            max_layers=None,
            max_vertices=None,
            render_mode="fill",
            file_signature=file_signature,
        )

        _stage(12, "cache")
        contour_stack = _VIEWER_BUILD_CACHE.get_contours(contour_key)
        contour_cache_hit = contour_stack is not None
        if contour_cache_hit:
            _stage(25, "cache")
        else:
            _stage(22, "decode")
            _stage(46, "contours")
            contour_stack = build_contour_stack(
                document,
                threshold=threshold,
                binarization_mode=bin_mode,
                xy_stride=xy_stride,
                metrics=metrics,
            )
            _VIEWER_BUILD_CACHE.set_contours(contour_key, contour_stack)

        _stage(58, "cache")
        geometry = _VIEWER_BUILD_CACHE.get_geometry(geometry_key)
        geometry_cache_hit = geometry is not None
        if geometry_cache_hit:
            _stage(78, "cache")
        else:
            _stage(72, "geometry")
            geometry = build_geometry_v2(
                contour_stack,
                max_layers=None,
                max_vertices=None,
                max_xy_stride=1,
                metrics=metrics,
            )
            _VIEWER_BUILD_CACHE.set_geometry(geometry_key, geometry)

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
                    "xy_stride": xy_stride,
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
            xy_stride=xy_stride,
            metrics=metrics,
            contour_cache_hit=contour_cache_hit,
            geometry_cache_hit=geometry_cache_hit,
        )


def _ensure_pws_convention(document) -> None:
    if "pws" not in document.machine.layer_image_format.lower():
        return
    if document.pws_convention:
        return
    width = document.width
    height = document.height
    aa = max(1, int(document.header.anti_aliasing))
    for layer in document.layers:
        if layer.data_length <= 0:
            continue
        with document.path.open("rb") as handle:
            handle.seek(layer.data_address)
            blob = handle.read(layer.data_length)
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
            self._funcs = self.context().functions()
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
                return
            if not program.addShaderFromSourceCode(qopengl_shader.ShaderTypeBit.Fragment, fragment_shader):
                self._shader_error = program.log()
                return
            if not program.link():
                self._shader_error = program.log()
                return
            self._program = program

            self._vbo_tri.create()
            self._vbo_line.create()
            self._vbo_point.create()
            self._gpu_dirty = True

        def resizeGL(self, width: int, height: int) -> None:  # noqa: N802
            if self._funcs is not None:
                self._funcs.glViewport(0, 0, max(1, width), max(1, height))

        def paintGL(self) -> None:  # noqa: N802
            if self._funcs is None:
                return
            self._funcs.glClearColor(0.05, 0.11, 0.10, 1.0)
            self._funcs.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            if self._shader_error or self._program is None:
                return

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
                    "PWMB draw mode=%s visible_layers=%d",
                    "contours" if self._contour_only else "fill",
                    len(draw_layers),
                )
                emit_event(
                    LOGGER_GPU,
                    logging.INFO,
                    event="gpu.draw",
                    msg="PWMB GPU draw metrics",
                    component="render3d.gpu",
                    data={"render3d": self._gpu_metrics.as_log_data()},
                )
                self._log_next_draw = False

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

        def _upload_single_buffer(self, vbo, vertices: list[tuple[float, float, float, float]]) -> int:
            if not vbo.isCreated():
                vbo.create()
            array = (
                np.asarray(vertices, dtype=np.float32).reshape((-1, 4))
                if vertices
                else np.zeros((0, 4), dtype=np.float32)
            )
            payload = array.tobytes()
            vbo.bind()
            vbo.allocate(payload, int(len(payload)))
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
            return sorted(
                layers,
                key=lambda layer_id: self._layer_z.get(layer_id, 0.0),
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
            vertices: list[tuple[float, float, float, float]],
        ) -> float | None:
            layer_range = ranges.get(layer_id)
            if layer_range is None or layer_range.count <= 0:
                return None
            if layer_range.start < 0 or layer_range.start >= len(vertices):
                return None
            return float(vertices[layer_range.start][2])

        def _fit_camera_to_geometry(self) -> None:
            cloud: list[tuple[float, float, float, float]] = []
            cloud.extend(self._geometry.triangle_vertices)
            cloud.extend(self._geometry.line_vertices)
            cloud.extend(self._geometry.point_vertices)
            if not cloud:
                self._center = QtGui.QVector3D(0.0, 0.0, 0.0)
                self._distance = 6.0
                return
            arr = np.asarray(cloud, dtype=np.float32).reshape((-1, 4))
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

    runner = TaskRunner(pool_kind="threads", workers=2)
    progress_queue: queue.SimpleQueue[tuple[int, str]] = queue.SimpleQueue()
    build_future: Future[_BuildJobResult] | None = None
    resolve_future: Future[Path | None] | None = None
    build_op_id: str | None = None
    poll_timer = qtcore.QTimer(dialog)
    poll_timer.setInterval(80)

    root = qtwidgets.QVBoxLayout(dialog)
    root.setContentsMargins(16, 16, 16, 16)
    root.setSpacing(10)

    title = qtwidgets.QLabel("PWMB 3D Viewer")
    title.setObjectName("title")
    subtitle = qtwidgets.QLabel("OpenGL viewport + build CPU async (contours -> geometry -> upload).")
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
    form.addRow("Layer cutoff", cutoff_slider)

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
    reset_btn = qtwidgets.QPushButton("Reset camera")
    export_btn = qtwidgets.QPushButton("Export screenshot")
    close_btn = qtwidgets.QPushButton("Close")
    close_btn.clicked.connect(dialog.reject)

    buttons.addWidget(rebuild_btn)
    buttons.addWidget(reset_btn)
    buttons.addWidget(export_btn)
    buttons.addStretch(1)
    buttons.addWidget(close_btn)
    root.addLayout(buttons)

    def _set_busy(busy: bool, message: str | None = None) -> None:
        rebuild_btn.setEnabled(not busy)
        threshold_spin.setEnabled(not busy)
        bin_mode.setEnabled(not busy)
        progress.setVisible(busy)
        if not busy:
            progress.setValue(0)
        if message is not None:
            info_label.setText(message)

    def _path_from_input() -> Path | None:
        text = source_edit.text().strip()
        if not text:
            return None
        return Path(text).expanduser()

    def _apply_stage(percent: int, stage: str) -> None:
        pct = max(0, min(100, int(percent)))
        label = _STAGE_LABELS.get(stage, f"Stage: {stage}")
        progress.setValue(pct)
        info_label.setText(f"{label} ({pct}%)")
        emit_event(
            LOGGER_BUILD,
            logging.INFO,
            event="build.progress",
            msg=f"PWMB build stage={stage} percent={pct}",
            component="render3d.build",
            op_id=build_op_id,
            data={"render3d": {"stage": stage, "percent": pct}},
        )

    def _drain_stage_updates() -> None:
        while True:
            try:
                percent, stage = progress_queue.get_nowait()
            except queue.Empty:
                break
            _apply_stage(percent, stage)

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

    def _ensure_polling() -> None:
        if not poll_timer.isActive():
            poll_timer.start()

    def _stop_polling_if_idle() -> None:
        if build_future is None and resolve_future is None and poll_timer.isActive():
            poll_timer.stop()

    def _start_build() -> None:
        nonlocal build_future, build_op_id
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
            info_label.setText("A build is already running.")
            return

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
                },
            )
        if build_op_id is None:
            info_label.setText("Cannot start build: missing operation id.")
            return

        _set_busy(True, _STAGE_LABELS["read"])
        progress.setValue(0)
        build_future = runner.submit(
            _build_geometry_job,
            source_path=str(source),
            threshold=int(threshold_spin.value()),
            bin_mode=bin_mode.currentText().strip(),
            op_id=build_op_id,
            progress_cb=lambda percent, stage: progress_queue.put((percent, stage)),
        )
        _ensure_polling()

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
        nonlocal build_future, build_op_id
        if build_future is None or not build_future.done():
            return
        future = build_future
        build_future = None
        _drain_stage_updates()
        _set_busy(False)
        try:
            result = future.result()
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
            info_label.setText(f"Build failed: {exc}")
            build_op_id = None
            _stop_polling_if_idle()
            return

        _apply_stage(90, "upload")
        if viewport_type is not None:
            viewport_widget.set_geometry(result.geometry, layer_ids=result.built_layer_ids)
            cutoff_max = max(result.document_layer_count - 1, result.built_layer_ids[-1] if result.built_layer_ids else 0)
            cutoff_slider.setRange(0, max(0, cutoff_max))
            cutoff_slider.setValue(cutoff_max)
            _apply_viewport_controls()
        _apply_stage(100, "done")
        info_label.setText(
            "Loaded "
            f"{Path(result.source_path).name} | "
            f"layers={len(result.built_layer_ids)}/{result.document_layer_count} | "
            f"xy_stride={result.xy_stride} | "
            f"tris={len(result.geometry.triangle_vertices) // 3} | "
            f"cache(contours={result.contour_cache_hit}, geometry={result.geometry_cache_hit})"
        )
        build_op_id = None
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

    def _cleanup() -> None:
        if poll_timer.isActive():
            poll_timer.stop()
        runner.shutdown(wait=False, cancel_futures=True)

    browse_btn.clicked.connect(_browse_source)
    rebuild_btn.clicked.connect(_start_build)
    reset_btn.clicked.connect(_reset_camera)
    export_btn.clicked.connect(_export_screenshot)
    poll_timer.timeout.connect(_poll_async)
    cutoff_slider.valueChanged.connect(lambda _v: _apply_viewport_controls())
    stride_slider.valueChanged.connect(lambda _v: _apply_viewport_controls())
    quality.currentIndexChanged.connect(lambda _i: _apply_viewport_controls())
    contour_only.stateChanged.connect(lambda _v: _apply_viewport_controls())
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
    return dialog
