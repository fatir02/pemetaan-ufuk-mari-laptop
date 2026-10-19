"""Launcher antarmuka PyQt lama (kompatibilitas/pengujian internal)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from ui.main_window import MainWindow


def main():
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    if hasattr(QApplication, "setHighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    app = QApplication(sys.argv)
    app.setApplicationName("PemetaanProfilUfukMariLegacy")
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.setWindowTitle("PEMETAAN PROFIL UFUK MAR'I — LEGACY PYQT")
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
