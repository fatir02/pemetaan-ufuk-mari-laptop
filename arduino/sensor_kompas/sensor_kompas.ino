/*
  sensor_kompas.ino
  Firmware Sensor Kompas & Kemiringan untuk Arduino Uno / Nano / ESP32.
  Digunakan pada Aplikasi Pemetaan Profil Ufuk Mar'i.

  Sensor yang didukung:
  - Bosch Sensortec BNO055 (Absolute Orientation Sensor 9-DOF)
  
  Koneksi Pin Arduino Uno:
  - VCC  -> 5V atau 3.3V (sesuai modul BNO055)
  - GND  -> GND
  - SDA  -> Pin A4 pada Arduino Uno (atau pin SDA terdedikasi)
  - SCL  -> Pin A5 pada Arduino Uno (atau pin SCL terdedikasi)

  Koneksi Pin ESP32 (Alternatif):
  - SDA  -> GPIO 21
  - SCL  -> GPIO 22

  Baudrate Serial: 115200 bps
  Output format JSON:
  {"azimuth": 270.0, "tilt": 0.0, "cal_mag": 3, "cal_gyro": 3}
*/

#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>

// Inisialisasi BNO055 dengan alamat I2C default 0x28
Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28);

void setup() {
  Serial.begin(115200);
  delay(1000);

  Wire.begin(); // Arduino Uno: SDA=A4, SCL=A5

  if (!bno.begin()) {
    // Coba fallback ke alamat alternatif 0x29 (jika pin ADR dihubungkan ke VCC/HIGH)
    bno = Adafruit_BNO055(55, 0x29);
    if (!bno.begin()) {
      Serial.println("{\"status\":\"error\",\"pesan\":\"BNO055 tidak terdeteksi di 0x28 maupun 0x29\"}");
      while (1) {
        delay(500);
      }
    }
  }

  // Menggunakan kristal eksternal untuk stabilitas pembacaan
  bno.setExtCrystalUse(true);
}

void loop() {
  sensors_event_t event;
  bno.getEvent(&event);

  uint8_t sys, gyro, accel, mag;
  bno.getCalibration(&sys, &gyro, &accel, &mag);

  // Format data JSON single-line thread-safe untuk ingestion di web_app.py & desktop GUI
  Serial.print("{\"azimuth\":");
  Serial.print(event.orientation.x, 1);
  Serial.print(",\"tilt\":");
  Serial.print(event.orientation.y, 1);
  Serial.print(",\"cal_mag\":");
  Serial.print(mag);
  Serial.print(",\"cal_gyro\":");
  Serial.print(gyro);
  Serial.println("}");

  delay(100); // Sampling rate ~10 Hz
}
