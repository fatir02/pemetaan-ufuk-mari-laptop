"""
screen_report.py
LAYAR 4: EVALUASI LAPANGAN & CETAK LAPORAN PDF RESMI
Menangani:
- Input form catatan evaluator: Nama Petugas, Deskripsi Hasil, Rekomendasi.
- Penerbitan Dokumen PDF Berita Acara & Laporan Falak Resmi (ReportLab).
- Ekspor data CSV sudut azimut-elevasi & gambar grafik PNG.
- Tombol navigasi kembali atau mulai pengamatan baru.
"""

import os
import time
from typing import Optional, Dict, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTextEdit, QLineEdit,
    QMessageBox, QFileDialog, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal

from core.report_generator import export_pdf_report, export_csv_data
from core.paths import get_app_dir


class ScreenReport(QWidget):
    """Layar Pelaporan & Dokumen PDF."""
    back_to_result = pyqtSignal()
    start_new_observation = pyqtSignal()
    proceed_to_preview = pyqtSignal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_package: Optional[Dict[str, Any]] = None

        self._init_ui()

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
        content_layout.setContentsMargins(20, 16, 20, 16)
        content_layout.setSpacing(14)

        # Header Layar 4
        head_row = QHBoxLayout()
        self.btn_back = QPushButton("⬅️ Kembali ke Hasil")
        self.btn_back.setStyleSheet("""
            QPushButton {
                background-color: #1e2634; color: #e2e8f0;
                border: 1px solid #334155; border-radius: 8px;
                padding: 6px 14px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #2a3445; color: #ffffff; }
        """)
        self.btn_back.clicked.connect(self.back_to_result.emit)
        head_row.addWidget(self.btn_back)

        head_row.addStretch()

        lbl_head = QLabel("EVALUASI LAPANGAN & PENERBITAN LAPORAN PDF")
        lbl_head.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 800; letter-spacing: 0.5px;")
        head_row.addWidget(lbl_head)

        head_row.addStretch()
        content_layout.addLayout(head_row)

        # Kartu Form Evaluasi
        form_card = QFrame()
        form_card.setStyleSheet("""
            background-color: #121721;
            border: 1px solid #1e2634;
            border-radius: 12px;
            padding: 16px 20px;
        """)
        form_l = QVBoxLayout(form_card)
        form_l.setSpacing(10)

        # Baris 1: Nama Lokasi & Petugas
        r1 = QHBoxLayout()
        r1.setSpacing(16)

        c1 = QVBoxLayout()
        c1.setSpacing(3)
        c1.addWidget(QLabel("Nama Lokasi / Pos Observasi Falak:"))
        self.edit_location = QLineEdit("Pos Observasi Falak Lapangan")
        self.edit_location.setStyleSheet(self._input_style())
        c1.addWidget(self.edit_location)
        r1.addLayout(c1)

        c2 = QVBoxLayout()
        c2.setSpacing(3)
        c2.addWidget(QLabel("Petugas Pengamat / Tim Falak:"))
        self.edit_observer = QLineEdit("Tim Falak & Astronomi")
        self.edit_observer.setStyleSheet(self._input_style())
        c2.addWidget(self.edit_observer)
        r1.addLayout(c2)

        form_l.addLayout(r1)

        # Baris 2: Deskripsi Hasil Pengamatan
        form_l.addWidget(QLabel("Deskripsi Hasil Analisis Ufuk:"))
        self.text_desc = QTextEdit()
        self.text_desc.setMaximumHeight(80)
        self.text_desc.setStyleSheet(self._input_style())
        form_l.addWidget(self.text_desc)

        # Baris 3: Rekomendasi Kelayakan Rukyatul Hilal
        form_l.addWidget(QLabel("Rekomendasi Kelayakan Tempat Rukyatul Hilal:"))
        self.text_rec = QTextEdit()
        self.text_rec.setMaximumHeight(80)
        self.text_rec.setStyleSheet(self._input_style())
        form_l.addWidget(self.text_rec)

        content_layout.addWidget(form_card)

        # Kartu Aksi Penerbitan & Ekspor
        action_card = QFrame()
        action_card.setStyleSheet("""
            background-color: #121721;
            border: 1px solid #1e2634;
            border-radius: 12px;
            padding: 16px 20px;
        """)
        act_l = QVBoxLayout(action_card)
        act_l.setSpacing(12)

        lbl_act_title = QLabel("AKSI PENERBITAN BERKAS & DOKUMEN")
        lbl_act_title.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        act_l.addWidget(lbl_act_title)

        # Tombol Cetak PDF Utama & Masuk ke Menu Preview
        self.btn_print_pdf = QPushButton("🖨️  CETAK & PREVIEW LAPORAN RESMI (PDF BERITA ACARA)")
        self.btn_print_pdf.setCursor(Qt.PointingHandCursor)
        self.btn_print_pdf.setMinimumHeight(52)
        self.btn_print_pdf.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #34d399;
                border-radius: 10px;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #34d399, stop:1 #10b981);
            }
        """)
        self.btn_print_pdf.clicked.connect(self._generate_pdf_report)
        act_l.addWidget(self.btn_print_pdf)

        # Baris Tombol Ekspor Tambahan
        sub_act_row = QHBoxLayout()
        sub_act_row.setSpacing(10)

        self.btn_export_csv = QPushButton("📄 Ekspor Data Numerik (CSV)")
        self.btn_export_csv.setStyleSheet(self._sub_btn_style())
        self.btn_export_csv.clicked.connect(self._export_csv)
        sub_act_row.addWidget(self.btn_export_csv)

        self.btn_new_observation = QPushButton("🚀 Mulai Pengamatan Baru")
        self.btn_new_observation.setStyleSheet(self._sub_btn_style("#0284c7", "#38bdf8"))
        self.btn_new_observation.clicked.connect(self.start_new_observation.emit)
        sub_act_row.addWidget(self.btn_new_observation)

        act_l.addLayout(sub_act_row)
        content_layout.addWidget(action_card)

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

    def _input_style(self) -> str:
        return """
            background-color: #18202d;
            color: #ffffff;
            border: 1px solid #283344;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 12px;
        """

    def _sub_btn_style(self, bg: str = "#1e2634", border: str = "#334155") -> str:
        return f"""
            QPushButton {{
                background-color: {bg};
                color: #ffffff;
                border: 1px solid {border};
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #2a3445;
            }}
        """

    def load_data(self, data_package: Dict[str, Any]):
        """Memuat paket data hasil dan menyusun draft teks cerdas."""
        self.data_package = data_package

        target_analysis = data_package.get("target_analysis", {})
        az = data_package.get("azimuth", 270.0)
        target_az = target_analysis.get("target_az", az)
        target_alt = target_analysis.get("target_alt", 0.0)
        is_clear = target_analysis.get("is_clear", True)
        desc_cat = target_analysis.get("description", "Ufuk Mar'i")

        # Draft teks otomatis jika belum diisi oleh pengguna
        smart_desc = (
            f"Berdasarkan ekstraksi kontur computer vision pada azimut bidikan {az:.2f}°, "
            f"diperoleh tinggi rintangan ufuk pada azimut sasaran {target_az:.2f}° sebesar {target_alt:+.2f}°. "
            f"Kondisi ufuk: {desc_cat}."
        )
        if not self.text_desc.toPlainText().strip():
            self.text_desc.setPlainText(smart_desc)

        if not self.text_rec.toPlainText().strip():
            if is_clear or target_alt <= 0.0:
                smart_rec = (
                    f"Lokasi pengamatan REKOMENDED (LAYAK). Tidak terdapat rintangan signifikan pada azimut {target_az:.2f}°. "
                    f"Ufuk mar'i berada di bawah atau sejajar ufuk hakiki sehingga sangat mendukung rukyatul hilal."
                )
            else:
                smart_rec = (
                    f"Lokasi pengamatan PERLU DIPERHATIKAN. Terdapat halangan daratan/bukit setinggi {target_alt:+.2f}° "
                    f"pada azimut {target_az:.2f}°. Hilal dengan ketinggian di bawah rintangan ini akan terhalang."
                )
            self.text_rec.setPlainText(smart_rec)

    def _ensure_data_package(self) -> bool:
        """Memastikan data pengamatan tersedia, memuat dari observasi jika belum ada."""
        if self.data_package is not None:
            return True

        main_win = self.window()
        if hasattr(main_win, "screen_observation") and hasattr(main_win, "screen_result"):
            pkg = main_win.screen_observation.build_observation_package()
            if pkg:
                main_win.screen_result.load_data(pkg)
                self.load_data(main_win.screen_result.data_package)
                return True
        return False

    def _generate_pdf_report(self):
        """Membuat dokumen PDF resmi dan menyimpannya di folder exports/."""
        if not self._ensure_data_package():
            QMessageBox.warning(
                self,
                "Peringatan",
                "Belum ada data pengamatan yang dapat dicetak.\n"
                "Silakan lakukan pengamatan di menu 'Pengamatan' terlebih dahulu."
            )
            return

        exports_dir = os.path.join(get_app_dir(), "exports")
        os.makedirs(exports_dir, exist_ok=True)
        pdf_path = os.path.join(exports_dir, f"Laporan_Ufuk_{int(time.time())}.pdf")

        try:
            export_pdf_report(
                output_pdf_path=pdf_path,
                location_name=self.edit_location.text().strip() or "Pos Observasi Falak",
                latitude=self.data_package["latitude"],
                longitude=self.data_package["longitude"],
                elevation_m=self.data_package["altitude"],
                az_center=self.data_package["azimuth"],
                hfov=15.0,
                vfov=8.5,
                tilt_center=self.data_package["elevation"],
                dip_deg=self.data_package["profile_data"].get("dip_deg", 0.197),
                profile_data=self.data_package["profile_data"],
                overlay_img_bgr=self.data_package["overlay_image"],
                target_analysis=self.data_package.get("target_analysis"),
                observer_notes=self.text_desc.toPlainText().strip(),
                recommendation_text=self.text_rec.toPlainText().strip(),
            )
            # Picu transisi ke Menu Preview Laporan
            self.proceed_to_preview.emit(pdf_path, self.data_package)
        except Exception as e:
            QMessageBox.critical(self, "Gagal Cetak PDF", f"Terjadi kesalahan saat membuat PDF:\n{str(e)}")

    def _export_csv(self):
        """Mengekspor data sudut ke CSV."""
        if not self._ensure_data_package():
            QMessageBox.warning(self, "Peringatan", "Belum ada data numerik pengamatan untuk diekspor.")
            return

        exports_dir = os.path.join(get_app_dir(), "exports")
        os.makedirs(exports_dir, exist_ok=True)
        csv_path = os.path.join(exports_dir, f"Data_Ufuk_{int(time.time())}.csv")

        try:
            export_csv_data(
                output_csv_path=csv_path,
                profile_data=self.data_package["profile_data"],
                location_name=self.edit_location.text().strip() or "Pos Observasi",
                az_center=self.data_package["azimuth"],
                dip_deg=self.data_package["profile_data"].get("dip_deg", 0.197),
            )
            QMessageBox.information(self, "Sukses Ekspor CSV", f"File data CSV berhasil disimpan:\n\n{csv_path}")
        except Exception as e:
            QMessageBox.critical(self, "Gagal Ekspor CSV", f"Terjadi kesalahan:\n{str(e)}")
