# -*- mode: python ; coding: utf-8 -*-

import os
import sys

project_dir = r"D:\pemetaan-ufuk-mari-Laptop"

added_files = [
    (os.path.join(project_dir, "assets"), "assets"),
    (os.path.join(project_dir, "compass_calibration.json"), "."),
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
    "reportlab",
    "reportlab.lib",
    "reportlab.platypus",
    "pypdfium2",
    "openpyxl",
    "serial",
    "serial.tools.list_ports",
    "core",
    "core.paths",
    "core.camera_worker",
    "core.cv_engine",
    "core.falak_calc",
    "core.compass_service",
    "core.report_generator",
    "core.sample_generator",
    "web_app",
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
    excludes=["tkinter", "IPython", "jupyter"],
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
