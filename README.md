# APLIKASI PEMETAAN PROFIL UFUK MAR'I BERBASIS COMPUTER VISION
**Instrumen Falak Digital untuk Analisis Kelayakan Tempat Rukyatul Hilal**  
*Laboratorium Astronomi & Ilmu Falak | Fakultas Syariah*

---

## 📌 1. Latar Belakang & Deskripsi

Dalam astronomi Islam (**Ilmu Falak**), penentuan awal bulan hijriah didasarkan pada visibilitas hilal (*imkanur rukyat* atau *rukyatul hilal bi al-fi'li*) sesaat setelah matahari terbenam (*ghurub*). Salah satu kendala terbesar di lapangan adalah bentang halangan daratan (*terrain obstructions*), seperti jajaran bukit, pegunungan, vegetasi/pepohonan, maupun bangunan buatan manusia pada ufuk mar'i (*apparent/visible horizon*).

Aplikasi desktop ini dirancang khusus untuk memetakan dan menganalisis kontur ufuk mar'i secara presisi dengan mengombinasikan:
1. **Perekaman Citra Kamera Lensa Eyepiece / Teleskop USB** secara asinkron (*non-blocking QThread*).
2. **Algoritma Computer Vision (OpenCV)** untuk mendeteksi garis batas perbatasan antara langit (*sky*) dan daratan (*ground/silhouette*).
3. **Model Matematika Proyeksi Optik Pinhole Falak** untuk mengonversi setiap koordinat piksel menjadi nilai sudut **Azimut (°)** dan **Elevasi (°)** secara akurat.
4. **Analisis Sudut Halangan Relatif** terhadap Ufuk Hakiki ($0^\circ$) dan Kerendahan Ufuk Laut ($-Dip$).
5. **Penerbitan Dokumen Berita Acara & Laporan Falak Resmi** dalam format PDF (ReportLab) dan CSV.

---

## 📐 2. Landasan Matematika & Formula Falak

### A. Kerendahan Ufuk (*Dip of Horizon*)
Ketika pengamat berada pada ketinggian $h$ meter di atas permukaan laut (dpl), ufuk mar'i laut berada di bawah ufuk hakiki ($0^\circ$) sebesar sudut kerendahan ufuk ($Dip$ atau $d$):
$$\text{Dip} = 1.76' \times \sqrt{h} \quad (\text{menit busur})$$
$$\text{Dip} = \frac{1.76}{60}^\circ \times \sqrt{h} \approx 0.029333^\circ \times \sqrt{h} \quad (\text{derajat})$$

### B. Proyeksi Optik Kamera (Piksel $\to$ Azimut & Elevasi)
Untuk citra berukuran lebar $W$ piksel dan tinggi $H$ piksel:
- Titik tengah sensor: $x_c = \frac{W - 1}{2}$, $y_c = \frac{H - 1}{2}$
- Sudut pandang kamera: $HFOV$ (Horizontal Field of View) dan $VFOV$ (Vertical Field of View)
- Arah bidikan tengah kamera: $Az_{\text{center}}$ (default $270^\circ$ / Barat) dan $Tilt_{\text{center}}$ (kemiringan optik)

Untuk setiap kolom piksel $x \in [0, W - 1]$ dan baris kontur ufuk $y_{\text{horizon}}(x)$:
$$\Delta Az = \arctan\left(\frac{x - x_c}{W / 2} \times \tan\left(\frac{HFOV}{2}\right)\right)$$
$$Az(x) = \left(Az_{\text{center}} + \Delta Az\right) \pmod{360^\circ}$$

$$\Delta Alt = \arctan\left(\frac{y_c - y_{\text{horizon}}(x)}{H / 2} \times \tan\left(\frac{VFOV}{2}\right)\right)$$
$$Alt(x) = Tilt_{\text{center}} + \Delta Alt$$

### C. Klasifikasi Sudut Halangan untuk Rukyatul Hilal
Ketinggian halangan ($Alt$) pada azimut sasaran diklasifikasikan berdasarkan kriteria visibilitas astronomis (misal Kriteria Baru MABIMS: Tinggi hilal minimal $3^\circ$, elongasi $6.4^\circ$):
- **$Alt \le -Dip$**: Bebas Halangan (Ufuk laut terbuka tanpa rintangan daratan).
- **$-Dip < Alt \le 0^\circ$**: Ufuk Rendah Terbuka (Di bawah ufuk hakiki, sangat ideal).
- **$0^\circ < Alt \le 1.2^\circ$**: Halangan Rendah (Bukit jauh / garis pantai rendah, hilal $> 1.5^\circ$ aman).
- **$1.2^\circ < Alt \le 3.0^\circ$**: Halangan Sedang (Rawan untuk hilal muda dengan tinggi $\le 3^\circ$).
- **$Alt > 3.0^\circ$**: Halangan Tinggi (Sangat berisiko menutupi hilal, lokasi tidak direkomendasikan).

---

## 📂 3. Struktur Direktori Proyek

```
pemetaan-ufuk-mari/
├── main.py                     # Titik masuk utama aplikasi (QApplication)
├── test_app.py                 # Skrip pengujian otomatis seluruh alur
├── requirements.txt            # Daftar pustaka dependensi Python
├── README.md                   # Dokumentasi ilmiah & teknis aplikasi
├── core/                       # Modul Logika Astronomi & Computer Vision
│   ├── falak_calc.py           # Perhitungan Falak (Dip, DMS, proyeksi sudut, klasifikasi)
│   ├── cv_engine.py            # Engine Computer Vision deteksi kontur ufuk (OpenCV)
│   ├── camera_worker.py        # Worker streaming kamera USB asinkron
│   ├── sample_generator.py     # Generator citra lanskap senja sintetis
│   └── report_generator.py     # Generator dokumen resmi PDF & ekspor CSV
├── ui/                         # Antarmuka Pengguna (UI)
│   ├── main_window.py          # Window utama & pengontrol stepper 4 layar
│   ├── styles.py               # Tema visual dark modern (QSS)
│   ├── screens/                # Alur 4 Layar (Mudah Dibaca & Diedit)
│   │   ├── screen_dashboard.py   # Layar 1: Dashboard Beranda & Tombol Mulai
│   │   ├── screen_observation.py # Layar 2: Kamera, HUD Azimuth 270°, Elevasi & GPS
│   │   ├── screen_result.py      # Layar 3: Hasil Kontur, Data Sensor & Kurva Matplotlib
│   │   └── screen_report.py      # Layar 4: Evaluasi Lapangan & Cetak Dokumen PDF Resmi
│   └── widgets/
│       ├── image_viewer.py     # Viewer citra dengan crosshair bidikan
│       └── plot_canvas.py      # Canvas grafik kurva profil ufuk (Matplotlib)
├── assets/                     # Ikon aplikasi & contoh citra lanskap
└── exports/                    # Berkas hasil keluaran (PDF, PNG, CSV)
```

---

## 🚀 4. Instalasi & Menjalankan Aplikasi

### Kebutuhan Sistem:
- Python 3.9 s.d. 3.14
- Sistem Operasi: Linux (Kali, Ubuntu, Debian), Windows 10/11, atau macOS.

### Instalasi Dependensi:
```bash
pip install -r requirements.txt
```

### Menjalankan Aplikasi:
```bash
python3 main.py
```

---

## 🖥️ 5. Alur Kerja Aplikasi (4 Tahap Streamlined)

1. **Tahap 1 - Beranda (Dashboard):**
   - Tampilan bersih dan elegan dengan tombol utama: `[MULAI PENGAMATAN]`.

2. **Tahap 2 - Pengamatan (Kamera & Sensor):**
   - Viewfinder kamera live / upload foto dengan overlay crosshair di tengah.
   - HUD Sensor otomatis: Indikator hijau saat mengarah tepat ke Barat (`270.0°`), sudut elevasi, dan koordinat GPS.
   - Tombol shutter frame atau pilih dari file/galeri dengan strip preview maksimal 3 foto.
   - Klik `[PROSES & LIHAT HASIL]` untuk ekstraksi kontur otomatis.

3. **Tahap 3 - Hasil & Profil Ufuk:**
   - Tampilan gabungan satu layar: Foto kontur ufuk + Data numerik + Kurva visual profil ufuk (Matplotlib).
   - Slider inspeksi azimut sasaran hilal untuk evaluasi sudut halangan.
   - Tombol `[Foto Ulang]` (jika ingin kembali ke kamera) atau `[Lanjut ke Cetak Laporan]`.

4. **Tahap 4 - Laporan PDF Resmi:**
   - Form catatan evaluasi terisi otomatis dengan rekomendasi falak.
   - Tombol `[CETAK LAPORAN RESMI (PDF)]` untuk menghasilkan dokumen berita acara siap cetak di folder `exports/`.

### Modul 1: Profil Ufuk (Pengambilan & Plotting)
1. **Live Streaming Kamera USB:** Pilih sumber kamera USB (misal `/dev/video0`) atau gunakan *Mode Simulasi Falak*. Klik **Mulai Kamera**.
2. **Form Parameter:**
   - Masukkan **Nama Lokasi** (misal *Pantai Parangtritis Pos Hilal*).
   - Masukkan **Lintang ($\phi$)** dan **Bujur ($\lambda$)** dalam format DMS (`-07° 58' 48" LS`) atau desimal (`-7.98`).
   - Masukkan **Ketinggian ($h$)** dalam meter $\to$ nilai Dip dihitung otomatis.
   - Atur **Azimut Bidikan Tengah Kamera** (default $270^\circ$) dan **HFOV/VFOV**.
3. **Ekstraksi Kontur Ufuk Mar'i:**
   - Klik tombol merah **📸 TANGKAP GAMBAR & EKSTRAKSI KONTUR UFUK MAR'I**.
   - Algoritma Computer Vision otomatis memproses batas langit-daratan, menghasilkan overlay cyan dan kurva grafik elevasi pada Matplotlib canvas.
4. **Ekspor Cepat:** Simpan grafik sebagai PNG, ekspor CSV, atau cetak ringkasan PDF.
5. Klik **➡️ ANALISIS UFUK SASARAN** untuk menuju ke Modul 2.

### Modul 2: Analisis Ufuk (Inspeksi Sudut Halangan)
1. **Pemilihan Azimut Sasaran:** Geser slider azimut atau ketikkan azimut benda langit (misal azimut hilal saat matahari terbenam). Anda juga bisa **mengklik langsung pada foto atau grafik** untuk memilih titik sasaran.
2. **Kalkulasi Real-Time:** Kartu status menampilkan:
   - Tinggi Halangan Ufuk Mar'i ($Alt$) dalam format desimal dan derajat-menit-detik (DMS).
   - Selisih terhadap Ufuk Hakiki ($0^\circ$) dan Ufuk Laut ($-Dip$).
   - Status pandangan (Bebas Halangan / Halangan Rendah / Terhalang Bukit / Terhalang Pohon).
3. **Catatan & Rekomendasi:** Isi catatan kondisi cuaca lapangan dan rekomendasi kelayakan. Rekomendasi awal terisi otomatis berdasarkan kriteria falak.
4. **Cetak Dokumen Resmi:** Klik **🖨️ CETAK DATA LAPORAN PEMETAAN UFUK (PDF RESMI)** untuk menghasilkan dokumen berita acara berstandar akademik.

---

## 📝 6. Catatan Pembaruan & Riwayat Perubahan Terkini

### A. `core/cv_engine.py` (Penyempurnaan Engine Computer Vision Kontur Ufuk)
1. **Deteksi Kolom Aktif Citra (Active Bounds Detection):**
   - Menambahkan deteksi kolom citra non-hitam untuk mengeliminasi dampak *letterbox* atau *pillarbox padding* pada citra hasil tangkapan layar/kamera ponsel.
2. **Optimasi Algoritma Dynamic Programming (DP) & Zenith-to-Nadir Prior:**
   - Mempertahankan jalur garis ufuk utama pada kontur daratan/vegetasi terjauh dan mencegah garis anjlok ke area jalan cor/lapangan di latar depan (*foreground*).
3. **Deteksi Struktur Ramping Vertikal Berbasis Validasi Kontras Horizontal:**
   - Memetakan struktur menara BTS utama, menara kisi SUTET di sisi kiri, dan menara tandon air secara presisi hingga pucuk teratas.
   - Menggunakan validasi kontras horizontal terhadap langit di samping kiri dan kanan struktur (`contrast >= 10.0`), memastikan lonjakan palsu (*false spikes*) akibat variasi gradasi awan mendung atau punggungan pegunungan tertolak 100%.
4. **Penyempurnaan Render Overlay Citra:**
   - Menambahkan resolusi otomatis indeks kolom horizontal `target_x` pada fungsi `render_overlay` untuk sinkronisasi retikel target dan anotasi derajat falak.

### B. `web_app.py` (Pembaruan Antarmuka Web Interaktif)
1. **Viewport Citra Interaktif dengan Zoom & Pan:**
   - Menambahkan kontrol perbesaran citra interaktif (tombol `🔍 +`, `🔍 -`, `↺ 100%`, roda mouse/scroll, serta gestur *pinch-to-zoom* 2 jari pada perangkat sentuh).
2. **Interaksi Langsung Penentuan Azimut (In-Image Azimuth Scrubbing):**
   - Memungkinkan pengamat menyentuh atau menggeser (*drag*) kursor azimut sasaran langsung pada kanvas citra foto dengan latensi instan (0 ms).
3. **Tampilan Kurva Profil Vektor Terpadu:**
   - Mengintegrasikan kembali kartu visualisasi *Kurva Profil Elevasi vs Azimuth* (Fast OpenCV Vector) berdampingan dengan inspeksi numerik parameter falak.
