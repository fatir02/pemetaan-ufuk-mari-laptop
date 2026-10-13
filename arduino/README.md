# Firmware Sensor Kompas & Kemiringan (Arduino Uno)

Folder ini berisi sketch Arduino untuk menghubungkan sensor orientasi absolut (Bosch BNO055) ke laptop via USB Serial pada aplikasi **Pemetaan Profil Ufuk Mar'i**.

## Skema Sambungan Kabel (Arduino Uno)

| Pin Sensor BNO055 | Pin Arduino Uno | Keterangan |
| :--- | :--- | :--- |
| **VIN / VCC** | **5V** atau **3.3V** | Sesuai spesifikasi modul BNO055 |
| **GND** | **GND** | Ground bersama |
| **SDA** | **A4** (atau pin SDA) | Jalur Data I2C |
| **SCL** | **A5** (atau pin SCL) | Jalur Clock I2C |
| **ADR / AD0** | *Biarkan kosong* (atau GND) | Alamat I2C `0x28` (default) |

## Dependensi Library Arduino

Pasang pustaka berikut melalui **Library Manager** di Arduino IDE:
1. `Adafruit BNO055` (oleh Adafruit)
2. `Adafruit Unified Sensor` (oleh Adafruit)
3. `Wire` (Bawaan Arduino)

## Cara Mengunggah (Upload) ke Arduino Uno

1. Buka berkas `sensor_kompas/sensor_kompas.ino` di Arduino IDE.
2. Pilih Board: **Tools -> Board -> Arduino AVR Boards -> Arduino Uno**.
3. Pilih Port COM: **Tools -> Port -> COMx** (misal COM7).
4. Klik tombol **Upload** (tanda panah ke kanan).
5. Setelah selesai upload, **tutup Serial Monitor Arduino IDE** agar port COM dapat diakses secara otomatis oleh aplikasi laptop (`web_app.py` atau `main.py`).

## Format Data Serial

Sensor mengirim telemetry berupa JSON satu baris per 100 ms (115200 baud):
```json
{"azimuth": 270.4, "tilt": 0.2, "cal_mag": 3, "cal_gyro": 3}
```
- `azimuth`: Arah mata angin dalam derajat (0.0° - 360.0°).
- `tilt`: Kemiringan kamera/teropong (0.0° = datar/lurus).
- `cal_mag` & `cal_gyro`: Status kalibrasi internal BNO055 (skala 0 s/d 3).
