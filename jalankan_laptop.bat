@echo off
title Pemetaan Profil Ufuk Mar'i - Laptop Edition
chcp 65001 >nul
cls
echo ======================================================================
echo    APLIKASI PEMETAAN PROFIL UFUK MAR'I (LAPTOP & DESKTOP EDITION)
echo    Laboratorium Astronomi & Ilmu Falak | Fakultas Syariah
echo ======================================================================
echo.
echo  Pilih mode antarmuka:
echo  [1] Web App Laptop (Browser: http://127.0.0.1:5000) [Direkomendasikan]
echo  [2] Native GUI Desktop (PyQt5)
echo  [3] Uji Sistem Otomatis (test_app.py)
echo.
set /p pilihan="Pilihan Anda [1/2/3] (Tekan Enter untuk [1]): "
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

:end
pause
