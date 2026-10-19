"""
image_viewer.py
Widget penampil citra kamera/foto dengan rendering cepat QPixmap,
penyesuaian rasio aspek otomatis, dan penangkapan interaksi klik kursor.
"""

from typing import Optional, Tuple
import numpy as np
import cv2
from PyQt5.QtWidgets import (
    QLabel, QSizePolicy, QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QGraphicsView, QGraphicsScene, QFrame, QPinchGesture,
    QGraphicsPathItem, QGraphicsEllipseItem, QToolTip,
)
from PyQt5.QtGui import QImage, QPixmap, QPainter, QColor, QFont, QPen, QPainterPath
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QRect, QRectF, QTimer, QEvent


class ZoomableGraphicsView(QGraphicsView):
    """Penampil gambar besar dengan zoom roda mouse dan pan lewat drag."""

    zoom_changed = pyqtSignal(int)
    horizon_edited = pyqtSignal(object)
    add_object_requested = pyqtSignal(int, int)
    obstacle_clicked = pyqtSignal(int, object)
    obstacle_range_edited = pyqtSignal(int, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = None
        self._zoom_steps = 0
        self._pinch_last_scale = 1.0
        self._horizon_items = []
        self._overlay_reference_scale = None
        self._horizon_data = None
        self._obstacles = []
        self._selected_range = None
        self._target_x = None
        self._interaction_mode = "navigate"
        self._control_items = []
        self._control_points = []
        self._drag_control_index = None
        self._drag_start_horizon = None
        self._drag_start_point = None
        self._span_items = []
        self._span_handles = []
        self._drag_span_handle = None
        self.setBackgroundBrush(QColor("#07090d"))
        self.setFrameShape(QFrame.NoFrame)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        # Qt mengirim pinch trackpad sebagai QGesture pada sebagian platform dan
        # NativeGesture pada macOS. Keduanya ditangani agar perilakunya konsisten.
        self.viewport().grabGesture(Qt.PinchGesture)

    def set_pixmap(self, pixmap: QPixmap):
        self._scene.clear()
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self.reset_zoom()

    @staticmethod
    def _path_from_horizon(horizon_y: np.ndarray, x_start: int, x_end: int) -> QPainterPath:
        path = QPainterPath()
        if x_end < x_start:
            return path
        path.moveTo(float(x_start), float(horizon_y[x_start]))
        for x in range(x_start + 1, x_end + 1):
            path.lineTo(float(x), float(horizon_y[x]))
        return path

    def set_horizon_overlay(
        self,
        horizon_y: np.ndarray,
        selected_range: Optional[Tuple[int, int]] = None,
        target_x: Optional[int] = None,
        obstacles: Optional[list] = None,
    ):
        """Gambar seluruh garis inspeksi sebagai layer vektor dinamis."""
        for handle in self._span_handles:
            if handle.scene() is self._scene:
                self._scene.removeItem(handle)
        for item in self._horizon_items:
            self._scene.removeItem(item)
        self._horizon_items = []
        self._span_items = []
        self._span_handles = []
        if self._pixmap_item is None:
            return

        width = int(round(self._pixmap_item.boundingRect().width()))
        horizon = np.asarray(horizon_y, dtype=np.float64)
        if width <= 1 or len(horizon) < width:
            return
        horizon = np.clip(horizon[:width], 0, self._pixmap_item.boundingRect().height() - 1)
        self._horizon_data = horizon.copy()
        self._obstacles = list(obstacles or [])
        self._selected_range = selected_range
        self._target_x = target_x

        # Tanpa objek terpilih, pertahankan warna kuning kontur utama. Saat
        # objek dipilih, kontur umum diredupkan menjadi abu-abu.
        base_role = "gray" if selected_range is not None else "horizon"
        base_item = QGraphicsPathItem(self._path_from_horizon(horizon, 0, width - 1))
        base_item.setZValue(10)
        base_item.setData(0, base_role)
        self._scene.addItem(base_item)
        self._horizon_items.append(base_item)

        # Hanya rentang azimut/objek yang dipilih diberi warna merah.
        if selected_range is not None:
            xs = max(0, min(width - 1, int(selected_range[0])))
            xe = max(0, min(width - 1, int(selected_range[1])))
            if xe < xs:
                xs, xe = xe, xs
            # Sedikit margin agar batas seleksi mudah terlihat tetapi tetap
            # mengikuti lebar objek hasil deteksi.
            margin = max(1, int(round(width * 0.0015)))
            xs, xe = max(0, xs - margin), min(width - 1, xe + margin)
            red_item = QGraphicsPathItem(self._path_from_horizon(horizon, xs, xe))
            red_item.setZValue(11)
            red_item.setData(0, "selected")
            self._scene.addItem(red_item)
            self._horizon_items.append(red_item)

        # Meridian azimut target juga berupa vektor, bukan garis yang tertanam
        # pada bitmap, sehingga ketebalannya ikut beradaptasi saat zoom.
        if target_x is not None and 0 <= int(target_x) < width:
            tx = int(target_x)
            target_path = QPainterPath()
            target_path.moveTo(float(tx), 0.0)
            target_path.lineTo(float(tx), float(self._pixmap_item.boundingRect().height()))
            target_item = QGraphicsPathItem(target_path)
            target_item.setZValue(9)
            target_item.setData(0, "target")
            self._scene.addItem(target_item)
            self._horizon_items.append(target_item)

        # Penanda rentang semua objek. Dalam mode fokus hanya objek terpilih
        # yang ditampilkan agar area pengamatan tidak ramai.
        for obstacle_index, obstacle in enumerate(obstacles or []):
            xs = obstacle.get("x_start")
            xe = obstacle.get("x_end")
            py = obstacle.get("y")
            if not all(isinstance(value, (int, float)) for value in (xs, xe, py)):
                continue
            xs, xe = int(xs), int(xe)
            if xe < xs:
                xs, xe = xe, xs
            xs, xe = max(0, xs), min(width - 1, xe)
            if selected_range is not None:
                sel0, sel1 = sorted((int(selected_range[0]), int(selected_range[1])))
                if xe < sel0 or xs > sel1:
                    continue
            span_y = min(float(self._pixmap_item.boundingRect().height() - 1), float(py) + 14.0)
            tick = 7.0
            bracket = QPainterPath()
            bracket.moveTo(float(xs), span_y)
            bracket.lineTo(float(xe), span_y)
            bracket.moveTo(float(xs), span_y - tick)
            bracket.lineTo(float(xs), span_y + tick)
            bracket.moveTo(float(xe), span_y - tick)
            bracket.lineTo(float(xe), span_y + tick)
            bracket_item = QGraphicsPathItem(bracket)
            bracket_item.setZValue(12)
            bracket_item.setData(0, "selected_span" if selected_range is not None else "span")
            bracket_item.setData(1, obstacle_index)
            self._scene.addItem(bracket_item)
            self._horizon_items.append(bracket_item)
            self._span_items.append((bracket_item, obstacle_index))

            # Handle kiri/kanan memungkinkan penanda H diperkecil/diperlebar.
            for side, hx in (("left", xs), ("right", xe)):
                handle = QGraphicsEllipseItem()
                handle.setZValue(31)
                handle.setData(0, "span_handle")
                handle.setData(1, obstacle_index)
                handle.setData(2, side)
                handle.setData(3, span_y)
                handle.setData(4, hx)
                handle.setBrush(QColor(56, 189, 248, 235))
                handle.setVisible(self._interaction_mode == "edit_horizon")
                self._scene.addItem(handle)
                self._span_handles.append(handle)

        self._overlay_reference_scale = max(1e-6, self.transform().m11())
        self._update_horizon_pen_widths()
        if self._interaction_mode == "edit_horizon":
            self._build_pen_control_points()

    def _clear_pen_control_points(self):
        for item in self._control_items:
            if item.scene() is self._scene:
                self._scene.removeItem(item)
        self._control_items = []
        self._control_points = []

    def _build_pen_control_points(self):
        """Buat anchor Pen Tool pada sudut/perubahan arah penting kontur."""
        self._clear_pen_control_points()
        if self._horizon_data is None or len(self._horizon_data) < 2:
            return
        width = len(self._horizon_data)
        points = np.column_stack((np.arange(width), self._horizon_data)).astype(np.float32)
        epsilon = max(1.25, float(self._pixmap_item.boundingRect().height()) * 0.0025)
        simplified = cv2.approxPolyDP(points.reshape(-1, 1, 2), epsilon, False).reshape(-1, 2)
        indices = sorted(set(int(np.clip(round(p[0]), 0, width - 1)) for p in simplified))
        if 0 not in indices:
            indices.insert(0, 0)
        if width - 1 not in indices:
            indices.append(width - 1)
        if len(indices) > 120:
            keep = np.linspace(0, len(indices) - 1, 120).round().astype(int)
            indices = [indices[i] for i in sorted(set(keep))]
        self._control_points = [(x, float(self._horizon_data[x])) for x in indices]
        for index, _point in enumerate(self._control_points):
            item = QGraphicsEllipseItem()
            item.setZValue(30)
            item.setData(0, "pen_control")
            item.setData(1, index)
            item.setBrush(QColor(255, 255, 255, 235))
            self._scene.addItem(item)
            self._control_items.append(item)
        self._update_control_handle_geometry()

    def _update_control_handle_geometry(self):
        if not self._control_items:
            return
        scale = max(1e-6, self.transform().m11())
        radius = 4.6 / scale
        pen = QPen(QColor(14, 165, 233, 245))
        pen.setWidthF(1.3 / scale)
        for index, item in enumerate(self._control_items):
            x, y = self._control_points[index]
            item.setRect(x - radius, y - radius, radius * 2.0, radius * 2.0)
            item.setPen(pen)

        span_pen = QPen(QColor(255, 255, 255, 240))
        span_pen.setWidthF(1.1 / scale)
        span_radius = 4.2 / scale
        for handle in self._span_handles:
            x = float(handle.data(4))
            y = float(handle.data(3))
            handle.setRect(x - span_radius, y - span_radius, span_radius * 2.0, span_radius * 2.0)
            handle.setPen(span_pen)

    def _refresh_horizon_paths_only(self):
        if self._horizon_data is None:
            return
        width = len(self._horizon_data)
        for item in self._horizon_items:
            role = item.data(0)
            if role in ("horizon", "gray"):
                item.setPath(self._path_from_horizon(self._horizon_data, 0, width - 1))
            elif role == "selected" and self._selected_range is not None:
                xs, xe = sorted((int(self._selected_range[0]), int(self._selected_range[1])))
                margin = max(1, int(round(width * 0.0015)))
                item.setPath(self._path_from_horizon(
                    self._horizon_data, max(0, xs - margin), min(width - 1, xe + margin)
                ))

    def set_interaction_mode(self, mode: str):
        """Pilih navigasi, koreksi kontur, atau tambah objek manual."""
        if mode not in ("navigate", "edit_horizon", "add_object"):
            mode = "navigate"
        self._interaction_mode = mode
        self._drag_control_index = None
        self._drag_span_handle = None
        for handle in self._span_handles:
            handle.setVisible(mode == "edit_horizon")
        if mode == "navigate":
            self._clear_pen_control_points()
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.viewport().setCursor(Qt.OpenHandCursor)
        elif mode == "edit_horizon":
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.ArrowCursor)
            self._build_pen_control_points()
        else:
            self._clear_pen_control_points()
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.PointingHandCursor)

    def _scene_image_point(self, viewport_pos: QPoint):
        if self._pixmap_item is None:
            return None
        point = self.mapToScene(viewport_pos)
        rect = self._pixmap_item.boundingRect()
        if not rect.contains(point):
            return None
        return point

    def _nearest_obstacle(self, point):
        if point is None or not self._obstacles:
            return None
        scale = max(1e-6, self.transform().m11())
        tolerance = max(5.0, 14.0 / scale)
        best = None
        best_distance = float("inf")
        for index, obstacle in enumerate(self._obstacles):
            px = float(obstacle.get("x", 0))
            py = float(obstacle.get("y", 0))
            xs = float(obstacle.get("x_start", px))
            xe = float(obstacle.get("x_end", px))
            dx = 0.0 if min(xs, xe) - tolerance <= point.x() <= max(xs, xe) + tolerance else abs(point.x() - px)
            dy = abs(point.y() - py)
            distance = float(np.hypot(dx, dy))
            if distance < best_distance and distance <= tolerance * 2.2:
                best = (index, obstacle)
                best_distance = distance
        return best

    def _nearest_control_index(self, point):
        if point is None or not self._control_points:
            return None
        tolerance = 9.0 / max(1e-6, self.transform().m11())
        distances = [float(np.hypot(point.x() - x, point.y() - y)) for x, y in self._control_points]
        index = int(np.argmin(distances))
        return index if distances[index] <= tolerance else None

    def _nearest_span_handle(self, point):
        if point is None or not self._span_handles:
            return None
        tolerance = 10.0 / max(1e-6, self.transform().m11())
        best = None
        best_distance = float("inf")
        for handle in self._span_handles:
            distance = float(np.hypot(point.x() - float(handle.data(4)), point.y() - float(handle.data(3))))
            if distance <= tolerance and distance < best_distance:
                best, best_distance = handle, distance
        return best

    def _insert_pen_control(self, point):
        """Tambahkan anchor baru pada posisi garis yang diklik."""
        if point is None or self._horizon_data is None:
            return None
        x = max(1, min(len(self._horizon_data) - 2, int(round(point.x()))))
        if any(abs(existing_x - x) <= 1 for existing_x, _ in self._control_points):
            return None
        self._control_points.append((x, float(self._horizon_data[x])))
        self._control_points.sort(key=lambda value: value[0])
        self._rebuild_control_items_from_points()
        return next(i for i, value in enumerate(self._control_points) if value[0] == x)

    def _rebuild_control_items_from_points(self):
        points = list(self._control_points)
        self._clear_pen_control_points()
        self._control_points = points
        for index, _point in enumerate(self._control_points):
            item = QGraphicsEllipseItem()
            item.setZValue(30)
            item.setData(0, "pen_control")
            item.setData(1, index)
            item.setBrush(QColor(255, 255, 255, 235))
            self._scene.addItem(item)
            self._control_items.append(item)
        self._update_control_handle_geometry()

    def _drag_pen_control(self, point):
        if point is None or self._horizon_data is None or self._drag_control_index is None:
            return
        index = self._drag_control_index
        anchor_x, anchor_start_y = self._drag_start_point
        left_limit = self._control_points[index - 1][0] + 1 if index > 0 else 0
        right_limit = self._control_points[index + 1][0] - 1 if index + 1 < len(self._control_points) else len(self._horizon_data) - 1
        target_x = int(np.clip(round(point.x()), left_limit, right_limit))
        target_y = np.clip(point.y(), 0, self._pixmap_item.boundingRect().height() - 1)
        left_x = self._control_points[index - 1][0] if index > 0 else target_x
        right_x = self._control_points[index + 1][0] if index + 1 < len(self._control_points) else target_x
        self._horizon_data[:] = self._drag_start_horizon
        left_y = float(self._drag_start_horizon[left_x])
        right_y = float(self._drag_start_horizon[right_x])
        if left_x < target_x:
            xs = np.arange(left_x, target_x + 1)
            self._horizon_data[xs] = np.interp(xs, [left_x, target_x], [left_y, target_y])
        if target_x < right_x:
            xs = np.arange(target_x, right_x + 1)
            self._horizon_data[xs] = np.interp(xs, [target_x, right_x], [target_y, right_y])
        if left_x == right_x:
            self._horizon_data[target_x] = target_y
        self._horizon_data[:] = np.clip(self._horizon_data, 0, self._pixmap_item.boundingRect().height() - 1)
        self._control_points[index] = (target_x, float(target_y))
        self._refresh_horizon_paths_only()
        self._update_control_handle_geometry()

    def _drag_object_span(self, point):
        handle = self._drag_span_handle
        if point is None or handle is None:
            return
        obstacle_index = int(handle.data(1))
        if not (0 <= obstacle_index < len(self._obstacles)):
            return
        obstacle = self._obstacles[obstacle_index]
        side = str(handle.data(2))
        width = len(self._horizon_data)
        new_x = max(0, min(width - 1, int(round(point.x()))))
        if side == "left":
            new_x = min(new_x, int(obstacle.get("x_end", new_x)) - 1)
            obstacle["x_start"] = max(0, new_x)
        else:
            new_x = max(new_x, int(obstacle.get("x_start", new_x)) + 1)
            obstacle["x_end"] = min(width - 1, new_x)
        handle.setData(4, new_x)
        for bracket, index in self._span_items:
            if index != obstacle_index:
                continue
            xs, xe = int(obstacle["x_start"]), int(obstacle["x_end"])
            y = float(handle.data(3))
            tick = 7.0
            path = QPainterPath()
            path.moveTo(xs, y); path.lineTo(xe, y)
            path.moveTo(xs, y - tick); path.lineTo(xs, y + tick)
            path.moveTo(xe, y - tick); path.lineTo(xe, y + tick)
            bracket.setPath(path)
        self._update_control_handle_geometry()

    def _update_horizon_pen_widths(self):
        """Buat garis semakin tipis di layar ketika gambar diperbesar."""
        if not self._horizon_items:
            return
        scale = max(1e-6, self.transform().m11())
        reference = max(1e-6, self._overlay_reference_scale or scale)
        relative_zoom = max(1.0, scale / reference)
        for item in self._horizon_items:
            role = item.data(0)
            selected = role in ("selected", "selected_span")
            if selected:
                base_screen_width = 2.2
                color = QColor(239, 68, 68, 235)
            elif role == "horizon":
                base_screen_width = 1.8
                color = QColor(250, 204, 21, 220)
            elif role == "target":
                base_screen_width = 1.35
                color = QColor(239, 68, 68, 150)
            elif role == "span":
                base_screen_width = 1.35
                color = QColor(56, 189, 248, 190)
            else:
                base_screen_width = 1.15
                color = QColor(148, 163, 184, 175)
            # QPen memakai satuan scene. Dibagi scale menjaga ukuran layar,
            # lalu dibagi sqrt(zoom) lagi agar benar-benar makin tipis saat zoom.
            screen_width = max(0.42, base_screen_width / np.sqrt(relative_zoom))
            scene_width = screen_width / scale
            pen = QPen(color)
            pen.setWidthF(scene_width)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            item.setPen(pen)
        self._update_control_handle_geometry()

    def reset_zoom(self):
        if self._pixmap_item is None:
            return
        self.resetTransform()
        self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)
        self._zoom_steps = 0
        self.zoom_changed.emit(100)
        self._update_horizon_pen_widths()

    def focus_on_image_rect(self, rect: QRectF):
        """Pusatkan viewport pada area tertentu dalam koordinat piksel gambar."""
        if self._pixmap_item is None or rect.isEmpty():
            return
        image_rect = self._pixmap_item.boundingRect()
        target = rect.intersected(image_rect)
        if target.isEmpty():
            self.reset_zoom()
            return
        self.resetTransform()
        self.fitInView(target, Qt.KeepAspectRatio)
        self.centerOn(target.center())
        self._zoom_steps = 0
        self.zoom_changed.emit(100)
        self._update_horizon_pen_widths()

    def _current_zoom_percent(self) -> int:
        """Persentase relatif terhadap skala fit-to-window saat ini."""
        if self._pixmap_item is None:
            return 100
        image_rect = self._pixmap_item.boundingRect()
        if image_rect.isEmpty():
            return 100
        viewport_rect = self.viewport().rect()
        fit_scale = min(
            viewport_rect.width() / image_rect.width(),
            viewport_rect.height() / image_rect.height(),
        )
        if fit_scale <= 0:
            return 100
        return max(1, int(round(100 * self.transform().m11() / fit_scale)))

    def _zoom_at_viewport_pos(self, factor: float, pos: QPoint):
        """Zoom dengan piksel di bawah kursor/jari tetap berada di tempatnya."""
        if self._pixmap_item is None or factor <= 0:
            return
        current_scale = self.transform().m11()
        image_rect = self._pixmap_item.boundingRect()
        viewport_rect = self.viewport().rect()
        fit_scale = min(
            viewport_rect.width() / max(1.0, image_rect.width()),
            viewport_rect.height() / max(1.0, image_rect.height()),
        )
        min_scale = max(0.01, fit_scale * 0.35)
        max_scale = max(min_scale, fit_scale * 35.0)
        target_scale = max(min_scale, min(max_scale, current_scale * factor))
        applied_factor = target_scale / max(current_scale, 1e-9)
        if abs(applied_factor - 1.0) < 1e-4:
            return

        old_anchor = self.transformationAnchor()
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        scene_before = self.mapToScene(pos)
        self.scale(applied_factor, applied_factor)
        scene_after = self.mapToScene(pos)
        delta = scene_after - scene_before
        self.translate(delta.x(), delta.y())
        self.setTransformationAnchor(old_anchor)
        self.zoom_changed.emit(self._current_zoom_percent())
        self._update_horizon_pen_widths()

    def wheelEvent(self, event):
        if self._pixmap_item is None or event.angleDelta().y() == 0:
            super().wheelEvent(event)
            return
        # Trackpad dua jari umumnya mengirim pixelDelta: gunakan sebagai pan.
        # Roda mouse mengirim angleDelta dan tetap digunakan untuk zoom.
        if not event.pixelDelta().isNull():
            delta = event.pixelDelta()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        direction = 1 if event.angleDelta().y() > 0 else -1
        new_steps = max(-8, min(24, self._zoom_steps + direction))
        if new_steps == self._zoom_steps:
            event.accept()
            return
        factor = 1.22 if direction > 0 else 1.0 / 1.22
        self._zoom_at_viewport_pos(factor, event.pos())
        self._zoom_steps = new_steps
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Double-click memperbesar area tepat di bawah pointer. Reset tetap
            # tersedia melalui tombol "Sesuaikan Layar" pada toolbar.
            self._zoom_at_viewport_pos(1.85, event.pos())
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            point = self._scene_image_point(event.pos())
            if self._interaction_mode == "edit_horizon" and point is not None:
                span_handle = self._nearest_span_handle(point)
                if span_handle is not None:
                    self._drag_span_handle = span_handle
                    self.viewport().setCursor(Qt.SizeHorCursor)
                    event.accept()
                    return
                control_index = self._nearest_control_index(point)
                if control_index is None and self._horizon_data is not None:
                    x = max(0, min(len(self._horizon_data) - 1, int(round(point.x()))))
                    tolerance = 8.0 / max(1e-6, self.transform().m11())
                    if abs(point.y() - self._horizon_data[x]) <= tolerance:
                        control_index = self._insert_pen_control(point)
                if control_index is not None:
                    self._drag_control_index = control_index
                    self._drag_start_horizon = self._horizon_data.copy()
                    self._drag_start_point = self._control_points[control_index]
                    self.viewport().setCursor(Qt.ClosedHandCursor)
                    event.accept()
                    return
            if self._interaction_mode == "add_object" and point is not None:
                self.add_object_requested.emit(int(round(point.x())), int(round(point.y())))
                event.accept()
                return
            if self._interaction_mode == "navigate":
                nearest = self._nearest_obstacle(point)
                if nearest is not None:
                    index, obstacle = nearest
                    label = obstacle.get("label") or "Halangan Ufuk"
                    azimuth = float(obstacle.get("azimuth", 0.0))
                    elevation = float(obstacle.get("elevation", 0.0))
                    QToolTip.showText(
                        event.globalPos(),
                        f"{label}\nAzimut {azimuth:.2f}°  •  Elevasi {elevation:+.2f}°",
                        self,
                    )
                    self.obstacle_clicked.emit(index, obstacle)
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_span_handle is not None and (event.buttons() & Qt.LeftButton):
            self._drag_object_span(self._scene_image_point(event.pos()))
            event.accept()
            return
        if self._drag_control_index is not None and (event.buttons() & Qt.LeftButton):
            self._drag_pen_control(self._scene_image_point(event.pos()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drag_span_handle is not None:
            self._drag_object_span(self._scene_image_point(event.pos()))
            obstacle_index = int(self._drag_span_handle.data(1))
            obstacle = self._obstacles[obstacle_index]
            self._drag_span_handle = None
            self.viewport().setCursor(Qt.ArrowCursor)
            self.obstacle_range_edited.emit(
                obstacle_index,
                int(obstacle.get("x_start", 0)),
                int(obstacle.get("x_end", 0)),
            )
            event.accept()
            return
        if event.button() == Qt.LeftButton and self._drag_control_index is not None:
            self._drag_pen_control(self._scene_image_point(event.pos()))
            self._drag_control_index = None
            self._drag_start_horizon = None
            self._drag_start_point = None
            self.viewport().setCursor(Qt.ArrowCursor)
            self.horizon_edited.emit(self._horizon_data.copy())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def viewportEvent(self, event):
        if event.type() == QEvent.Gesture:
            pinch = event.gesture(Qt.PinchGesture)
            if pinch is not None:
                if pinch.state() == Qt.GestureStarted:
                    self._pinch_last_scale = 1.0
                scale = float(pinch.totalScaleFactor())
                factor = scale / max(self._pinch_last_scale, 1e-6)
                center = pinch.centerPoint().toPoint()
                self._zoom_at_viewport_pos(factor, center)
                self._pinch_last_scale = scale
                if pinch.state() in (Qt.GestureFinished, Qt.GestureCanceled):
                    self._pinch_last_scale = 1.0
                event.accept()
                return True

        # macOS mengirim pinch trackpad sebagai NativeGesture. value() adalah
        # delta zoom kecil, positif untuk membuka dan negatif untuk mencubit.
        if event.type() == QEvent.NativeGesture:
            try:
                if event.gestureType() == Qt.ZoomNativeGesture:
                    factor = max(0.75, min(1.25, 1.0 + float(event.value())))
                    local_pos = self.viewport().mapFromGlobal(event.globalPos())
                    self._zoom_at_viewport_pos(factor, local_pos)
                    event.accept()
                    return True
            except (AttributeError, TypeError):
                pass
        return super().viewportEvent(event)


class FullscreenImageViewer(QDialog):
    """Dialog fullscreen untuk inspeksi overlay beresolusi penuh."""

    def __init__(
        self,
        bgr_image: np.ndarray,
        parent=None,
        focus_rect: Optional[QRectF] = None,
        horizon_y: Optional[np.ndarray] = None,
        selected_range: Optional[Tuple[int, int]] = None,
        target_x: Optional[int] = None,
        obstacles: Optional[list] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Pratinjau Citra Kontur — Fullscreen")
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.setStyleSheet("background-color:#07090d;color:#e2e8f0;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QFrame()
        toolbar.setStyleSheet("background:#111827;border-bottom:1px solid #263244;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(14, 7, 14, 7)
        title = QLabel("Citra Kontur Ufuk Mar'i")
        title.setStyleSheet("font-size:13px;font-weight:bold;color:#38bdf8;border:none;")
        hint = QLabel("Scroll/cubit: zoom  •  Drag/2 jari: geser  •  Double-click: zoom titik  •  Esc: tutup")
        hint.setStyleSheet("font-size:11px;color:#94a3b8;border:none;")
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(54)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_label.setStyleSheet("font-weight:bold;color:#fbbf24;border:none;")
        reset_button = QPushButton("Sesuaikan Layar")
        close_button = QPushButton("Tutup")
        for button in (reset_button, close_button):
            button.setCursor(Qt.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton{background:#1e293b;color:white;border:1px solid #334155;"
                "border-radius:6px;padding:6px 12px;}"
                "QPushButton:hover{background:#334155;}"
            )
        toolbar_layout.addWidget(title)
        toolbar_layout.addSpacing(18)
        toolbar_layout.addWidget(hint)
        toolbar_layout.addStretch()
        self.navigate_button = QPushButton("Navigasi")
        self.edit_button = QPushButton("Edit Garis")
        self.add_button = QPushButton("Tambah Objek")
        for button in (self.navigate_button, self.edit_button, self.add_button):
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton{background:#172033;color:#cbd5e1;border:1px solid #334155;"
                "border-radius:6px;padding:6px 10px;}"
                "QPushButton:checked{background:#0369a1;color:white;border-color:#38bdf8;}"
            )
        self.navigate_button.setChecked(True)
        toolbar_layout.addWidget(self.navigate_button)
        toolbar_layout.addWidget(self.edit_button)
        toolbar_layout.addWidget(self.add_button)
        toolbar_layout.addWidget(self.zoom_label)
        toolbar_layout.addWidget(reset_button)
        toolbar_layout.addWidget(close_button)
        layout.addWidget(toolbar)

        self.view = ZoomableGraphicsView()
        layout.addWidget(self.view, stretch=1)

        rgb_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        h, w, channels = rgb_image.shape
        q_image = QImage(
            rgb_image.data, w, h, channels * w, QImage.Format_RGB888
        ).copy()
        self.view.set_pixmap(QPixmap.fromImage(q_image))
        self.view.zoom_changed.connect(lambda value: self.zoom_label.setText(f"{value}%"))
        reset_button.clicked.connect(self.view.reset_zoom)
        close_button.clicked.connect(self.close)
        self.navigate_button.clicked.connect(lambda: self._set_mode("navigate"))
        self.edit_button.clicked.connect(lambda: self._set_mode("edit_horizon"))
        self.add_button.clicked.connect(lambda: self._set_mode("add_object"))
        def prepare_view():
            # Tunggu viewport memperoleh ukuran fullscreen sebelum fitInView.
            if focus_rect is not None:
                self.view.focus_on_image_rect(focus_rect)
            if horizon_y is not None:
                self.view.set_horizon_overlay(
                    horizon_y,
                    selected_range,
                    target_x=target_x,
                    obstacles=obstacles,
                )

        QTimer.singleShot(0, prepare_view)

    def _set_mode(self, mode: str):
        self.navigate_button.setChecked(mode == "navigate")
        self.edit_button.setChecked(mode == "edit_horizon")
        self.add_button.setChecked(mode == "add_object")
        self.view.set_interaction_mode(mode)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Escape, Qt.Key_F11):
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)


class InteractiveImageViewer(QLabel):
    """
    Widget penampil citra berbasis QLabel dengan penskalaan aspek rasio
    dan penangkapan koordinat klik pengguna pada citra asli.
    """
    pixel_clicked = pyqtSignal(int, int)  # Emits (x, y) dalam koordinat citra asli
    mouse_moved = pyqtSignal(int, int)

    def __init__(self, parent=None, placeholder_text="Kamera belum aktif"):
        super().__init__(parent)
        self.placeholder_text = placeholder_text
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(280, 160)
        self.setStyleSheet("""
            QLabel {
                background-color: #0d0f12;
                border: 1px solid #252b36;
                border-radius: 6px;
            }
        """)

        self._cv_image = None
        self._pixmap = None
        self._last_rendered_rect = QRect()
        self.show_crosshair = False
        self.crosshair_is_locked = False
        self.setMouseTracking(True)

    def set_crosshair(self, show: bool, is_locked: bool = False):
        """Mengatur tampilan crosshair bidikan pada tengah viewport."""
        self.show_crosshair = show
        self.crosshair_is_locked = is_locked
        self.update()

    def set_cv_image(self, bgr_image: Optional[np.ndarray]):
        """Menampilkan citra OpenCV format BGR."""
        if bgr_image is None or bgr_image.size == 0:
            self._cv_image = None
            self._pixmap = None
            self.update()
            return

        self._cv_image = bgr_image
        h, w, ch = bgr_image.shape
        bytes_per_line = ch * w
        # Konversi BGR OpenCV ke RGB QImage
        rgb_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self._pixmap = QPixmap.fromImage(q_img)
        self.update()

    def get_cv_image(self) -> Optional[np.ndarray]:
        """Mengambil frame OpenCV aktif."""
        return self._cv_image.copy() if self._cv_image is not None else None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Latar belakang gelap
        painter.fillRect(self.rect(), QColor("#0d0f12"))

        if self._pixmap is None or self._pixmap.isNull():
            # Tampilkan placeholder
            painter.setPen(QColor("#546070"))
            font = QFont("Segoe UI", 10)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, self.placeholder_text)
            return

        # Skala pixmap mempertahankan aspek rasio (KeepAspectRatio)
        scaled_pixmap = self._pixmap.scaled(
            self.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        # Posisi tengah
        x = (self.width() - scaled_pixmap.width()) // 2
        y = (self.height() - scaled_pixmap.height()) // 2
        self._last_rendered_rect = QRect(x, y, scaled_pixmap.width(), scaled_pixmap.height())

        painter.drawPixmap(x, y, scaled_pixmap)

        # Gambar Crosshair Overlay di Tengah Viewport jika aktif
        if self.show_crosshair:
            center_x = self.width() // 2
            center_y = self.height() // 2
            radius = 24
            line_ext = 40

            color = QColor("#10b981") if self.crosshair_is_locked else QColor("#38bdf8")
            pen = painter.pen()
            pen.setColor(color)
            pen.setWidth(2)
            painter.setPen(pen)

            # Lingkaran bidikan tengah
            painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

            # Garis silang bidikan
            painter.drawLine(center_x - line_ext, center_y, center_x - radius, center_y)
            painter.drawLine(center_x + radius, center_y, center_x + line_ext, center_y)
            painter.drawLine(center_x, center_y - line_ext, center_x, center_y - radius)
            painter.drawLine(center_x, center_y + radius, center_x, center_y + line_ext)

            # Titik pusat
            painter.setBrush(color)
            painter.drawEllipse(center_x - 3, center_y - 3, 6, 6)

    def _map_widget_to_image_coords(self, pos: QPoint) -> Optional[Tuple[int, int]]:
        """Mengonversi posisi mouse pada widget ke koordinat piksel citra asli."""
        if self._cv_image is None or not self._last_rendered_rect.contains(pos):
            return None

        orig_h, orig_w = self._cv_image.shape[:2]
        rel_x = pos.x() - self._last_rendered_rect.x()
        rel_y = pos.y() - self._last_rendered_rect.y()

        img_x = int(rel_x * (orig_w / self._last_rendered_rect.width()))
        img_y = int(rel_y * (orig_h / self._last_rendered_rect.height()))

        img_x = max(0, min(orig_w - 1, img_x))
        img_y = max(0, min(orig_h - 1, img_y))

        return img_x, img_y

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            coords = self._map_widget_to_image_coords(event.pos())
            if coords is not None:
                self.pixel_clicked.emit(coords[0], coords[1])
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        coords = self._map_widget_to_image_coords(event.pos())
        if coords is not None:
            self.mouse_moved.emit(coords[0], coords[1])
        super().mouseMoveEvent(event)
