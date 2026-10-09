@echo off
title Pemetaan Profil Ufuk Mar'i - Laptop Edition
cd /d "%~dp0"
chcp 65001 >nul
cls

echo ======================================================================
echo    APLIKASI PEMETAAN PROFIL UFUK MAR'I [LAPTOP DAN DESKTOP EDITION]
echo    Laboratorium Astronomi dan Ilmu Falak - Fakultas Syariah
echo ======================================================================
echo.

:: 1. Verifikasi ketersediaan Python di PATH
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python tidak terdeteksi di laptop ini!
    echo.
    echo Pastikan Python versi 3.10 atau lebih baru sudah diinstal dari:
    echo   https://www.python.org/downloads/
    echo.
    echo PENTING: Saat instalasi, pastikan mencentang kotak:
    echo   [v] Add python.exe to PATH
    echo ======================================================================
    echo.
    pause
    exit /b 1
)

:: 2. Verifikasi dan pasang dependensi otomatis jika belum lengkap
python -c "import flask, cv2, PyQt5, openpyxl, pypdfium2, reportlab, matplotlib, scipy, numpy" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Terdeteksi pustaka yang dibutuhkan belum lengkap terpasang.
    echo Sedang menginstal dependensi dari requirements.txt secara otomatis...
    echo.
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Gagal memasang pustaka secara otomatis.
        echo Pastikan laptop terhubung ke internet dan coba jalankan:
        echo   pip install -r requirements.txt
        echo ======================================================================
        echo.
        pause
        exit /b 1
    )
    echo.
    echo [SUKSES] Semua pustaka berhasil dipasang!
    echo.
)

echo  Pilih mode antarmuka:
echo  [1] Web App Laptop (Browser: http://127.0.0.1:5000) [Direkomendasikan]
echo  [2] Native GUI Desktop (PyQt5)
echo  [3] Uji Sistem Otomatis (test_app.py)
echo  [4] Pasang / Perbarui Dependensi (pip install -r requirements.txt)
echo.

set "pilihan="
set /p pilihan="Pilihan Anda [1/2/3/4] (Tekan Enter untuk [1]): "
if "%pilihan%"=="" set pilihan=1

if "%pilihan%"=="1" (
    echo.
    echo Menjalankan Web App Laptop...
    echo Buka browser di http://127.0.0.1:5000
    start http://127.0.0.1:5000
    python web_app.py
    goto end
)

if "%pilihan%"=="2" (
    echo.
    echo Membuka Desktop GUI PyQt5...
    python main.py
    goto end
)

if "%pilihan%"=="3" (
    echo.
    echo Menjalankan Pengujian Otomatis...
    python test_app.py
    goto end
)

if "%pilihan%"=="4" (
    echo.
    echo Memperbarui dependensi dari requirements.txt...
    python -m pip install -r requirements.txt
    goto end
)

:end
echo.
pause
