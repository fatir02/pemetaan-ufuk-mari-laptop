"""
screen_result.py
LAYAR 3: HASIL OLAH & KURVA PROFIL UFUK
Tampilan terpadu dalam satu layar:
- Foto jepretan dengan overlay garis kontur ufuk mar'i (OpenCV).
- Data numerik sensor & koordinat (Azimuth, Elevasi, GPS, Alt, Dip).
- Visualisasi grafik kurva profil ufuk (Matplotlib).
- Slider azimut sasaran hilal & status kelayakan falak.
- Tombol aksi: [Foto Ulang] & [Lanjut ke Cetak PDF].
"""

from typing import Optional, Dict, Any
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QSlider, QSplitter, QScrollArea, QLineEdit,
    QInputDialog,
)
from PyQt5.QtCore import Qt, pyqtSignal, QRectF

from core.falak_calc import classify_obstacle, format_dms, pixel_to_azimuth_elevation
from ui.widgets.image_viewer import InteractiveImageViewer, FullscreenImageViewer
from ui.widgets.plot_canvas import HorizonPlotCanvas


class ScreenResult(QWidget):
    """Layar Hasil Olah & Kurva Profil Ufuk Mar'i."""
    retake_requested = pyqtSignal()
    proceed_to_report = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_package: Optional[Dict[str, Any]] = None
        self.target_azimuth: float = 270.0

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)

        # ==========================================
        # 1. HEADER RINGKAS LAYAR HASIL
        # ==========================================
        header_bar = QHBoxLayout()

        self.btn_retake = QPushButton("↺  Foto Ulang")
        self.btn_retake.setStyleSheet("""
            QPushButton {
                background-color: #1e2634; color: #e2e8f0;
                border: 1px solid #334155; border-radius: 8px;
                padding: 8px 18px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #2a3445; color: #ffffff; }
        """)
        self.btn_retake.clicked.connect(self.retake_requested.emit)
        header_bar.addWidget(self.btn_retake)

        header_bar.addStretch()

        lbl_head = QLabel("HASIL EKSTRAKSI KONTUR & PROFIL UFUK MAR'I")
        lbl_head.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 800; letter-spacing: 0.5px;")
        header_bar.addWidget(lbl_head)

        header_bar.addStretch()

        self.btn_to_report = QPushButton("📑  Lanjut ke Cetak Laporan ➡️")
        self.btn_to_report.setCursor(Qt.PointingHandCursor)
        self.btn_to_report.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #0369a1);
                color: #ffffff; font-size: 13px; font-weight: bold;
                border: 1px solid #38bdf8; border-radius: 8px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369a1, stop:1 #0284c7);
            }
        """)
        self.btn_to_report.clicked.connect(self._on_proceed_report)
        header_bar.addWidget(self.btn_to_report)

        main_layout.addLayout(header_bar)

        # ==========================================
        # 2. RESPONSIF CONTAINER: KIRI (FOTO & DATA) & KANAN (GRAFIK KURVA)
        # ==========================================
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        scroll_content = QWidget()
        scroll_content_layout = QVBoxLayout(scroll_content)
        scroll_content_layout.setContentsMargins(0, 0, 0, 0)
        scroll_content_layout.setSpacing(10)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        # PANEL KIRI: Foto Overlay & Tabel Numerik
        self.left_box = QWidget()
        left_layout = QVBoxLayout(self.left_box)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)

        lbl_foto_title = QLabel("Citra Kontur Ufuk Mar'i (Garis Kuning = Batas Daratan):")
        lbl_foto_title.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px;")
        left_layout.addWidget(lbl_foto_title)

        self.image_viewer = InteractiveImageViewer(placeholder_text="Menunggu Data Hasil...")
        self.image_viewer.setMinimumHeight(180)
        self.image_viewer.setCursor(Qt.PointingHandCursor)
        self.image_viewer.setToolTip("Klik untuk membuka gambar fullscreen dan gunakan scroll mouse untuk zoom")
        self.image_viewer.pixel_clicked.connect(self._open_fullscreen_image)
        left_layout.addWidget(self.image_viewer, stretch=3)

        # Kartu Data Numerik Terukur
        data_card = QFrame()
        data_card.setStyleSheet("""
            background-color: #121721;
            border: 1px solid #1e2634;
            border-radius: 10px;
            padding: 8px 12px;
        """)
        card_l = QVBoxLayout(data_card)
        card_l.setSpacing(4)

        lbl_data_title = QLabel("DATA SENSOR & KOORDINAT PENGAMATAN")
        lbl_data_title.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
        card_l.addWidget(lbl_data_title)

        self.row_az = self._create_data_row("Sudut Azimuth Bidikan", "270.00°")
        self.row_alt = self._create_data_row("Kemiringan Optik (Tilt)", "0.00°")
        self.row_gps = self._create_data_row("Koordinat GPS (φ, λ)", "-07° 58' 48\", 110° 18' 22\"")
        self.row_height = self._create_data_row("Ketinggian Tempat (h)", "45.0 mdpl")
        self.row_dip = self._create_data_row("Kerendahan Ufuk Laut (Dip)", "-0.20°")

        for r in [self.row_az, self.row_alt, self.row_gps, self.row_height, self.row_dip]:
            card_l.addWidget(r)

        left_layout.addWidget(data_card, stretch=2)
        self.splitter.addWidget(self.left_box)

        # PANEL KANAN: Grafik Kurva Matplotlib & Analisis Sasaran
        self.right_box = QWidget()
        right_layout = QVBoxLayout(self.right_box)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(8)

        lbl_chart_title = QLabel("Kurva Profil Ufuk Mar'i (Elevasi Relatif, Baseline Terendah = 0°):")
        lbl_chart_title.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px;")
        right_layout.addWidget(lbl_chart_title)

        self.plot_canvas = HorizonPlotCanvas(self, width=6, height=3)
        self.plot_canvas.setMinimumHeight(180)
        self.plot_canvas.azimuth_clicked.connect(self._on_plot_azimuth_clicked)
        right_layout.addWidget(self.plot_canvas, stretch=3)

        # Inspeksi Titik Azimut Sasaran Hilal
        inspect_card = QFrame()
        inspect_card.setStyleSheet("""
            background-color: #121721;
            border: 1px solid #1e2634;
            border-radius: 10px;
            padding: 10px 14px;
        """)
        inspect_l = QVBoxLayout(inspect_card)
        inspect_l.setSpacing(6)

        slider_row = QHBoxLayout()
        lbl_slider_txt = QLabel("Inspeksi Azimut Hilal/Objek:")
        lbl_slider_txt.setStyleSheet("color: #e2e8f0; font-weight: bold; font-size: 11px;")
        slider_row.addWidget(lbl_slider_txt)

        self.lbl_target_az_val = QLabel("270.00°")
        self.lbl_target_az_val.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px;")
        slider_row.addWidget(self.lbl_target_az_val)

        slider_row.addStretch()
        inspect_l.addLayout(slider_row)

        self.target_slider = QSlider(Qt.Horizontal)
        self.target_slider.setRange(26000, 28000)
        self.target_slider.setValue(27000)
        self.target_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 6px; background: #1e2634; border-radius: 3px; }
            QSlider::sub-page:horizontal { background: #38bdf8; border-radius: 3px; }
            QSlider::handle:horizontal {
                background: #ff5252; width: 16px; margin-top: -5px; margin-bottom: -5px; border-radius: 8px;
            }
        """)
        self.target_slider.valueChanged.connect(self._on_target_slider_changed)
        inspect_l.addWidget(self.target_slider)

        # Status Hasil Analisis Pada Titik Tersebut
        status_row = QHBoxLayout()
        self.lbl_obstruction_elev = QLabel("Tinggi Halangan: --")
        self.lbl_obstruction_elev.setStyleSheet("color: #fbbf24; font-weight: bold; font-size: 12px;")
        status_row.addWidget(self.lbl_obstruction_elev)

        status_row.addStretch()

        self.lbl_recommendation_badge = QLabel("Status: Menganalisis...")
        self.lbl_recommendation_badge.setStyleSheet("""
            background-color: #10b981; color: #ffffff;
            font-size: 11px; font-weight: bold;
            padding: 4px 12px; border-radius: 10px;
        """)
        status_row.addWidget(self.lbl_recommendation_badge)

        inspect_l.addLayout(status_row)
        right_layout.addWidget(inspect_card, stretch=2)

        # Editor nama objek untuk versi desktop. Nilai awal berasal dari
        # klasifikasi otomatis, tetapi pengamat dapat mengoreksinya sebelum PDF.
        self.object_card = QFrame()
        self.object_card.setStyleSheet("""
            background-color: #121721; border: 1px solid #1e2634;
            border-radius: 10px; padding: 8px 12px;
        """)
        self.object_layout = QVBoxLayout(self.object_card)
        self.object_layout.setSpacing(6)
        obj_title = QLabel("OBJEK HALANGAN SKYLINE")
        obj_title.setStyleSheet("color: #38bdf8; font-size: 10px; font-weight: bold;")
        self.object_layout.addWidget(obj_title)
        self.object_empty = QLabel("Belum ada objek menonjol terdeteksi.")
        self.object_empty.setStyleSheet("color: #64748b; font-size: 10px;")
        self.object_layout.addWidget(self.object_empty)
        self.object_editors = []
        right_layout.addWidget(self.object_card, stretch=2)

        self.splitter.addWidget(self.right_box)
        scroll_content_layout.addWidget(self.splitter)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area, stretch=1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Responsif: jika lebar jendela sempit (< 850px, misalnya layar HP/tablet vertikal),
        # otomatis ubah susunan menjadi vertikal: foto di atas, grafik di bawah
        if self.width() < 850:
            if self.splitter.orientation() != Qt.Vertical:
                self.splitter.setOrientation(Qt.Vertical)
                if hasattr(self, "left_box") and self.left_box.layout():
                    self.left_box.layout().setContentsMargins(0, 0, 0, 8)
                if hasattr(self, "right_box") and self.right_box.layout():
                    self.right_box.layout().setContentsMargins(0, 8, 0, 0)
        else:
            if self.splitter.orientation() != Qt.Horizontal:
                self.splitter.setOrientation(Qt.Horizontal)
                if hasattr(self, "left_box") and self.left_box.layout():
                    self.left_box.layout().setContentsMargins(0, 0, 8, 0)
                if hasattr(self, "right_box") and self.right_box.layout():
                    self.right_box.layout().setContentsMargins(8, 0, 0, 0)

    def _create_data_row(self, label: str, value: str) -> QFrame:
        """Baris item data numerik."""
        row = QFrame()
        l = QHBoxLayout(row)
        l.setContentsMargins(0, 2, 0, 2)
        lbl_k = QLabel(label)
        lbl_k.setStyleSheet("color: #94a3b8; font-size: 11px;")
        lbl_v = QLabel(value)
        lbl_v.setObjectName("Val")
        lbl_v.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 11px;")
        l.addWidget(lbl_k)
        l.addStretch()
        l.addWidget(lbl_v)
        return row

    def _open_fullscreen_image(
        self,
        _x: int = 0,
        _y: int = 0,
        focus_rect: Optional[QRectF] = None,
        selected_range=None,
    ):
        """Buka overlay hasil dalam viewer fullscreen interaktif."""
        # Semua mode fullscreen menggunakan foto mentah dan layer vektor
        # dinamis. Overlay bitmap hanya dipakai pada panel preview kecil.
        image = None
        horizon_y = None
        target_x = None
        obstacles = None
        if self.data_package is not None:
            raw = self.data_package.get("raw_image")
            if raw is not None:
                image = raw.copy()
                profile = self.data_package["profile_data"]
                horizon_y = profile.get("horizon_y")
                obstacles = profile.get("prominent_obstacles", [])
                azimuths = profile.get("azimuths")
                if azimuths is not None and len(azimuths):
                    target_x = int(np.argmin(np.abs(np.asarray(azimuths) - self.target_azimuth)))
        if image is None:
            image = self.image_viewer.get_cv_image()
        if image is None:
            return
        # Simpan referensi agar dialog non-modal tidak dihapus oleh garbage
        # collector dan pengguna tetap dapat menutupnya lewat Esc/F11/tombol.
        if getattr(self, "fullscreen_viewer", None) is not None:
            self.fullscreen_viewer.close()
        self.fullscreen_viewer = FullscreenImageViewer(
            image,
            self,
            focus_rect=focus_rect,
            horizon_y=horizon_y,
            selected_range=selected_range,
            target_x=target_x,
            obstacles=obstacles,
        )
        self.fullscreen_viewer.view.horizon_edited.connect(self._save_manual_horizon)
        self.fullscreen_viewer.view.add_object_requested.connect(self._add_manual_object)
        self.fullscreen_viewer.view.obstacle_range_edited.connect(self._save_object_range)
        self.fullscreen_viewer.showFullScreen()

    def _save_object_range(self, index: int, x_start: int, x_end: int):
        """Simpan perubahan lebar penanda H dan rentang azimut objek."""
        if self.data_package is None:
            return
        profile = self.data_package["profile_data"]
        objects = profile.get("prominent_obstacles", [])
        if not (0 <= index < len(objects)):
            return
        width = len(profile["azimuths"])
        xs = max(0, min(width - 1, int(x_start)))
        xe = max(xs + 1, min(width - 1, int(x_end)))
        obj = objects[index]
        obj["x_start"], obj["x_end"] = xs, xe
        obj["az_start"] = float(profile["azimuths"][xs])
        obj["az_end"] = float(profile["azimuths"][xe])
        obj["is_manual_range"] = True
        obj["text"] = (
            f"{obj.get('label', 'Halangan Ufuk')}: Az {obj['az_start']:.2f}-"
            f"{obj['az_end']:.2f} deg | Alt {obj.get('elevation', 0):+.2f} deg"
        )
        obj["short_text"] = (
            f"Az {obj['az_start']:.2f}°-{obj['az_end']:.2f}°, "
            f"Alt {obj.get('elevation', 0):+.2f}°"
        )
        self._refresh_overlay_with_object_names()
        self._populate_object_editors()

    def _recalculate_profile_from_horizon(self, horizon_y):
        """Sinkronkan elevasi profil setelah koreksi garis manual."""
        if self.data_package is None:
            return
        profile = self.data_package["profile_data"]
        raw = self.data_package.get("raw_image")
        if raw is None:
            return
        height, width = raw.shape[:2]
        horizon = np.clip(np.asarray(horizon_y, dtype=np.float64), 0, height - 1)
        azimuths, absolute_elevations = pixel_to_azimuth_elevation(
            x=np.arange(width),
            y=horizon,
            img_w=width,
            img_h=height,
            az_center=float(profile.get("az_center", self.data_package["azimuth"])),
            hfov=float(profile.get("hfov", 15.0)),
            vfov=profile.get("vfov"),
            tilt_center=float(profile.get("tilt_center", self.data_package["elevation"])),
        )
        elevations = np.asarray(absolute_elevations, dtype=np.float64)
        baseline = float(np.min(elevations))
        elevations -= baseline
        profile["horizon_y"] = horizon
        profile["azimuths"] = np.asarray(azimuths, dtype=np.float64)
        profile["elevations"] = elevations
        profile["baseline_raw_elevation"] = baseline
        profile["stats"].update({
            "min_elevation": float(np.min(elevations)),
            "min_azimuth": float(profile["azimuths"][int(np.argmin(elevations))]),
            "max_elevation": float(np.max(elevations)),
            "max_azimuth": float(profile["azimuths"][int(np.argmax(elevations))]),
            "mean_elevation": float(np.mean(elevations)),
        })
        for obj in profile.get("prominent_obstacles", []):
            x = max(0, min(width - 1, int(obj.get("x", 0))))
            obj["y"] = int(round(horizon[x]))
            obj["elevation"] = float(elevations[x])

    def _save_manual_horizon(self, horizon_y):
        self._recalculate_profile_from_horizon(horizon_y)
        self._refresh_overlay_with_object_names()
        self._update_analysis_at_azimuth(self.target_azimuth)

    def _add_manual_object(self, x: int, y: int):
        """Tambah objek yang terlewat melalui titik yang dipilih pengguna."""
        if self.data_package is None:
            return
        labels = ["Menara/Antena", "Vegetasi/Pohon", "Bangunan/Atap", "Halangan Ufuk"]
        label, accepted = QInputDialog.getItem(
            self,
            "Tambah Objek Skyline",
            "Pilih jenis objek pada titik ini:",
            labels,
            0,
            False,
        )
        if not accepted:
            return
        profile = self.data_package["profile_data"]
        horizon = np.asarray(profile["horizon_y"], dtype=np.float64).copy()
        width = len(horizon)
        x = max(0, min(width - 1, int(x)))
        radius = max(3, int(round(width * 0.004)))
        lo, hi = max(0, x - radius), min(width, x + radius + 1)
        # Titik pilihan menjadi pucuk; transisi Gaussian menyambungkannya secara
        # halus ke kontur lama sehingga tidak membentuk patahan vertikal kasar.
        offsets = np.arange(lo, hi) - x
        weights = np.exp(-0.5 * (offsets / max(1.0, radius * 0.48)) ** 2)
        horizon[lo:hi] = np.minimum(horizon[lo:hi], horizon[lo:hi] * (1.0 - weights) + float(y) * weights)
        self._recalculate_profile_from_horizon(horizon)

        azimuths = profile["azimuths"]
        elevations = profile["elevations"]
        class_keys = {
            "Menara/Antena": "tower_antenna",
            "Vegetasi/Pohon": "vegetation",
            "Bangunan/Atap": "building_roof",
            "Halangan Ufuk": "skyline_obstacle",
        }
        objects = profile.setdefault("prominent_obstacles", [])
        obj = {
            "id": len(objects) + 1,
            "x": x,
            "y": int(round(horizon[x])),
            "x_start": lo,
            "x_end": hi - 1,
            "azimuth": float(azimuths[x]),
            "az_start": float(azimuths[lo]),
            "az_end": float(azimuths[hi - 1]),
            "elevation": float(elevations[x]),
            "prominence": float(max(0.0, elevations[x] - np.median(elevations[lo:hi]))),
            "prominence_px": float(max(0.0, np.median(horizon[lo:hi]) - horizon[x])),
            "height_px": float(max(0.0, np.median(horizon[lo:hi]) - horizon[x])),
            "object_class": class_keys[label],
            "auto_label": label,
            "label": label,
            "source": "manual_annotation",
            "is_manual": True,
            "text": f"{label}: Az {azimuths[lo]:.2f}-{azimuths[hi - 1]:.2f} deg | Alt {elevations[x]:+.2f} deg",
            "short_text": f"Az {azimuths[lo]:.2f}°-{azimuths[hi - 1]:.2f}°, Alt {elevations[x]:+.2f}°",
        }
        objects.append(obj)
        profile["stats"]["prominent_count"] = len(objects)
        self._refresh_overlay_with_object_names()
        self._populate_object_editors()
        # Segarkan layer viewer saat ini dan kembali ke navigasi agar marker
        # baru langsung bisa diklik untuk melihat namanya.
        if getattr(self, "fullscreen_viewer", None) is not None:
            view = self.fullscreen_viewer.view
            view.set_horizon_overlay(
                profile["horizon_y"],
                target_x=int(np.argmin(np.abs(profile["azimuths"] - self.target_azimuth))),
                obstacles=objects,
            )
            self.fullscreen_viewer._set_mode("navigate")

    def _focus_skyline_object(self, index: int):
        """Buka fullscreen dan fokuskan citra pada rentang azimut objek."""
        if self.data_package is None:
            return
        objects = self.data_package["profile_data"].get("prominent_obstacles", [])
        image = self.image_viewer.get_cv_image()
        if image is None or not (0 <= index < len(objects)):
            return
        obj = objects[index]
        height, width = image.shape[:2]
        x0 = float(obj.get("x_start", obj.get("x", 0)))
        x1 = float(obj.get("x_end", obj.get("x", 0)))
        if x1 < x0:
            x0, x1 = x1, x0
        center_x = (x0 + x1) / 2.0
        tip_y = float(obj.get("y", height * 0.45))
        object_height = max(
            float(obj.get("height_px") or 0.0),
            float(obj.get("prominence_px") or 0.0),
            height * 0.06,
        )

        # Tampilkan konteks di kiri-kanan rentang azimut, bukan crop objek yang
        # terlalu sempit. Area vertikal mencakup puncak hingga skyline/kaki.
        focus_width = max((x1 - x0 + 1.0) * 8.0, width * 0.18)
        focus_height = max(object_height * 2.8, height * 0.30)
        center_y = min(height * 0.88, tip_y + object_height * 0.45)
        focus_rect = QRectF(
            center_x - focus_width / 2.0,
            center_y - focus_height / 2.0,
            focus_width,
            focus_height,
        )

        az_mid = (
            float(obj.get("az_start", obj.get("azimuth", self.target_azimuth)))
            + float(obj.get("az_end", obj.get("azimuth", self.target_azimuth)))
        ) / 2.0
        self.target_slider.setValue(int(round(az_mid * 100)))
        self._open_fullscreen_image(
            focus_rect=focus_rect,
            selected_range=(int(round(x0)), int(round(x1))),
        )

    def load_data(self, data_package: Dict[str, Any]):
        """Memuat paket data ekstraksi dari Layar 2."""
        self.data_package = data_package
        self.img_color = data_package.get("overlay_image")

        profile_data = data_package["profile_data"]
        azimuth = data_package["azimuth"]
        elevation = data_package["elevation"]
        lat = data_package["latitude"]
        lon = data_package["longitude"]
        alt = data_package["altitude"]
        dip_deg = profile_data.get("dip_deg", 0.197)

        # 1. Update foto overlay citra langsung dengan warna asli & kontur kuning OpenCV
        if self.img_color is not None:
            self.image_viewer.set_cv_image(self.img_color)

        # 2. Update baris data numerik
        self._set_row_val(self.row_az, f"{azimuth:.2f}°")
        self._set_row_val(self.row_alt, f"{elevation:+.2f}°")
        self._set_row_val(self.row_gps, f"{format_dms(lat, is_lat=True)}, {format_dms(lon, is_lon=True)}")
        self._set_row_val(self.row_height, f"{alt:.1f} mdpl")
        self._set_row_val(self.row_dip, f"-{dip_deg:.3f}°")

        # 3. Update range slider azimut sasaran sesuai data profil
        az_array = profile_data["azimuths"]
        az_min = float(az_array[0])
        az_max = float(az_array[-1])
        self.target_slider.setRange(int(az_min * 100), int(az_max * 100))
        mid_val = int(azimuth * 100)
        self.target_slider.setValue(max(int(az_min * 100), min(int(az_max * 100), mid_val)))

        # 4. Update grafik Matplotlib
        self._update_analysis_at_azimuth(azimuth)
        self._populate_object_editors()

    def _clear_object_editors(self):
        for editor_row in self.object_editors:
            editor_row.setParent(None)
            editor_row.deleteLater()
        self.object_editors = []

    def _populate_object_editors(self):
        """Tampilkan klasifikasi skyline dan editor nama pada desktop PyQt."""
        self._clear_object_editors()
        if self.data_package is None:
            return
        objects = self.data_package["profile_data"].get("prominent_obstacles", [])
        self.object_empty.setVisible(not bool(objects))
        for index, obj in enumerate(objects):
            row = QFrame()
            row_l = QHBoxLayout(row)
            row_l.setContentsMargins(0, 1, 0, 1)
            info = QPushButton(
                f"#{index + 1}  Az {obj.get('az_start', obj.get('azimuth', 0)):.2f}°–"
                f"{obj.get('az_end', obj.get('azimuth', 0)):.2f}°  "
                f"Alt {obj.get('elevation', 0):+.2f}°"
            )
            info.setCursor(Qt.PointingHandCursor)
            info.setToolTip("Klik untuk memperbesar objek pada gambar")
            info.setStyleSheet("""
                QPushButton { color:#94a3b8; font-size:10px; text-align:left;
                    background:#18202d; border:1px solid #273449;
                    border-radius:6px; padding:5px 7px; }
                QPushButton:hover { color:#ffffff; border-color:#38bdf8; background:#1e293b; }
            """)
            info.clicked.connect(lambda _checked=False, idx=index: self._focus_skyline_object(idx))
            edit = QLineEdit(str(obj.get("label") or f"Objek {index + 1}"))
            edit.setPlaceholderText("Nama objek skyline")
            edit.setStyleSheet("background:#18202d;color:white;border:1px solid #334155;border-radius:6px;padding:5px;")
            edit.editingFinished.connect(lambda idx=index, widget=edit: self._rename_object(idx, widget.text()))
            row_l.addWidget(info, stretch=2)
            row_l.addWidget(edit, stretch=2)
            self.object_layout.addWidget(row)
            self.object_editors.append(row)

    def _rename_object(self, index: int, new_name: str):
        if self.data_package is None:
            return
        objects = self.data_package["profile_data"].get("prominent_obstacles", [])
        if not (0 <= index < len(objects)):
            return
        name = new_name.strip() or objects[index].get("auto_label") or f"Objek {index + 1}"
        objects[index]["label"] = name
        objects[index]["text"] = (
            f"{name}: Az {objects[index].get('az_start', 0):.2f}-"
            f"{objects[index].get('az_end', 0):.2f} deg | "
            f"Alt {objects[index].get('elevation', 0):+.2f} deg"
        )
        self._refresh_overlay_with_object_names()

    def _refresh_overlay_with_object_names(self):
        """Render ulang overlay desktop dan simpan hasil untuk laporan PDF."""
        if self.data_package is None:
            return
        from core.cv_engine import HorizonDetector
        profile = self.data_package["profile_data"]
        raw = self.data_package.get("raw_image")
        if raw is None:
            return
        detector = HorizonDetector()
        overlay = detector.render_overlay(
            image_bgr=raw,
            horizon_y=profile["horizon_y"],
            azimuths=profile["azimuths"],
            elevations=profile["elevations"],
            target_az=self.target_azimuth,
            dip_deg=profile.get("dip_deg", 0.0),
            az_center=self.data_package["azimuth"],
            hfov=profile.get("hfov", 15.0),
            vfov=profile.get("vfov", 8.5),
            tilt_center=self.data_package["elevation"],
            prominent_obstacles=profile.get("prominent_obstacles", []),
            show_prominent_peaks=True,
        )
        self.data_package["overlay_image"] = overlay
        self.img_color = overlay
        self.image_viewer.set_cv_image(overlay)

    def _set_row_val(self, row_frame: QFrame, text: str):
        lbl = row_frame.findChild(QLabel, "Val")
        if lbl:
            lbl.setText(text)

    def _on_target_slider_changed(self, val_int: int):
        target_az = val_int / 100.0
        self.lbl_target_az_val.setText(f"{target_az:.2f}°")
        self._update_analysis_at_azimuth(target_az)

    def _on_plot_azimuth_clicked(self, az: float):
        self.target_slider.setValue(int(az * 100))

    def _update_analysis_at_azimuth(self, target_az: float):
        """Memperbarui nilai halangan dan grafik berdasarkan azimut sasaran terpilih."""
        if self.data_package is None:
            return
        self.target_azimuth = target_az

        profile_data = self.data_package["profile_data"]
        az_array = profile_data["azimuths"]
        el_array = profile_data["elevations"]
        dip_deg = profile_data.get("dip_deg", 0.0)

        # Cari indeks azimut terdekat
        idx = int(np.argmin(np.abs(az_array - target_az)))
        obstacle_alt = float(el_array[idx])

        # Klasifikasi halangan
        obs_result = classify_obstacle(obstacle_alt, dip_deg)
        status_text = obs_result["status"]
        category_text = obs_result["category"]
        is_clear = (status_text == "Bebas Halangan")

        self.lbl_obstruction_elev.setText(f"Tinggi Halangan: {obstacle_alt:+.2f}° ({format_dms(obstacle_alt)})")

        if is_clear:
            self.lbl_recommendation_badge.setText(f"✅ {status_text} (Layak)")
            self.lbl_recommendation_badge.setStyleSheet("""
                background-color: #10b981; color: #ffffff;
                font-size: 11px; font-weight: bold; padding: 4px 12px; border-radius: 10px;
            """)
        elif "Rendah" in status_text:
            self.lbl_recommendation_badge.setText(f"⚠️ {status_text}")
            self.lbl_recommendation_badge.setStyleSheet("""
                background-color: #f59e0b; color: #ffffff;
                font-size: 11px; font-weight: bold; padding: 4px 12px; border-radius: 10px;
            """)
        else:
            self.lbl_recommendation_badge.setText(f"❌ {status_text}")
            self.lbl_recommendation_badge.setStyleSheet("""
                background-color: #ef4444; color: #ffffff;
                font-size: 11px; font-weight: bold; padding: 4px 12px; border-radius: 10px;
            """)

        # Update grafik plot canvas
        self.plot_canvas.update_plot(
            azimuths=az_array,
            elevations=el_array,
            dip_deg=dip_deg,
            target_az=target_az,
            target_alt=obstacle_alt
        )

        # Simpan state analisis ke paket data
        self.data_package["target_analysis"] = {
            "target_az": target_az,
            "target_alt": obstacle_alt,
            "alt_obstacle": obstacle_alt,
            "is_clear": is_clear,
            "category": category_text,
            "status": status_text,
            "description": obs_result.get("recommendation", category_text),
            "severity": obs_result.get("severity", ""),
            "color": obs_result.get("color", "#00e676"),
            "recommendation": obs_result.get("recommendation", ""),
        }

    def _on_proceed_report(self):
        """Lanjut ke Layar 4 (Laporan)."""
        if self.data_package is not None:
            self.proceed_to_report.emit(self.data_package)
