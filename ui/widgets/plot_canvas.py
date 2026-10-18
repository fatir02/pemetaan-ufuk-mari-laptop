"""
plot_canvas.py
Widget Matplotlib FigureCanvasQTAgg terintegrasi PyQt5 untuk visualisasi profil ufuk mar'i.
Mendukung interaksi kursor azimut, garis referensi falak (ufuk hakiki & dip),
dan ekspor gambar berkualitas tinggi.
"""

from typing import Optional
import numpy as np
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas


class HorizonPlotCanvas(QWidget):
    """
    Widget visualisasi grafik profil ufuk mar'i dengan Matplotlib terintegrasi PyQt5.
    """
    azimuth_clicked = pyqtSignal(float)

    def __init__(self, parent=None, width=7, height=3, dpi=100):
        super().__init__(parent)

        self.figure = Figure(figsize=(width, height), dpi=dpi)
        self.figure.patch.set_facecolor("#181c24")
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

        self._azimuths = None
        self._elevations = None
        self._dip_deg = 0.0
        self._target_az = None
        self._target_alt = None

        self._init_empty_plot()
        self.canvas.mpl_connect("button_press_event", self._on_canvas_click)

    def _init_empty_plot(self):
        """Menampilkan placeholder plot sebelum ada ekstraksi data."""
        self.ax.clear()
        self.ax.set_facecolor("#121417")
        self.ax.text(
            0.5, 0.5,
            "Belum ada data ekstraksi ufuk mar'i.\nSilakan tangkap frame atau muat gambar pada modul di atas.",
            color="#78909c",
            ha="center", va="center",
            transform=self.ax.transAxes,
            fontsize=10,
            fontweight="500",
        )
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for spine in self.ax.spines.values():
            spine.set_color("#2b3240")
        self.canvas.draw()

    def update_plot(
        self,
        azimuths: np.ndarray,
        elevations: np.ndarray,
        dip_deg: float = 0.0,
        target_az: Optional[float] = None,
        target_alt: Optional[float] = None,
    ):
        """
        Memperbarui kurva kontur ufuk mar'i dan garis referensi falak.
        """
        self._azimuths = azimuths
        self._elevations = elevations
        self._dip_deg = dip_deg
        self._target_az = target_az
        self._target_alt = target_alt

        self.ax.clear()
        self.ax.set_facecolor("#13161c")

        # Set batas sumbu awal agar transformasi non-singular
        min_y = min(-dip_deg - 0.5, float(np.min(elevations)) - 0.5, -1.0)
        max_y = max(float(np.max(elevations)) + 0.8, 2.0)
        self.ax.set_xlim(azimuths[0], azimuths[-1])
        self.ax.set_ylim(min_y, max_y)

        # 1. Baseline relatif: titik terendah profil sengaja ditetapkan 0°.
        self.ax.plot(
            [azimuths[0], azimuths[-1]], [0.0, 0.0],
            color="#4fc3f7", linestyle="--", linewidth=1.2,
            label="Baseline Ufuk Relatif (0.00°)", alpha=0.9
        )

        # 2. Kurva Profil Ufuk Mar'i relatif terhadap baseline tersebut.
        self.ax.plot(
            azimuths, elevations,
            color="#ff5252", linewidth=2.0,
            label="Kontur Ufuk Mar'i", zorder=3
        )
        # Shading bukit/halangan di bawah kontur
        self.ax.fill_between(azimuths, elevations, min_y, color="#ff1744", alpha=0.15, zorder=2)

        # 3. Kursor Azimut Sasaran
        if target_az is not None:
            self.ax.plot(
                [target_az, target_az], [min_y, max_y],
                color="#e040fb", linestyle="-.", linewidth=1.5,
                label=f"Sasaran ({target_az:.2f}°)", zorder=4
            )
            if target_alt is not None:
                self.ax.scatter([target_az], [target_alt], color="#e040fb", s=60, zorder=5)
                self.ax.annotate(
                    f"{target_alt:+.2f}°",
                    xy=(target_az, target_alt),
                    xytext=(target_az + 0.15, target_alt + 0.25),
                    fontsize=8,
                    fontweight="bold",
                    color="#ffffff",
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="#4a148c", edgecolor="#e040fb", alpha=0.85),
                )

        # Konfigurasi Sumbu
        self.ax.set_xlim(azimuths[0], azimuths[-1])
        max_y = max(float(np.max(elevations)) + 0.8, 2.0)
        self.ax.set_ylim(min_y, max_y)

        self.ax.set_xlabel("Rentang Azimut Bidikan (°)", color="#cfd8dc", fontsize=9, fontweight="bold")
        self.ax.set_ylabel("Elevasi Relatif dari Baseline 0°", color="#cfd8dc", fontsize=9, fontweight="bold")
        self.ax.set_title("Profil Elevasi Relatif Ufuk Mar'i vs Azimut", color="#ffffff", fontsize=10, fontweight="bold", pad=8)

        # Tampilan grid dan border
        self.ax.grid(True, linestyle="--", alpha=0.25, color="#78909c")
        self.ax.tick_params(colors="#90a4ae", labelsize=8)
        for spine in self.ax.spines.values():
            spine.set_color("#2b3240")

        # Legenda
        self.ax.legend(
            loc="upper right",
            fontsize=8,
            facecolor="#1e232d",
            edgecolor="#374151",
            labelcolor="#eceff1",
            framealpha=0.85
        )

        try:
            self.figure.tight_layout()
        except Exception:
            pass
        self.canvas.draw()

    def set_target_azimuth(self, target_az: float, target_alt: float):
        """Memperbarui garis sasaran tanpa perlu merender ulang keseluruhan data."""
        if self._azimuths is not None and self._elevations is not None:
            self.update_plot(
                self._azimuths,
                self._elevations,
                self._dip_deg,
                target_az=target_az,
                target_alt=target_alt,
            )

    def _on_canvas_click(self, event):
        """Menangkap klik pengguna pada grafik untuk memilih azimut sasaran."""
        if event.inaxes == self.ax and event.xdata is not None:
            self.azimuth_clicked.emit(float(event.xdata))

    def save_figure(self, filepath: str, dpi: int = 300) -> bool:
        """Menyimpan grafik ke file PNG/JPG/PDF."""
        try:
            self.figure.savefig(filepath, dpi=dpi, facecolor=self.figure.get_facecolor(), bbox_inches="tight")
            return True
        except Exception:
            return False
