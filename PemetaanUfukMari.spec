# -*- mode: python ; coding: utf-8 -*-

import os
import sys

project_dir = os.path.abspath(SPECPATH) if "SPECPATH" in locals() else os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else r"C:\pemetaan-ufuk-mari-laptop"

added_files = [
    (os.path.join(project_dir, "assets"), "assets"),
    (os.path.join(project_dir, "compass_calibration.json"), "."),
    # Template UI dipecah (HTML/CSS/JS) dan harus ikut ke dalam EXE.
    (os.path.join(project_dir, "web", "templates"), os.path.join("web", "templates")),
]

hidden_imports = [
    "flask",
    "jinja2",
    "werkzeug",
    "cv2",
    "numpy",
    "scipy",
    "scipy.signal",
    "matplotlib",
    "matplotlib.pyplot",
    "matplotlib.backends.backend_agg",
    "reportlab",
    "reportlab.lib",
    "reportlab.platypus",
    "pypdfium2",
    "openpyxl",
    "serial",
    "serial.tools.list_ports",
    "core",
    "core.paths",
    "core.cv_engine",
    "core.falak_calc",
    "core.compass_service",
    "core.report_generator",
    "core.sample_generator",
    "web_app",
    "webview",
    "webview.platforms.edgechromium",
]

a = Analysis(
    [os.path.join(project_dir, "app_desktop.py")],
    pathex=[project_dir],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # PyQt5 & Tkinter tidak dipakai: aplikasi web memakai pywebview/WebView2
    # dan dialog native (ctypes). Tkinter justru terbukti memicu crash
    # tcl86t.dll ketika dijalankan bersama thread Flask.
    excludes=[
        "IPython", "jupyter",
        "tkinter", "_tkinter",
        "PyQt5", "PyQt6", "PySide2", "PySide6",
        "core.camera_worker",
        "PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="PemetaanUfukMari",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_dir, "assets", "app_icon.ico"),
)
