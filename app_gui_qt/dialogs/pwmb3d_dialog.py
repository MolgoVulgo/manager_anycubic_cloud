from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app_gui_qt.qt_compat import require_qt
from app_gui_qt.widgets import make_panel
from pwmb_core import read_pwmb_document
from render3d_core import build_contour_stack, build_geometry_v2
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


@dataclass(slots=True)
class _BuildJobResult:
    geometry: PwmbContourGeometry
    built_layer_ids: list[int]
    document_layer_count: int
    source_path: str


def _build_geometry_job(
    *,
    source_path: str,
    threshold: int,
    bin_mode: str,
) -> _BuildJobResult:
    document = read_pwmb_document(source_path)
    stack = build_contour_stack(
        document,
        threshold=threshold,
        binarization_mode=bin_mode,
    )
    geometry = build_geometry_v2(
        stack,
        max_layers=None,
        max_vertices=None,
        max_xy_stride=1,
    )
    return _BuildJobResult(
        geometry=geometry,
        built_layer_ids=sorted(stack.layers.keys()),
        document_layer_count=len(document.layers),
        source_path=source_path,
    )


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
        from PySide6 import QtGui, QtOpenGLWidgets  # type: ignore
    except ImportError:
        return _build_viewport_placeholder(parent=parent), None

    class PwmbOpenGLViewport(QtOpenGLWidgets.QOpenGLWidget):  # type: ignore[misc]
        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self.setObjectName("pwmbViewport")
            self.setMinimumSize(480, 360)
            self.setMouseTracking(True)
            self._program: QtGui.QOpenGLShaderProgram | None = None
            self._funcs = None
            self._shader_error: str | None = None

            self._vbo_tri = QtGui.QOpenGLBuffer(QtGui.QOpenGLBuffer.Type.VertexBuffer)
            self._vbo_line = QtGui.QOpenGLBuffer(QtGui.QOpenGLBuffer.Type.VertexBuffer)
            self._vbo_point = QtGui.QOpenGLBuffer(QtGui.QOpenGLBuffer.Type.VertexBuffer)

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

        def initializeGL(self) -> None:  # noqa: N802
            self._funcs = self.context().functions()
            self._funcs.glEnable(GL_DEPTH_TEST)
            self._funcs.glEnable(GL_BLEND)
            self._funcs.glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

            program = QtGui.QOpenGLShaderProgram(self)
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
            if not program.addShaderFromSourceCode(QtGui.QOpenGLShader.ShaderTypeBit.Vertex, vertex_shader):
                self._shader_error = program.log()
                return
            if not program.addShaderFromSourceCode(QtGui.QOpenGLShader.ShaderTypeBit.Fragment, fragment_shader):
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
            if not draw_layers:
                return

            self._program.bind()
            self._program.setUniformValue("u_mvp", mvp)

            if not self._contour_only:
                self._program.setUniformValue("u_color", QtGui.QVector4D(0.23, 0.85, 0.70, 0.52))
                self._draw_buffer(
                    vbo=self._vbo_tri,
                    mode=GL_TRIANGLES,
                    ranges=self._geometry.tri_range,
                    layers=draw_layers,
                )

            self._program.setUniformValue("u_color", QtGui.QVector4D(0.05, 0.95, 0.85, 1.0))
            self._draw_buffer(
                vbo=self._vbo_line,
                mode=GL_LINES,
                ranges=self._geometry.line_range,
                layers=draw_layers,
            )
            self._program.setUniformValue("u_color", QtGui.QVector4D(0.95, 0.95, 0.95, 1.0))
            self._draw_buffer(
                vbo=self._vbo_point,
                mode=GL_POINTS,
                ranges=self._geometry.point_range,
                layers=draw_layers,
            )
            self._program.release()

        def _upload_gpu_buffers(self) -> None:
            self._upload_single_buffer(self._vbo_tri, self._geometry.triangle_vertices)
            self._upload_single_buffer(self._vbo_line, self._geometry.line_vertices)
            self._upload_single_buffer(self._vbo_point, self._geometry.point_vertices)
            self._layer_z = self._build_layer_z_map()
            self._fit_camera_to_geometry()

        def _upload_single_buffer(self, vbo, vertices: list[tuple[float, float, float, float]]) -> None:
            if not vbo.isCreated():
                vbo.create()
            array = (
                np.asarray(vertices, dtype=np.float32).reshape((-1, 4))
                if vertices
                else np.zeros((0, 4), dtype=np.float32)
            )
            vbo.bind()
            vbo.allocate(array.tobytes(), int(array.nbytes))
            vbo.release()

        def _draw_buffer(
            self,
            *,
            vbo,
            mode: int,
            ranges: dict[int, LayerRange],
            layers: list[int],
        ) -> None:
            if self._funcs is None or self._program is None:
                return
            vbo.bind()
            self._program.enableAttributeArray(0)
            self._program.setAttributeBuffer(0, GL_FLOAT, 0, 4, 16)
            if mode == GL_LINES:
                self._funcs.glLineWidth(1.0)
            elif mode == GL_POINTS:
                self._funcs.glPointSize(2.0)
            for layer_id in layers:
                layer_range = ranges.get(layer_id)
                if layer_range is None or layer_range.count <= 0:
                    continue
                self._funcs.glDrawArrays(mode, layer_range.start, layer_range.count)
            self._program.disableAttributeArray(0)
            vbo.release()

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
            self.update()

        def set_layer_cutoff(self, value: int) -> None:
            self._layer_cutoff = int(value)
            self.update()

        def set_stride_z(self, value: int) -> None:
            self._stride_z = max(1, int(value))
            self.update()

        def set_force_full_quality(self, enabled: bool) -> None:
            self._force_full_quality = bool(enabled)
            self.update()

        def set_contour_only(self, enabled: bool) -> None:
            self._contour_only = bool(enabled)
            self.update()

        def reset_camera(self) -> None:
            self._yaw_deg = -35.0
            self._pitch_deg = 28.0
            self._fit_camera_to_geometry()
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
                self.update()
            super().mouseMoveEvent(event)

        def wheelEvent(self, event) -> None:  # noqa: N802
            delta = event.angleDelta().y()
            factor = 0.9 if delta > 0 else 1.1
            self._distance = max(0.25, min(5000.0, self._distance * factor))
            self.update()
            super().wheelEvent(event)

    return PwmbOpenGLViewport(parent=parent), PwmbOpenGLViewport


