"""
paths.py
Utilitas penanganan path direktori aplikasi dan aset resource.
Memastikan kompatibilitas penuh baik saat dijalankan dari source code Python
maupun saat dibungkus ke dalam aplikasi standalone (.exe) via PyInstaller.
"""

import os
import sys


def get_app_dir() -> str:
    """
    Mengembalikan direktori utama aplikasi (tempat file .exe atau root proyek berada).
    Folder ini digunakan untuk menyimpan data pengguna seperti exports/ dan kalibrasi.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_resource_path(relative_path: str) -> str:
    """
    Mengembalikan path absolut untuk file aset/resource (assets/icon.png, dsb).
    Bekerja mulus baik saat dijalankan langsung maupun saat di-bundle PyInstaller (onedir/onefile).
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidate_mei = os.path.join(meipass, relative_path)
            if os.path.exists(candidate_mei):
                return candidate_mei

    app_dir = get_app_dir()
    candidate = os.path.join(app_dir, relative_path)
    return candidate
