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
)
from PyQt5.QtGui import QImage, QPixmap, QPainter, QColor, QFont
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QRect, QRectF, QTimer, QEvent


class ZoomableGraphicsView(QGraphicsView):
    """Penampil gambar besar dengan zoom roda mouse dan pan lewat drag."""

    zoom_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = None
        self._zoom_steps = 0
        self._pinch_last_scale = 1.0
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

    def reset_zoom(self):
        if self._pixmap_item is None:
            return
        self.resetTransform()
        self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)
        self._zoom_steps = 0
        self.zoom_changed.emit(100)

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

    def __init__(self, bgr_image: np.ndarray, parent=None, focus_rect: Optional[QRectF] = None):
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
        if focus_rect is not None:
            # Tunggu viewport memperoleh ukuran fullscreen sebelum fitInView.
            QTimer.singleShot(0, lambda: self.view.focus_on_image_rect(focus_rect))

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