def build_pwmb3d_dialog(parent=None, *, pwmb_path: str | Path | None = None, file_label: str | None = None):
    qtcore, qtwidgets = require_qt()
    dialog = qtwidgets.QDialog(parent)
    dialog.setWindowTitle("PWMB 3D Viewer")
    dialog.resize(1120, 700)
    dialog.setMinimumSize(860, 560)

    runner = TaskRunner(pool_kind="threads", workers=1)
    build_future: Future[_BuildJobResult] | None = None
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
    progress.setRange(0, 0)
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
        browse_btn.setEnabled(not busy)
        source_edit.setEnabled(not busy)
        threshold_spin.setEnabled(not busy)
        bin_mode.setEnabled(not busy)
        progress.setVisible(busy)
        if message is not None:
            info_label.setText(message)

    def _path_from_input() -> Path | None:
        text = source_edit.text().strip()
        if not text:
            return None
        return Path(text).expanduser()

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

    def _poll_build() -> None:
        nonlocal build_future
        if build_future is None:
            return
        if not build_future.done():
            return
        poll_timer.stop()
        future = build_future
        build_future = None
        _set_busy(False)
        try:
            result = future.result()
        except Exception as exc:
            info_label.setText(f"Build failed: {exc}")
            return

        if viewport_type is not None:
            viewport_widget.set_geometry(result.geometry, layer_ids=result.built_layer_ids)
            cutoff_max = max(result.document_layer_count - 1, result.built_layer_ids[-1] if result.built_layer_ids else 0)
            cutoff_slider.setRange(0, max(0, cutoff_max))
            cutoff_slider.setValue(cutoff_max)
            _apply_viewport_controls()
        info_label.setText(
            "Loaded "
            f"{Path(result.source_path).name} | "
            f"layers built={len(result.built_layer_ids)} / {result.document_layer_count} | "
            f"triangles={len(result.geometry.triangle_vertices) // 3}"
        )

    def _start_build() -> None:
        nonlocal build_future
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

        _set_busy(True, "Building 3D geometry...")
        build_future = runner.submit(
            _build_geometry_job,
            source_path=str(source),
            threshold=int(threshold_spin.value()),
            bin_mode=bin_mode.currentText().strip(),
        )
        poll_timer.start()

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
    poll_timer.timeout.connect(_poll_build)
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
    else:
        if file_label:
            info_label.setText(f"Open 3D viewer for {file_label}. Select a local .pwmb file to render.")
        else:
            info_label.setText("Select a local .pwmb file then click Rebuild preview.")
    return dialog
