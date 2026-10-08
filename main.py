"""
main.py
Titik masuk utama (entry point) aplikasi instrumen falak:
"APLIKASI PEMETAAN PROFIL UFUK MAR'I BERBASIS COMPUTER VISION"
Laboratorium Astronomi & Falak, Fakultas Syariah.
"""

import sys
import os

# Tambahkan direktori root aplikasi ke sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from ui.main_window import MainWindow


def main():
    # Aktifkan dukungan layar resolusi tinggi (High DPI Scaling) lintas resolusi
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    if hasattr(QApplication, "setHighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    app = QApplication(sys.argv)
    app.setApplicationName("PemetaanProfilUfukMari")

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.setWindowTitle("APLIKASI PEMETAAN PROFIL UFUK MAR'I (LAPTOP EDITION)")
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
