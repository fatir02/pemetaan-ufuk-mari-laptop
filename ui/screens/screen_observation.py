"""
screen_observation.py
LAYAR 2: PENGAMATAN (KAMERA, SENSOR HUD, & JEPRET FOTO)
Alur pengamatan lapangan:
- Viewfinder kamera live / penampil citra dengan crosshair bidikan.
- HUD Sensor: Indikator Azimuth 270° Barat (Lock Hijau), Elevasi, dan GPS.
- Shutter potret frame & upload dari file / galeri.
- Preview thumbnail strip (hingga 3 foto).
- Tombol aksi [PROSES & LIHAT HASIL] untuk mengekstrak kontur ufuk.
"""

import os
from typing import Optional, List, Dict, Any
import numpy as np
import cv2

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSlider, QDialog, QLineEdit, QFileDialog, QMessageBox,
    QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QImage, QPixmap

from core.camera_worker import CameraWorker
from core.sample_generator import generate_synthetic_horizon
from core.cv_engine import HorizonDetector
from core.falak_calc import calculate_dip, parse_dms, format_dms
from core.compass_service import compass_service
from core.paths import get_resource_path
from ui.widgets.image_viewer import InteractiveImageViewer


class ManualCoordsDialog(QDialog):
    """Dialog sederhana untuk mengubah koordinat GPS dan elevasi secara manual."""
    def __init__(self, lat: float, lon: float, alt: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ubah Koordinat Pengamatan (GPS)")
        self.setFixedSize(360, 240)
        self.setStyleSheet("""
            QDialog { background-color: #151922; color: #ffffff; }
            QLabel { color: #94a3b8; font-size: 12px; }
            QLineEdit {
                background-color: #1e2634;
                color: #ffffff;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Latitude (Lintang, desimal atau DMS):"))
        self.edit_lat = QLineEdit(str(lat))
        layout.addWidget(self.edit_lat)

        layout.addWidget(QLabel("Longitude (Bujur, desimal atau DMS):"))
        self.edit_lon = QLineEdit(str(lon))
        layout.addWidget(self.edit_lon)

        layout.addWidget(QLabel("Ketinggian Tempat (h dalam meter dpl):"))
        self.edit_alt = QLineEdit(str(alt))
        layout.addWidget(self.edit_alt)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_cancel = QPushButton("Batal")
        btn_cancel.setStyleSheet("background-color: #334155; color: #ffffff;")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("Simpan")
        btn_save.setStyleSheet("background-color: #0284c7; color: #ffffff;")
        btn_save.clicked.connect(self.accept)
        btn_box.addWidget(btn_save)

        layout.addLayout(btn_box)

    def get_values(self):
        lat = parse_dms(self.edit_lat.text())
        lon = parse_dms(self.edit_lon.text())
        try:
            alt = float(self.edit_alt.text().strip())
        except ValueError:
            alt = 10.0
        return lat, lon, alt


class ScreenObservation(QWidget):
    """Layar Pengamatan & Sensor Kamera."""
    # Sinyal saat proses ekstraksi selesai dan siap menuju Layar 3 (Hasil)
    proceed_to_result = pyqtSignal(dict)
    back_to_dashboard = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Nilai acuan sensor default
        self.azimuth_val = 270.0       # Derajat Azimuth tengah (Barat)
        self.elevation_val = 0.0      # Kemiringan kemiringan kamera (Tilt)
        self.latitude = -7.9800        # Lintang pengamat (Parangtritis)
        self.longitude = 110.3061      # Bujur pengamat
        self.altitude = 45.0           # Ketinggian mdpl
        self.is_manual_gps = False

        # Kamera & Detektor
        self.cv_detector = HorizonDetector()
        # Kamera fisik adalah default. Sebelumnya is_simulation=True membuat
        # tombol live tidak pernah mencoba webcam laptop/USB.
        self.camera_worker = CameraWorker(camera_index=None, is_simulation=False)
        self.camera_worker.frame_ready.connect(self._on_camera_frame)
        self.camera_worker.fps_updated.connect(self._on_camera_fps)
        self.camera_worker.status_changed.connect(self._on_camera_status)
        self.camera_worker.error_occurred.connect(self._on_camera_error)

        # Buffer foto (maksimal 3 slot)
        self.captured_images: List[np.ndarray] = []
        self.selected_image_index: int = -1
        self.current_live_frame: Optional[np.ndarray] = None

        self._init_ui()
        self._load_initial_sample()

        compass_service.start()
        self.sensor_timer = QTimer(self)
        self.sensor_timer.timeout.connect(self._poll_sensor_service)
        self.sensor_timer.start(100)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        scroll_content = QWidget()
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(16, 12, 16, 12)
        content_layout.setSpacing(10)

        # ==========================================
        # 1. HUD SENSOR DI ATAS
        # ==========================================
        hud_container = QFrame()
        hud_container.setStyleSheet("""
            QFrame {
                background-color: #121721;
                border: 1px solid #1e2634;
                border-radius: 12px;
                padding: 4px;
            }
        """)
        hud_layout = QVBoxLayout(hud_container)
        hud_layout.setSpacing(8)

        # Baris Atas HUD: Banner Indikator 270° Barat
        top_bar = QHBoxLayout()
        self.btn_back = QPushButton("⬅️ Beranda")
        self.btn_back.setStyleSheet("""
            QPushButton {
                background-color: #1e2634; color: #94a3b8;
                border: 1px solid #334155; border-radius: 8px;
                padding: 6px 14px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #2a3445; color: #ffffff; }
        """)
        self.btn_back.clicked.connect(self.back_to_dashboard.emit)
        top_bar.addWidget(self.btn_back)

        top_bar.addStretch()

        # Banner Kunci Barat 270°
        self.badge_west = QLabel("🧭 TEPAT KE BARAT (270.0°)")
        self.badge_west.setAlignment(Qt.AlignCenter)
        self.badge_west.setStyleSheet("""
            background-color: #10b981;
            color: #ffffff;
            font-size: 12px;
            font-weight: 800;
            padding: 6px 18px;
            border-radius: 14px;
            letter-spacing: 0.5px;
        """)
        top_bar.addWidget(self.badge_west)

        top_bar.addStretch()

        # Tombol Lock Barat Cepat
        self.btn_lock_west = QPushButton("🎯 Kunci 270° Barat")
        self.btn_lock_west.setStyleSheet("""
            QPushButton {
                background-color: #0284c7; color: #ffffff;
                border: 1px solid #38bdf8; border-radius: 8px;
                padding: 6px 14px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)
        self.btn_lock_west.clicked.connect(self._reset_to_west)
        top_bar.addWidget(self.btn_lock_west)

        hud_layout.addLayout(top_bar)

        # Baris Bawah HUD: Nilai Sensor (Azimuth, Elevasi, GPS)
        data_bar = QHBoxLayout()
        data_bar.setSpacing(12)

        # Azimuth Box
        self.card_azimuth = self._create_hud_card("Sudut Azimuth", f"{self.azimuth_val:.1f}°", "#38bdf8")
        data_bar.addWidget(self.card_azimuth)

        # Slider Azimuth Cepat (250° - 290°)
        az_slider_box = QVBoxLayout()
        az_slider_box.setSpacing(2)
        lbl_adj = QLabel("Geser Arah Bidikan:")
        lbl_adj.setStyleSheet("color: #64748b; font-size: 11px;")
        az_slider_box.addWidget(lbl_adj)

        self.slider_azimuth = QSlider(Qt.Horizontal)
        self.slider_azimuth.setRange(2500, 2900)  # 250.0 s.d 290.0
        self.slider_azimuth.setValue(2700)
        self.slider_azimuth.setStyleSheet("""
            QSlider::groove:horizontal { height: 6px; background: #1e2634; border-radius: 3px; }
            QSlider::sub-page:horizontal { background: #0284c7; border-radius: 3px; }
            QSlider::handle:horizontal {
                background: #38bdf8; width: 16px; margin-top: -5px; margin-bottom: -5px; border-radius: 8px;
            }
        """)
        self.slider_azimuth.valueChanged.connect(self._on_azimuth_slider_changed)
        az_slider_box.addWidget(self.slider_azimuth)
        data_bar.addLayout(az_slider_box, stretch=2)

        # Elevasi Kemiringan Box
        self.card_elevation = self._create_hud_card("Sudut Elevasi (Pitch)", f"{self.elevation_val:+.1f}°", "#fbbf24")
        data_bar.addWidget(self.card_elevation)

        # GPS Box dengan tombol edit
        gps_box = QFrame()
        gps_box.setStyleSheet("background-color: #171d29; border: 1px solid #232a38; border-radius: 8px; padding: 6px;")
        gps_l = QHBoxLayout(gps_box)
        gps_l.setContentsMargins(8, 4, 8, 4)

        info_v = QVBoxLayout()
        info_v.setSpacing(1)
        lbl_gps_t = QLabel("Koordinat & Ketinggian (GPS)")
        lbl_gps_t.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.lbl_gps_val = QLabel(f"{self.latitude:.4f}, {self.longitude:.4f} | {self.altitude:.0f} mdpl")
        self.lbl_gps_val.setStyleSheet("color: #a78bfa; font-weight: bold; font-size: 12px;")
        info_v.addWidget(lbl_gps_t)
        info_v.addWidget(self.lbl_gps_val)
        gps_l.addLayout(info_v)

        btn_edit_gps = QPushButton("✏️")
        btn_edit_gps.setToolTip("Ubah Koordinat Manual")
        btn_edit_gps.setStyleSheet("""
            QPushButton {
                background-color: #232a38; color: #38bdf8;
                border: 1px solid #334155; border-radius: 6px;
                padding: 6px 10px; font-size: 13px;
            }
            QPushButton:hover { background-color: #2e384b; }
        """)
        btn_edit_gps.clicked.connect(self._open_coords_dialog)
        gps_l.addWidget(btn_edit_gps)

        data_bar.addWidget(gps_box, stretch=2)
        hud_layout.addLayout(data_bar)

        content_layout.addWidget(hud_container)

        # ==========================================
        # 2. VIEWPORT CITRA / LIVE STREAM
        # ==========================================
        self.image_viewer = InteractiveImageViewer(
            placeholder_text="Kamera Siap. Silakan Ambil Foto atau Muat Gambar."
        )
        self.image_viewer.setMinimumHeight(240)
        self.image_viewer.set_crosshair(True, is_locked=True)
        content_layout.addWidget(self.image_viewer, stretch=4)

        # Kontrol Kamera & Ambil Foto
        cam_bar = QHBoxLayout()
        cam_bar.setSpacing(10)

        self.btn_live_cam = QPushButton("🔴 Mode Live Kamera")
        self.btn_live_cam.setCheckable(True)
        self.btn_live_cam.setStyleSheet("""
            QPushButton {
                background-color: #1e2634; color: #e2e8f0;
                border: 1px solid #334155; border-radius: 8px;
                padding: 8px 16px; font-weight: bold; font-size: 12px;
            }
            QPushButton:checked {
                background-color: #dc2626; color: #ffffff; border-color: #ef4444;
            }
        """)
        self.btn_live_cam.clicked.connect(self._toggle_live_camera)
        cam_bar.addWidget(self.btn_live_cam)

        self.lbl_camera_status = QLabel("Kamera nonaktif")
        self.lbl_camera_status.setStyleSheet("color:#94a3b8;font-size:11px;")
        cam_bar.addWidget(self.lbl_camera_status)

        self.btn_capture = QPushButton("📸 Potret Frame")
        self.btn_capture.setStyleSheet("""
            QPushButton {
                background-color: #0284c7; color: #ffffff;
                border: 1px solid #38bdf8; border-radius: 8px;
                padding: 8px 18px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)
        self.btn_capture.clicked.connect(self._capture_current_frame)
        cam_bar.addWidget(self.btn_capture)

        self.btn_browse = QPushButton("📂 Pilih dari Galeri/File...")
        self.btn_browse.setStyleSheet("""
            QPushButton {
                background-color: #1e2634; color: #e2e8f0;
                border: 1px solid #334155; border-radius: 8px;
                padding: 8px 16px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #2a3445; }
        """)
        self.btn_browse.clicked.connect(self._browse_image_file)
        cam_bar.addWidget(self.btn_browse)

        self.btn_sample = QPushButton("🖼️ Muat Contoh")
        self.btn_sample.setStyleSheet("""
            QPushButton {
                background-color: #1e2634; color: #e2e8f0;
                border: 1px solid #334155; border-radius: 8px;
                padding: 8px 16px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #2a3445; }
        """)
        self.btn_sample.clicked.connect(self._load_sample_landscape)
        cam_bar.addWidget(self.btn_sample)

        cam_bar.addStretch()

        self.lbl_photo_status = QLabel("1 Foto Siap Diproses")
        self.lbl_photo_status.setStyleSheet("color: #10b981; font-weight: bold; font-size: 12px;")
        cam_bar.addWidget(self.lbl_photo_status)

        content_layout.addLayout(cam_bar)

        # ==========================================
        # 3. PREVIEW STRIP (SLOT HINGGA 3 FOTO) & TOMBOL PROSES
        # ==========================================
        bottom_bar = QFrame()
        bottom_bar.setStyleSheet("""
            QFrame {
                background-color: #121721;
                border: 1px solid #1e2634;
                border-radius: 12px;
                padding: 8px;
            }
        """)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setSpacing(12)

        # Label Preview
        preview_label = QLabel("Preview Foto\n(Maks 3 Slot):")
        preview_label.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
        bottom_layout.addWidget(preview_label)

        # 3 Kotak Thumbnail
        self.thumb_labels: List[QLabel] = []
        for i in range(3):
            lbl = QLabel(f"Slot {i+1}")
            lbl.setFixedSize(72, 54)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("""
                QLabel {
                    background-color: #18202d;
                    border: 1.5px dashed #334155;
                    border-radius: 8px;
                    color: #475569;
                    font-size: 11px;
                }
            """)
            lbl.mousePressEvent = lambda event, idx=i: self._select_thumbnail(idx)
            self.thumb_labels.append(lbl)
            bottom_layout.addWidget(lbl)

        self.btn_delete_photo = QPushButton("🗑️ Hapus")
        self.btn_delete_photo.setToolTip("Hapus foto pada slot yang dipilih")
        self.btn_delete_photo.setStyleSheet("""
            QPushButton {
                background-color: #1e2634; color: #ef4444;
                border: 1px solid #334155; border-radius: 6px;
                padding: 6px 12px; font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2b1f24; border-color: #ef4444; }
            QPushButton:disabled { color: #475569; border-color: #1e2634; }
        """)
        self.btn_delete_photo.clicked.connect(self._delete_selected_slot)
        self.btn_reset_photos = self.btn_delete_photo  # alias kompatibilitas
        bottom_layout.addWidget(self.btn_delete_photo)

        bottom_layout.addStretch()

        # Tombol Aksi Utama: [PROSES & LIHAT HASIL]
        self.btn_proceed = QPushButton("🔍  PROSES & LIHAT HASIL ➡️")
        self.btn_proceed.setCursor(Qt.PointingHandCursor)
        self.btn_proceed.setMinimumHeight(48)
        self.btn_proceed.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #34d399;
                border-radius: 10px;
                padding: 10px 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #34d399, stop:1 #10b981);
            }
            QPushButton:disabled {
                background-color: #1e2634;
                color: #64748b;
                border-color: #334155;
            }
        """)
        self.btn_proceed.clicked.connect(self._process_and_proceed)
        bottom_layout.addWidget(self.btn_proceed)

        content_layout.addWidget(bottom_bar)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

    def _create_hud_card(self, title: str, value: str, val_color: str) -> QFrame:
        """Membuat kotak tampilan data HUD sensor."""
        card = QFrame()
        card.setStyleSheet("background-color: #171d29; border: 1px solid #232a38; border-radius: 8px; padding: 6px;")
        l = QVBoxLayout(card)
        l.setContentsMargins(10, 4, 10, 4)
        l.setSpacing(1)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        v_lbl = QLabel(value)
        v_lbl.setObjectName("ValLabel")
        v_lbl.setStyleSheet(f"color: {val_color}; font-weight: bold; font-size: 15px;")

        l.addWidget(t_lbl)
        l.addWidget(v_lbl)
        return card

    def _poll_sensor_service(self):
        data = compass_service.get_data()
        if not data.get("connected"):
            return
        az = float(data.get("azimuth", 270.0))
        tilt = float(data.get("tilt", 0.0))
        self.azimuth_val = az
        self.elevation_val = tilt

        val_lbl = self.card_azimuth.findChild(QLabel, "ValLabel")
        if val_lbl:
            val_lbl.setText(f"{az:.1f}°")

        el_lbl = self.card_elevation.findChild(QLabel, "ValLabel")
        if el_lbl:
            el_lbl.setText(f"{tilt:+.1f}°")

        slider_val = int(az * 10)
        if self.slider_azimuth.minimum() <= slider_val <= self.slider_azimuth.maximum():
            self.slider_azimuth.blockSignals(True)
            self.slider_azimuth.setValue(slider_val)
            self.slider_azimuth.blockSignals(False)

        is_west = abs(az - 270.0) <= 2.5
        if is_west:
            self.badge_west.setText(f"🧭 TEPAT KE BARAT ({az:.1f}°)")
            self.badge_west.setStyleSheet("""
                background-color: #10b981; color: #ffffff;
                font-size: 12px; font-weight: 800; padding: 6px 18px;
                border-radius: 14px;
            """)
            self.image_viewer.set_crosshair(True, is_locked=True)
        else:
            self.badge_west.setText(f"🧭 AZIMUTH: {az:.1f}°")
            self.badge_west.setStyleSheet("""
                background-color: #1e293b; color: #38bdf8;
                font-size: 12px; font-weight: bold; padding: 6px 18px;
                border-radius: 14px;
            """)
            self.image_viewer.set_crosshair(True, is_locked=False)

    def _on_azimuth_slider_changed(self, val_int: int):
        """Dipicu saat slider arah azimuth diubah."""
        self.azimuth_val = val_int / 10.0
        val_lbl = self.card_azimuth.findChild(QLabel, "ValLabel")
        if val_lbl:
            val_lbl.setText(f"{self.azimuth_val:.1f}°")

        # Cek apakah mengarah ke Barat (270° ± 2.5°)
        is_west = abs(self.azimuth_val - 270.0) <= 2.5
        if is_west:
            self.badge_west.setText("🧭 TEPAT KE BARAT (270.0°)")
            self.badge_west.setStyleSheet("""
                background-color: #10b981; color: #ffffff;
                font-size: 12px; font-weight: 800; padding: 6px 18px;
                border-radius: 14px;
            """)
            self.image_viewer.set_crosshair(True, is_locked=True)
        else:
            self.badge_west.setText(f"🧭 AZIMUTH: {self.azimuth_val:.1f}°")
            self.badge_west.setStyleSheet("""
                background-color: #334155; color: #94a3b8;
                font-size: 12px; font-weight: bold; padding: 6px 18px;
                border-radius: 14px;
            """)
            self.image_viewer.set_crosshair(True, is_locked=False)

    def _reset_to_west(self):
        """Mereset bidikan tepat ke 270° Barat."""
        self.slider_azimuth.setValue(2700)

    def _open_coords_dialog(self):
        """Membuka dialog ubah GPS."""
        dlg = ManualCoordsDialog(self.latitude, self.longitude, self.altitude, self)
        if dlg.exec_() == QDialog.Accepted:
            self.latitude, self.longitude, self.altitude = dlg.get_values()
            self.is_manual_gps = True
            self.lbl_gps_val.setText(f"{self.latitude:.4f}, {self.longitude:.4f} | {self.altitude:.0f} mdpl (Manual)")

    def _toggle_live_camera(self, active: bool):
        """Menghidupkan/mematikan stream kamera live."""
        if active:
            if not self.camera_worker.isRunning():
                self.current_live_frame = None
                self.lbl_camera_status.setText("Mencari kamera...")
                self.lbl_camera_status.setStyleSheet("color:#fbbf24;font-size:11px;")
                self.camera_worker.start()
            self.btn_live_cam.setText("⏹️ Hentikan Kamera")
        else:
            self.camera_worker.stop()
            self.btn_live_cam.setText("🔴 Mode Live Kamera")

    def _on_camera_fps(self, fps: float):
        self.lbl_camera_status.setText(f"Kamera aktif • {fps:.1f} FPS")
        self.lbl_camera_status.setStyleSheet("color:#10b981;font-size:11px;font-weight:bold;")

    def _on_camera_status(self, running: bool, message: str):
        self.lbl_camera_status.setText(message)
        self.lbl_camera_status.setStyleSheet(
            f"color:{'#10b981' if running else '#94a3b8'};font-size:11px;"
        )
        if not running:
            self.btn_live_cam.blockSignals(True)
            self.btn_live_cam.setChecked(False)
            self.btn_live_cam.setText("🔴 Mode Live Kamera")
            self.btn_live_cam.blockSignals(False)

    def _on_camera_error(self, message: str):
        self.lbl_camera_status.setText("Kamera gagal dibuka")
        self.lbl_camera_status.setStyleSheet("color:#ef4444;font-size:11px;font-weight:bold;")
        QMessageBox.warning(self, "Kamera Tidak Tersedia", message)

    def _on_camera_frame(self, frame_bgr: np.ndarray):
        """Menerima frame dari live kamera."""
        self.current_live_frame = frame_bgr.copy()
        if self.btn_live_cam.isChecked():
            display_img = self._get_display_variant(frame_bgr)
            self.image_viewer.set_cv_image(display_img)

    def _get_display_variant(self, img_bgr: np.ndarray) -> np.ndarray:
        """Mengembalikan citra asli berwarna."""
        return img_bgr

    def _capture_current_frame(self):
        """Memotret frame kamera saat ini atau frame aktif."""
        frame = self.current_live_frame if self.current_live_frame is not None else self.image_viewer.get_cv_image()
        if frame is None:
            QMessageBox.information(self, "Info", "Belum ada frame citra aktif untuk dipotret.")
            return

        if len(self.captured_images) >= 3:
            QMessageBox.warning(self, "Batas Foto", "Maksimal 3 foto tercapai. Silakan hapus foto pada slot yang ingin diganti.")
            return

        self._add_captured_image(frame)

    def _browse_image_file(self):
        """Membuka file citra dari disk/galeri."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Pilih Foto Lanskap Ufuk", "",
            "File Gambar (*.jpg *.jpeg *.png *.bmp);;Semua File (*.*)"
        )
        if file_path and os.path.exists(file_path):
            img = cv2.imread(file_path)
            if img is not None:
                self._add_captured_image(img)

    def _load_sample_landscape(self):
        """Memuat citra contoh lanskap ufuk bawaan."""
        sample_path = get_resource_path(os.path.join("assets", "sample_horizon.jpg"))
        if os.path.exists(sample_path):
            img = cv2.imread(sample_path)
        else:
            img = generate_synthetic_horizon(1280, 720)
        self._add_captured_image(img)

    def _load_initial_sample(self):
        """Memuat contoh awal saat pertama kali buka aplikasi."""
        self._load_sample_landscape()

    def _add_captured_image(self, img_bgr: np.ndarray):
        """Menambahkan citra ke daftar captured images."""
        if len(self.captured_images) >= 3:
            self.captured_images[2] = img_bgr
            idx = 2
        else:
            self.captured_images.append(img_bgr)
            idx = len(self.captured_images) - 1

        self.selected_image_index = idx
        self._update_thumbnails()
        self.image_viewer.set_cv_image(self._get_display_variant(img_bgr))
        self.lbl_photo_status.setText(f"{len(self.captured_images)} Foto Siap Diproses")
        self.btn_proceed.setEnabled(True)

    def _select_thumbnail(self, index: int):
        """Memilih thumbnail foto tertentu."""
        if 0 <= index < len(self.captured_images):
            self.selected_image_index = index
            self._update_thumbnails()
            self.image_viewer.set_cv_image(self._get_display_variant(self.captured_images[index]))

    def _delete_selected_slot(self):
        """Menghapus foto pada slot yang sedang dipilih."""
        if not self.captured_images:
            QMessageBox.information(self, "Informasi", "Belum ada foto dalam slot untuk dihapus.")
            return

        if self.selected_image_index < 0 or self.selected_image_index >= len(self.captured_images):
            QMessageBox.information(self, "Pilih Slot", "Silakan klik salah satu slot foto yang ingin dihapus terlebih dahulu.")
            return

        # Hapus foto dari slot yang dipilih
        del self.captured_images[self.selected_image_index]

        if len(self.captured_images) > 0:
            # Tetap pada indeks yang sama jika masih ada, atau ke slot terakhir yang tersedia
            self.selected_image_index = min(self.selected_image_index, len(self.captured_images) - 1)
            self.image_viewer.set_cv_image(self._get_display_variant(self.captured_images[self.selected_image_index]))
            self.lbl_photo_status.setText(f"{len(self.captured_images)} Foto Siap Diproses")
            self.btn_proceed.setEnabled(True)
        else:
            self.selected_image_index = -1
            self.image_viewer.set_cv_image(None)
            self.lbl_photo_status.setText("Belum ada foto")
            self.btn_proceed.setEnabled(False)

        self._update_thumbnails()

    def _clear_photos(self):
        """Mereset buffer semua foto."""
        self.captured_images.clear()
        self.selected_image_index = -1
        self._update_thumbnails()
        self.image_viewer.set_cv_image(None)
        self.lbl_photo_status.setText("Belum ada foto")
        self.btn_proceed.setEnabled(False)

    def _update_thumbnails(self):
        """Memperbarui visual thumbnail preview dan status tombol hapus."""
        for i, lbl in enumerate(self.thumb_labels):
            if i < len(self.captured_images):
                img = self.captured_images[i]
                h, w, ch = img.shape
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
                pix = QPixmap.fromImage(qimg).scaled(72, 54, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                lbl.setPixmap(pix)

                if i == self.selected_image_index:
                    lbl.setStyleSheet("border: 2px solid #10b981; border-radius: 8px; background-color: #122822;")
                else:
                    lbl.setStyleSheet("border: 1px solid #475569; border-radius: 8px; background-color: #18202d;")
            else:
                lbl.clear()
                lbl.setText(f"Slot {i+1}")
                lbl.setStyleSheet("""
                    background-color: #18202d;
                    border: 1.5px dashed #334155;
                    border-radius: 8px;
                    color: #475569;
                    font-size: 11px;
                """)

        if hasattr(self, "btn_delete_photo"):
            self.btn_delete_photo.setEnabled(len(self.captured_images) > 0 and self.selected_image_index >= 0)

    def build_observation_package(self) -> Optional[dict]:
        """Mengekstrak kontur dan menyusun paket data pengamatan dari foto aktif."""
        if not self.captured_images or self.selected_image_index < 0:
            self._load_initial_sample()
            if not self.captured_images:
                return None
            self.selected_image_index = 0

        active_img = self.captured_images[self.selected_image_index]
        h, w = active_img.shape[:2]

        # 1. Ekstraksi batas ufuk mar'i
        try:
            horizon_y, mask = self.cv_detector.detect_horizon(
                active_img,
                method=HorizonDetector.METHOD_GRADIENT,
                blur_kernel=5,
                smooth_window=15
            )
        except Exception:
            return None

        # 2. Perhitungan Profil Sudut Falak
        profile_data = self.cv_detector.compute_horizon_profile(
            horizon_y=horizon_y,
            img_w=w,
            img_h=h,
            az_center=self.azimuth_val,
            hfov=15.0,
            vfov=8.5,
            tilt_center=self.elevation_val,
            elevation_m=self.altitude
        )

        # 3. Render Overlay Citra (Warna, Hitam-Putih CLAHE, dan Biner)
        bw_data = getattr(self.cv_detector, "last_bw_data", None) or self.cv_detector.preprocess_bw(active_img)
        enhanced_bw = bw_data["enhanced_bw"]
        binary_bw = bw_data["binary_bw"]

        overlay_img = self.cv_detector.render_overlay(
            image_bgr=active_img,
            horizon_y=horizon_y,
            azimuths=profile_data["azimuths"],
            elevations=profile_data["elevations"],
            target_az=self.azimuth_val,
            show_true_horizon=True,
            dip_deg=profile_data["dip_deg"],
            az_center=self.azimuth_val,
            hfov=15.0,
            vfov=8.5,
            tilt_center=self.elevation_val
        )

        overlay_bw = self.cv_detector.render_overlay(
            image_bgr=enhanced_bw,
            horizon_y=horizon_y,
            azimuths=profile_data["azimuths"],
            elevations=profile_data["elevations"],
            target_az=self.azimuth_val,
            show_true_horizon=True,
            dip_deg=profile_data["dip_deg"],
            az_center=self.azimuth_val,
            hfov=15.0,
            vfov=8.5,
            tilt_center=self.elevation_val
        )

        overlay_binary = self.cv_detector.render_overlay(
            image_bgr=binary_bw,
            horizon_y=horizon_y,
            azimuths=profile_data["azimuths"],
            elevations=profile_data["elevations"],
            target_az=self.azimuth_val,
            show_true_horizon=True,
            dip_deg=profile_data["dip_deg"],
            az_center=self.azimuth_val,
            hfov=15.0,
            vfov=8.5,
            tilt_center=self.elevation_val
        )

        # 4. Susun paket data lengkap untuk Layar 3 & Layar 4
        package = {
            "raw_image": active_img,
            "overlay_image": overlay_img,
            "overlay_bw": overlay_bw,
            "overlay_binary": overlay_binary,
            "enhanced_bw": enhanced_bw,
            "binary_bw": binary_bw,
            "profile_data": profile_data,
            "azimuth": self.azimuth_val,
            "elevation": self.elevation_val,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "location_name": "Pos Observasi Falak Lapangan",
            "is_manual_gps": self.is_manual_gps,
        }
        return package

    def _process_and_proceed(self):
        """Mengekstrak kontur ufuk mar'i dengan Computer Vision dan pindah ke Layar 3."""
        if not self.captured_images or self.selected_image_index < 0:
            QMessageBox.warning(self, "Peringatan", "Silakan potret atau muat minimal satu foto.")
            return

        package = self.build_observation_package()
        if package is None:
            QMessageBox.critical(self, "Gagal Ekstraksi", "Terjadi kesalahan saat mengekstrak kontur ufuk.")
            return

        # Pindah ke Layar 3
        self.proceed_to_result.emit(package)

    def closeEvent(self, event):
        if self.camera_worker.isRunning():
            self.camera_worker.stop()
        event.accept()
