"""
web_app.py
Aplikasi Web Mobile & Desktop Pemetaan Profil Ufuk Mar'i Berbasis Computer Vision.
Versi Ultra-Cepat (High Performance Engine):
- Zero-latency client-side inspection slider (respons 0 ms)
- Pure OpenCV vector chart rendering (50 ms vs 2400 ms Matplotlib)
- Client-side auto-compress (upload <200 KB)
- Optimized PDF page cache & preview
- Form Evaluasi & Berita Acara Falak lengkap
"""

import os
import sys
import io
import time
import base64
import numpy as np
import cv2
import pypdfium2

from flask import Flask, request, jsonify, send_file, render_template_string

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.cv_engine import HorizonDetector
from core.falak_calc import calculate_dip, classify_obstacle, format_dms
from core.report_generator import export_pdf_report, export_csv_data
from core.sample_generator import generate_synthetic_horizon

app = Flask(__name__)
detector = HorizonDetector()

# Cache analisis terakhir
LAST_ANALYSIS = {}
PDF_CACHE = {"path": None, "hash": None, "pages": []}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Pemetaan Ufuk Mar'i - Laptop Edition</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background-color: #0b0f17; color: #e2e8f0; padding-bottom: 60px; -webkit-font-smoothing: antialiased; }
    
    /* Header Bar Responsif */
    .header {
      background: linear-gradient(135deg, #0f172a, #1e293b);
      padding: 16px 20px;
      border-bottom: 1px solid #334155;
      display: flex;
      flex-direction: column;
      gap: 12px;
      text-align: center;
    }
    .header-brand {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
    }
    .header-brand h1 {
      font-size: 1.25rem;
      color: #38bdf8;
      font-weight: 800;
      letter-spacing: 0.5px;
    }
    .header-brand p {
      font-size: 0.78rem;
      color: #94a3b8;
      margin-top: 2px;
    }
    .header-meta {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .clock-badge {
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 4px 10px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.78rem;
    }
    .clock-label { color: #64748b; font-weight: 600; font-size: 0.7rem; }
    .clock-val { color: #38bdf8; font-family: monospace; font-weight: bold; }
    .badge-laptop {
      background: rgba(56, 189, 248, 0.15);
      color: #38bdf8;
      border: 1px solid #0284c7;
      padding: 4px 10px;
      border-radius: 8px;
      font-size: 0.75rem;
      font-weight: 700;
    }

    /* Container & Grid Tata Letak Laptop */
    .container {
      max-width: 720px;
      margin: 0 auto;
      padding: 14px;
    }
    .dashboard-grid {
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .dash-col-left { display: flex; flex-direction: column; gap: 14px; }
    .dash-col-right { display: flex; flex-direction: column; gap: 14px; }

    .card { background-color: #131b2a; border: 1px solid #233147; border-radius: 14px; padding: 16px; margin-bottom: 0; }
    .card-title { font-size: 0.94rem; font-weight: 700; color: #38bdf8; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; }
    .form-group { margin-bottom: 12px; }
    label { display: block; font-size: 0.78rem; color: #94a3b8; margin-bottom: 5px; font-weight: 600; }
    input[type="number"], input[type="text"], select, textarea {
      width: 100%; background-color: #1a2436; border: 1px solid #334155; border-radius: 8px; color: #ffffff;
      padding: 10px 12px; font-size: 0.88rem; outline: none; font-family: inherit;
    }
    textarea { resize: vertical; line-height: 1.45; }
    input:focus, textarea:focus { border-color: #38bdf8; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
    .grid-4 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }
    .btn {
      display: inline-block; width: 100%; border: none; border-radius: 10px; padding: 12px 16px; font-size: 0.9rem;
      font-weight: 700; cursor: pointer; text-align: center; text-decoration: none; transition: 0.15s;
    }
    .btn-primary { background: linear-gradient(135deg, #0284c7, #0369a1); color: #ffffff; }
    .btn-primary:hover { background: linear-gradient(135deg, #0369a1, #0284c7); }
    .btn-success { background: linear-gradient(135deg, #10b981, #059669); color: #ffffff; }
    .btn-success:hover { background: linear-gradient(135deg, #059669, #10b981); }
    .btn-secondary { background-color: #1e293b; color: #94a3b8; border: 1px solid #334155; }
    .btn-secondary:hover { background-color: #334155; color: #ffffff; }
    .btn-sm { padding: 8px 10px; font-size: 0.8rem; border-radius: 8px; width: 100%; }
    .photo-area {
      border: 2px dashed #334155; border-radius: 12px; padding: 18px 14px; text-align: center;
      background-color: #0f172a; margin-bottom: 12px;
    }
    .preview-img { width: 100%; border-radius: 8px; display: none; margin-top: 10px; border: 1px solid #334155; }
    .badge {
      display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: bold;
    }
    .badge-success { background-color: #064e3b; color: #34d399; border: 1px solid #059669; }
    .badge-info { background-color: #0c4a6e; color: #38bdf8; border: 1px solid #0284c7; }
    .badge-accent { background-color: #1e1b4b; color: #a5b4fc; border: 1px solid #4338ca; }

    /* Dual visual layout */
    .dual-visual-wrapper {
      display: flex;
      flex-direction: column;
      gap: 14px;
      margin-bottom: 14px;
    }
    .visual-card { padding: 14px; }
    .img-wrapper {
      position: relative;
      background: #000;
      border-radius: 8px;
      overflow: hidden;
      border: 1px solid #334155;
    }
    .result-img {
      width: 100%;
      height: auto;
      display: block;
      object-fit: contain;
      max-height: 380px;
    }

    /* Stats Cards */
    .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .stat-card { background-color: #1a2436; border: 1px solid #28374d; border-radius: 10px; padding: 10px 12px; text-align: center; }
    .stat-val { font-size: 1.15rem; font-weight: 800; color: #38bdf8; margin-top: 4px; }
    .stat-lbl { font-size: 0.72rem; color: #94a3b8; }
    .stat-sub { font-size: 0.68rem; color: #64748b; margin-top: 2px; }

    /* Placeholder Workspace */
    .placeholder-card {
      border: 2px dashed #233147;
      background: radial-gradient(circle at 50% 30%, #151e30, #0c121e);
      padding: 36px 20px;
      text-align: center;
    }
    .placeholder-features {
      display: flex;
      flex-direction: column;
      gap: 10px;
      max-width: 500px;
      margin: 16px auto;
      text-align: left;
    }
    .pf-item {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      background: rgba(15, 23, 42, 0.6);
      padding: 10px 14px;
      border-radius: 8px;
      border: 1px solid #1e293b;
    }
    .pf-icon { font-size: 1.2rem; }
    .pf-item b { font-size: 0.84rem; color: #38bdf8; display: block; margin-bottom: 2px; }
    .pf-item p { font-size: 0.74rem; color: #94a3b8; margin: 0; }

    #loading { display: none; text-align: center; padding: 20px 0; color: #38bdf8; font-weight: 700; }
    .spinner {
      border: 4px solid rgba(56, 189, 248, 0.2); border-top: 4px solid #38bdf8; border-radius: 50%;
      width: 32px; height: 32px; animation: spin 0.8s linear infinite; margin: 0 auto 10px;
    }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    .slider-container { margin: 15px 0; }
    input[type=range] { width: 100%; accent-color: #38bdf8; }

    /* Gaya Viewfinder Kamera Live */
    #liveCamWrapper {
      display: none;
      position: relative;
      width: 100%;
      border-radius: 12px;
      overflow: hidden;
      background-color: #000000;
      border: 2px solid #38bdf8;
      margin-bottom: 14px;
    }
    #cameraVideo {
      width: 100%;
      height: auto;
      display: block;
      object-fit: cover;
      max-height: 440px;
    }
    #cameraOverlay {
      position: absolute;
      top: 0; left: 0;
      width: 100%; height: 100%;
      pointer-events: none;
    }
    .cam-controls {
      position: absolute;
      bottom: 12px;
      left: 0; right: 0;
      display: flex;
      justify-content: center;
      gap: 12px;
      padding: 0 16px;
      z-index: 10;
    }
    .btn-shutter {
      background: radial-gradient(circle, #ef4444 40%, #dc2626 100%);
      color: #ffffff;
      font-weight: 900;
      font-size: 0.92rem;
      border: 3px solid #ffffff;
      border-radius: 30px;
      padding: 10px 22px;
      box-shadow: 0 4px 12px rgba(239, 68, 68, 0.5);
      cursor: pointer;
    }
    .btn-close-cam {
      background: rgba(15, 23, 42, 0.85);
      color: #94a3b8;
      border: 1px solid #475569;
      border-radius: 20px;
      padding: 8px 14px;
      font-size: 0.8rem;
      cursor: pointer;
    }

    /* Modal / Viewer Dokumen PDF Laporan Ringan */
    #reportPreviewModal {
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background-color: rgba(5, 8, 14, 0.96);
      z-index: 9999;
      flex-direction: column;
    }
    .preview-doc-header {
      background: linear-gradient(135deg, #0f172a, #1e293b);
      border-bottom: 1px solid #334155;
      padding: 10px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      flex-wrap: wrap;
    }
    .preview-doc-header h2 {
      font-size: 0.92rem;
      color: #38bdf8;
      font-weight: 800;
      letter-spacing: 0.5px;
    }
    .doc-toolbar {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }
    .doc-btn {
      background-color: #1e293b;
      color: #e2e8f0;
      border: 1px solid #334155;
      border-radius: 6px;
      padding: 6px 10px;
      font-size: 0.82rem;
      font-weight: bold;
      cursor: pointer;
    }
    .doc-btn:hover { background-color: #334155; color: #38bdf8; }
    .doc-viewport {
      flex: 1;
      overflow: auto;
      padding: 16px 10px;
      text-align: center;
      background-color: #070a10;
      touch-action: pan-x pan-y pinch-zoom;
      -webkit-overflow-scrolling: touch;
    }
    .doc-container {
      display: inline-block;
      transition: transform 0.1s ease-out;
      transform-origin: top center;
    }
    .doc-page {
      background-color: #ffffff;
      border-radius: 4px;
      box-shadow: 0 6px 24px rgba(0, 0, 0, 0.7);
      margin: 0 auto 20px auto;
      max-width: 100%;
      overflow: hidden;
    }
    .doc-page img {
      width: 100%;
      height: auto;
      display: block;
    }
    .doc-page-footer {
      background: #0f172a;
      color: #64748b;
      font-size: 0.75rem;
      padding: 6px;
      border-top: 1px solid #1e293b;
    }

    /* Media Query Khusus Layar Laptop & Desktop (Lebar >= 992px) */
    @media (min-width: 992px) {
      .container {
        max-width: 1440px;
        padding: 20px 24px;
      }
      .header {
        flex-direction: row;
        justify-content: space-between;
        align-items: center;
        padding: 16px 32px;
        text-align: left;
      }
      .header-brand {
        justify-content: flex-start;
      }
      .header-meta {
        justify-content: flex-end;
      }
      .dashboard-grid {
        display: grid;
        grid-template-columns: 420px 1fr;
        gap: 20px;
        align-items: start;
      }
      .dual-visual-wrapper {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
      }
      .stats-grid {
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;
      }
      .grid-4 {
        grid-template-columns: 1fr 1fr;
      }
      .result-img {
        max-height: 340px;
      }
    }
  </style>
</head>
<body>

  <div class="header">
    <div class="header-brand">
      <div style="font-size: 1.8rem;">🔭</div>
      <div>
        <h1>PEMETAAN PROFIL UFUK MAR'I</h1>
        <p>Instrumen Falak Digital & Deteksi Halangan Rukyat (Edisi Laptop & Desktop)</p>
      </div>
    </div>
    <div class="header-meta">
      <div class="clock-badge">
        <span class="clock-label">WIB (UTC+7)</span>
        <span class="clock-val" id="clockWib">--:--:--</span>
      </div>
      <div class="clock-badge">
        <span class="clock-label">UTC</span>
        <span class="clock-val" id="clockUtc">--:--:--</span>
      </div>
      <span class="badge badge-laptop">🖥️ Mode Laptop</span>
    </div>
  </div>

  <div class="container">
    <div class="dashboard-grid">

      <!-- PANEL KIRI: INPUT CITRA & SENSOR -->
      <div class="dash-col-left">
        <!-- KARTU 1: PENGAMBILAN CITRA & KAMERA -->
        <div class="card">
          <div class="card-title">
            <span>📸 1. Muat Citra Ufuk Mar'i</span>
            <span class="badge badge-info" id="statusBadgeInput">Siap</span>
          </div>

          <div class="grid-2">
            <button type="button" class="btn btn-secondary btn-sm" onclick="document.getElementById('galleryInput').click()">
              📁 Buka File / Foto Ufuk
            </button>
            <button type="button" class="btn btn-primary btn-sm" onclick="startLiveCamera()">
              📹 Kamera / Webcam Laptop
            </button>
          </div>

          <input type="file" id="galleryInput" accept="image/*" style="display: none;" onchange="onFileSelected(this)">

          <div id="liveCamWrapper">
            <!-- Pilihan Sumber Perangkat Kamera -->
            <div style="background: rgba(15, 23, 42, 0.95); padding: 8px 12px; display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; border-bottom: 1px solid #334155;">
              <div style="display: flex; align-items: center; gap: 6px;">
                <span style="font-size: 0.78rem; color: #38bdf8; font-weight: bold;">📹 Sumber:</span>
                <select id="cameraSourceSelect" onchange="onCameraDeviceSelected(this.value)" style="width: auto; max-width: 200px; padding: 4px 8px; font-size: 0.75rem; background: #1a2436; border: 1px solid #334155; border-radius: 6px; color: #ffffff;">
                  <option value="">Deteksi Kamera...</option>
                </select>
              </div>
              <button type="button" onclick="toggleHpCameraGuide()" style="background: none; border: none; color: #38bdf8; font-size: 0.74rem; cursor: pointer; text-decoration: underline;">
                📲 Cara Hubungkan Kamera HP
              </button>
            </div>

            <!-- Petunjuk Cepat Hubungkan HP -->
            <div id="hpCamGuide" style="display: none; background: #0f172a; padding: 10px 14px; border-bottom: 1px solid #233147; font-size: 0.75rem; color: #cbd5e1; line-height: 1.5;">
              <b style="color: #38bdf8; display: block; margin-bottom: 4px;">📲 Hubungkan Kamera HP ke Laptop (Webcam Sementara):</b>
              <p>1. Unduh aplikasi <b>Iriun Webcam</b> atau <b>DroidCam</b> di HP & Laptop Anda.</p>
              <p>2. Sambungkan HP ke Laptop via Wi-Fi yang sama atau kabel USB.</p>
              <p>3. Kamera HP otomatis terdeteksi pada pilihan <b>Sumber</b> di atas!</p>
              <p style="color: #64748b; margin-top: 4px;"><i>Nanti saat sudah memiliki alat teleskop / USB eyepiece camera khusus, cukup colok kabel USB ke laptop dan pilih dari dropdown yang sama.</i></p>
            </div>

            <video id="cameraVideo" playsinline autoplay muted></video>
            <canvas id="cameraOverlay"></canvas>
            <div class="cam-controls">
              <button type="button" class="btn-shutter" onclick="captureLiveFrame()">
                📸 AMBIL FRAME
              </button>
              <button type="button" class="btn-close-cam" onclick="stopLiveCamera()">
                ✖️ Tutup Kamera
              </button>
            </div>
          </div>

          <div class="photo-area" id="dropArea">
            <p style="font-size: 1.8rem; margin-bottom: 4px;">🏞️</p>
            <p style="font-weight: 700; color: #38bdf8; font-size: 0.88rem;" id="lblPhotoStatus">Belum ada foto yang dipilih</p>
            <p style="font-size: 0.74rem; color: #64748b; margin-top: 3px;">Klik 'Buka File / Foto Ufuk' atau gunakan Kamera / Webcam Laptop</p>
          </div>

          <img id="rawPreview" class="preview-img" alt="Preview Foto Aktif">
        </div>

        <!-- KARTU 2: PARAMETER BIDIKAN & SENSOR -->
        <div class="card">
          <div class="card-title">
            <span>🧭 2. Parameter Sensor & Bidikan</span>
            <button type="button" class="btn btn-secondary btn-sm" style="width: auto;" onclick="getGPS()">📍 Ambil GPS</button>
          </div>

          <div class="grid-2">
            <div class="form-group">
              <label>Azimuth Bidikan (0 - 360°):</label>
              <div style="display: flex; gap: 6px;">
                <input type="number" id="inpAzimuth" value="270.0" step="0.1">
                <button type="button" class="btn btn-secondary btn-sm" style="width: auto; white-space: nowrap;" onclick="document.getElementById('inpAzimuth').value='270.0'">270° Barat</button>
              </div>
            </div>
            <div class="form-group">
              <label>Kemiringan / Tilt (°):</label>
              <input type="number" id="inpTilt" value="0.0" step="0.1">
            </div>
          </div>

          <div class="grid-3">
            <div class="form-group">
              <label>Lintang / Lat (°):</label>
              <input type="number" id="inpLat" value="-7.9800" step="0.0001" placeholder="-7.9800">
              <span style="font-size: 0.68rem; color: #64748b;">LS: minus (-), LU: plus (+)</span>
            </div>
            <div class="form-group">
              <label>Bujur / Lon (°):</label>
              <input type="number" id="inpLon" value="110.3061" step="0.0001" placeholder="110.3061">
              <span style="font-size: 0.68rem; color: #64748b;">BT: plus (+), BB: minus (-)</span>
            </div>
            <div class="form-group">
              <label>Tinggi (mdpl):</label>
              <input type="number" id="inpAlt" value="45.0" step="1" placeholder="45">
              <span style="font-size: 0.68rem; color: #64748b;">Meter dpl (Ketinggian alat)</span>
            </div>
          </div>

          <button type="button" id="btnProcess" class="btn btn-primary" onclick="processImage()" style="margin-top: 6px;">
            🚀 PROSES EKSTRAKSI KONTUR UFUK
          </button>
        </div>

        <div id="loading">
          <div class="spinner"></div>
          <p id="loadingText">Sedang mengekstrak profil ufuk mar'i dengan Computer Vision...</p>
        </div>
      </div>

      <!-- PANEL KANAN: HASIL ANALISIS & WORKSPACE LAPTOP -->
      <div class="dash-col-right">

        <!-- WORKSPACE PLACEHOLDER SAAT BELUM PROSES -->
        <div id="rightPlaceholder" class="card placeholder-card">
          <div style="font-size: 2.8rem; margin-bottom: 12px;">🔭 ⛰️ 📈</div>
          <h3 style="color: #38bdf8; font-size: 1.15rem; margin-bottom: 8px;">Workspace Pemetaan Profil Ufuk Mar'i</h3>
          <p style="color: #94a3b8; font-size: 0.85rem; max-width: 540px; margin: 0 auto 16px auto; line-height: 1.5;">
            Silakan muat berkas citra ufuk atau aktifkan kamera/webcam laptop di panel kiri, tentukan koordinat lokasi, lalu klik <b>PROSES EKSTRAKSI KONTUR UFUK</b>.
          </p>
          <div class="placeholder-features">
            <div class="pf-item">
              <span class="pf-icon">⚡</span>
              <div><b>Segmentasi Kontur Otomatis</b><p>Deteksi perbatasan langit-daratan berbasis Computer Vision OpenCV</p></div>
            </div>
            <div class="pf-item">
              <span class="pf-icon">📐</span>
              <div><b>Kurva Elevasi vs Azimut Sinkron</b><p>Pemetaan Ufuk Mar'i, Ufuk Hakiki (0.00°), Dip Laut, dan Kriteria MABIMS (+3.00°)</p></div>
            </div>
            <div class="pf-item">
              <span class="pf-icon">📑</span>
              <div><b>Penerbitan Dokumen Resmi</b><p>Evaluasi kelayakan tempat rukyatul hilal & pencetakan Berita Acara format PDF</p></div>
            </div>
          </div>
          <button type="button" class="btn btn-primary" style="max-width: 260px; margin: 20px auto 0 auto;" onclick="document.getElementById('galleryInput').click()">
            📁 Pilih Berkas Citra Ufuk
          </button>
        </div>

        <!-- HASIL OLAH & KURVA PROFIL -->
        <div id="resultSection" style="display: none;">
          
          <!-- DUAL VISUAL SECTION (SIDE-BY-SIDE ON LAPTOP) -->
          <div class="dual-visual-wrapper">
            <div class="card visual-card">
              <div class="card-title">
                <span>⛰️ 3. Citra Hasil Kontur Ufuk Mar'i</span>
                <span id="resBadge" class="badge badge-success">Analisis Selesai</span>
              </div>
              <div class="img-wrapper">
                <img id="resOverlayImg" class="result-img" alt="Hasil Kontur">
              </div>
            </div>

            <div class="card visual-card">
              <div class="card-title">
                <span>📈 4. Kurva Profil Elevasi vs Azimuth</span>
                <span class="badge badge-accent">Fast OpenCV Vector</span>
              </div>
              <div class="img-wrapper">
                <img id="resPlotImg" class="result-img" alt="Grafik Profil">
              </div>
            </div>
          </div>

          <!-- KARTU INSPEKSI AZIMUT & STATISTIK FALAK -->
          <div class="card" style="margin-bottom: 14px;">
            <div class="card-title">
              <span>🎯 Inspeksi Azimut Sasaran Hilal</span>
              <span style="font-size: 0.8rem; color: #94a3b8;">Scrubbing instan 0 ms</span>
            </div>

            <div class="slider-container">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <label style="margin: 0; font-size: 0.82rem;">Titik Azimut Sasaran:</label>
                <b id="lblSliderAz" style="color: #38bdf8; font-size: 1.05rem; background: #0f172a; padding: 2px 10px; border-radius: 6px; border: 1px solid #334155;">270.00°</b>
              </div>
              <input type="range" id="sliderAz" min="262.5" max="277.5" step="0.05" value="270.0" oninput="onSliderTargetChanged(this.value)">
              <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: #64748b; margin-top: 4px;">
                <span id="lblMinAz">262.5°</span>
                <span>Tengah (Barat)</span>
                <span id="lblMaxAz">277.5°</span>
              </div>
            </div>

            <div class="stats-grid">
              <div class="stat-card">
                <div class="stat-lbl">Tinggi Halangan Mar'i</div>
                <div class="stat-val" id="resTargetAlt">+0.14°</div>
                <div class="stat-sub" id="resTargetAltDms">00° 08' 24"</div>
              </div>
              <div class="stat-card">
                <div class="stat-lbl">Ufuk Laut (Dip)</div>
                <div class="stat-val" id="resDip">-0.20°</div>
                <div class="stat-sub" id="resDipDms">-00° 11' 50"</div>
              </div>
              <div class="stat-card">
                <div class="stat-lbl">Selisih Hakiki (Δ0°)</div>
                <div class="stat-val" id="resDeltaHakiki">+0.14°</div>
                <div class="stat-sub">Relatif Ufuk 0.00°</div>
              </div>
              <div class="stat-card">
                <div class="stat-lbl">Status Rukyatul Hilal</div>
                <div class="stat-val" id="resStatusTxt" style="font-size: 0.92rem; color: #34d399;">Cukup Layak</div>
                <div class="stat-sub" id="resCategoryTxt">Ufuk Terbuka</div>
              </div>
            </div>

            <div style="background-color: #0f172a; padding: 12px 14px; border-radius: 8px; margin-top: 12px; font-size: 0.82rem; line-height: 1.5; color: #cbd5e1; border-left: 3px solid #38bdf8;">
              <p id="resDescText">Memuat deskripsi kelayakan...</p>
            </div>
          </div>

          <!-- KARTU 4: FORM EVALUASI LAPANGAN & PENERBITAN LAPORAN PDF -->
          <div class="card" id="evalCard" style="border: 1px solid #0284c7;">
            <div class="card-title" style="border-bottom: 1px solid #233147; padding-bottom: 8px;">
              <span>📋 EVALUASI LAPANGAN & PENERBITAN DOKUMEN RESMI</span>
            </div>

            <div class="grid-2">
              <div class="form-group">
                <label>Nama Lokasi / Pos Observasi Falak:</label>
                <input type="text" id="editLocation" value="Pos Observasi Falak (Laptop)">
              </div>
              <div class="form-group">
                <label>Petugas Pengamat / Tim Falak:</label>
                <input type="text" id="editObserver" value="Tim Falak & Astronomi">
              </div>
            </div>

            <div class="form-group">
              <label>Deskripsi Hasil Analisis Ufuk:</label>
              <textarea id="textDesc" rows="3" placeholder="Deskripsi otomatis terisi saat proses analisa selesai..."></textarea>
            </div>

            <div class="form-group">
              <label>Rekomendasi Kelayakan Tempat Rukyatul Hilal:</label>
              <textarea id="textRec" rows="3" placeholder="Rekomendasi kelayakan tempat terisi otomatis..."></textarea>
            </div>

            <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 10px; padding: 14px; margin-top: 14px;">
              <p style="color: #38bdf8; font-size: 0.78rem; font-weight: bold; margin-bottom: 10px; letter-spacing: 0.5px;">
                AKSI PENERBITAN BERKAS & DOKUMEN
              </p>

              <button type="button" class="btn btn-success" onclick="openReportPreview()" style="margin-bottom: 10px; padding: 14px; font-size: 0.95rem;">
                🖨️ CETAK / PREVIEW LAPORAN RESMI (PDF BERITA ACARA)
              </button>

              <div class="grid-2">
                <button type="button" class="btn btn-secondary btn-sm" onclick="openDataTableModal()">
                  📊 Buka Tabel & Ekspor Data (CSV)
                </button>
                <button type="button" class="btn btn-primary btn-sm" onclick="resetObservation()">
                  🚀 Mulai Pengamatan Baru
                </button>
              </div>
            </div>

          </div>

        </div>

      </div>

    </div>

  </div>

  <!-- VIEWER TABEL DATA NUMERIK INTERAKTIF -->
  <div id="dataTableModal" style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(5, 8, 14, 0.96); z-index: 9999; flex-direction: column;">
    <div class="preview-doc-header">
      <div style="display: flex; align-items: center; gap: 8px;">
        <button type="button" class="doc-btn" onclick="closeDataTableModal()">⬅️ Kembali</button>
        <h2>📊 TABEL DATA NUMERIK PROFIL UFUK MAR'I</h2>
      </div>

      <div class="doc-toolbar">
        <label style="font-size: 0.76rem; color: #94a3b8; margin: 0 4px 0 0;">Kerapatan:</label>
        <select id="selTableInterval" onchange="renderDataTable(this.value)" style="background: #1e293b; color: #38bdf8; border: 1px solid #334155; border-radius: 6px; padding: 6px 8px; font-size: 0.8rem; font-weight: bold; outline: none;">
          <option value="0.5">Interval 0.50° (Rekomendasi Falak)</option>
          <option value="0.25">Interval 0.25° (Detail)</option>
          <option value="0.1">Interval 0.10° (Rapat)</option>
          <option value="all">Semua Titik Sampel</option>
        </select>
        <button type="button" class="doc-btn" style="background: #059669; color: #fff;" onclick="downloadCsv()">📥 Unduh File CSV</button>
        <button type="button" class="doc-btn" onclick="copyTableToClipboard()">📋 Salin Teks</button>
      </div>
    </div>

    <!-- Ringkasan Statistik Tabel -->
    <div style="background: #111726; padding: 8px 16px; border-bottom: 1px solid #1e293b; display: flex; gap: 16px; flex-wrap: wrap; font-size: 0.78rem;">
      <span style="color: #94a3b8;">Total Baris: <b id="tblSampleCount" style="color: #38bdf8;">--</b></span>
      <span style="color: #94a3b8;">Rentang Azimut: <b id="tblAzRange" style="color: #38bdf8;">--</b></span>
      <span style="color: #94a3b8;">Ufuk Laut (Dip): <b id="tblDipVal" style="color: #38bdf8;">--</b></span>
      <span style="color: #94a3b8;">Elevasi Min/Max: <b id="tblElevRange" style="color: #38bdf8;">--</b></span>
    </div>

    <!-- Area Tabel Scrollable -->
    <div style="flex: 1; overflow: auto; padding: 14px 16px; background-color: #070a10;">
      <div style="max-width: 1300px; margin: 0 auto; background: #131b2a; border: 1px solid #233147; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.5);">
        <table id="numericTable" style="width: 100%; border-collapse: collapse; text-align: left; font-size: 0.82rem;">
          <thead>
            <tr style="background: #0f172a; color: #38bdf8; border-bottom: 2px solid #233147; position: sticky; top: 0; z-index: 2;">
              <th style="padding: 10px 12px; font-weight: bold; border-right: 1px solid #1e293b;">No</th>
              <th style="padding: 10px 12px; font-weight: bold; border-right: 1px solid #1e293b;">Azimut (°)</th>
              <th style="padding: 10px 12px; font-weight: bold; border-right: 1px solid #1e293b;">Elevasi Mar'i (°)</th>
              <th style="padding: 10px 12px; font-weight: bold; border-right: 1px solid #1e293b;">Format DMS Falak</th>
              <th style="padding: 10px 12px; font-weight: bold; border-right: 1px solid #1e293b;">Selisih Hakiki (Δ0.00°)</th>
              <th style="padding: 10px 12px; font-weight: bold; border-right: 1px solid #1e293b;">Selisih Dip (ΔLaut)</th>
              <th style="padding: 10px 12px; font-weight: bold;">Status Rukyatul Hilal</th>
            </tr>
          </thead>
          <tbody id="numericTableBody">
            <!-- Diisi lewat JS -->
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- VIEWER DOKUMEN LAPORAN PDF INTERAKTIF -->
  <div id="reportPreviewModal">
    <div class="preview-doc-header">
      <div style="display: flex; align-items: center; gap: 8px;">
        <button type="button" class="doc-btn" onclick="closeReportPreview()">⬅️ Tutup</button>
        <h2>📑 PREVIEW DOKUMEN LAPORAN RESMI</h2>
      </div>

      <div class="doc-toolbar">
        <button type="button" class="doc-btn" onclick="stepZoom(-0.2)">➖</button>
        <span id="lblZoomLevel" style="color: #38bdf8; font-weight: bold; font-size: 0.85rem; min-width: 44px; text-align: center;">100%</span>
        <button type="button" class="doc-btn" onclick="stepZoom(0.2)">➕</button>
        <button type="button" class="doc-btn" onclick="resetZoom()">🔄 100%</button>
        <button type="button" class="doc-btn" onclick="fitWidthZoom()">↔️ Pas Lebar</button>
        <button type="button" class="doc-btn" style="background: #059669; color: #fff;" onclick="downloadCurrentPdf()">📥 Unduh PDF</button>
      </div>
    </div>

    <div style="background: #111726; padding: 8px 16px; border-bottom: 1px solid #1e293b; display: flex; align-items: center; gap: 12px;">
      <span style="font-size: 0.78rem; color: #94a3b8; white-space: nowrap;">Perbesaran:</span>
      <input type="range" id="zoomSlider" min="50" max="250" value="100" step="5" oninput="setZoomScale(this.value / 100.0)">
    </div>

    <div class="doc-viewport" id="docViewport">
      <div class="doc-container" id="docContainer">
      </div>
    </div>
  </div>

  <script>
    let selectedImageBase64 = null;
    let currentProfileData = null;
    let cameraStream = null;
    let animFrameId = null;
    let currentZoom = 1.0;
    let sliderDebounceTimer = null;
    let lastHudDrawTime = 0;
    let clientProfileCurve = null;

    // Jam Falak Presisi (WIB UTC+7 & UTC)
    function updateClocks() {
      const now = new Date();
      const utcStr = now.toISOString().substr(11, 8);
      const wibTime = new Date(now.getTime() + (7 * 3600 * 1000));
      const wibStr = wibTime.toISOString().substr(11, 8);
      const elWib = document.getElementById('clockWib');
      const elUtc = document.getElementById('clockUtc');
      if (elWib) elWib.innerText = wibStr;
      if (elUtc) elUtc.innerText = utcStr;
    }
    setInterval(updateClocks, 1000);
    updateClocks();

    // Konversi Sudut ke Sexagesimal DMS (+DD° MM' SS.SS")
    function formatDms(deg) {
      const sign = deg < 0 ? "-" : "+";
      const abs = Math.abs(deg);
      const d = Math.floor(abs);
      const remMin = (abs - d) * 60;
      const m = Math.floor(remMin);
      const s = ((remMin - m) * 60).toFixed(1);
      return sign + String(d).padStart(2, '0') + "° " + String(m).padStart(2, '0') + "' " + String(s).padStart(4, '0') + '"';
    }

    // Tampilkan foto langsung ke preview saat dipilih, dan kompresi latar belakang
    function compressAndSetImage(file, statusText) {
      const reader = new FileReader();
      reader.onload = function(e) {
        const dataUrl = e.target.result;
        selectedImageBase64 = dataUrl;
        displayLoadedImage(dataUrl, statusText);

        // Kompresi latar belakang jika resolusi foto sangat besar (misal 12-48 MP kamera HP)
        const img = new Image();
        img.onload = function() {
          let w = img.width;
          let h = img.height;
          const maxDim = 1280;
          if (w > maxDim || h > maxDim) {
            if (w > h) {
              h = Math.round((h * maxDim) / w);
              w = maxDim;
            } else {
              w = Math.round((w * maxDim) / h);
              h = maxDim;
            }
            const canvas = document.createElement('canvas');
            canvas.width = w;
            canvas.height = h;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, w, h);
            selectedImageBase64 = canvas.toDataURL('image/jpeg', 0.86);
          }
        };
        img.src = dataUrl;
      };
      reader.readAsDataURL(file);
    }

    function onFileSelected(input) {
      if (input.files && input.files[0]) {
        const sourceName = input.id === 'galleryInput' ? 'Penyimpanan Berkas' : 'Kamera / Webcam';
        compressAndSetImage(input.files[0], "Foto siap dari " + sourceName);
        input.value = "";
      }
    }

    function displayLoadedImage(b64, statusText) {
      const preview = document.getElementById('rawPreview');
      preview.src = b64;
      preview.style.display = 'block';
      const dropArea = document.getElementById('dropArea');
      if (dropArea) dropArea.classList.add('active');
      document.getElementById('lblPhotoStatus').innerText = statusText || "Foto Terpilih";
      document.getElementById('lblPhotoStatus').style.color = "#10b981";
      stopLiveCamera();
    }

    function loadSamplePhoto() {
      fetch('/api/sample_image')
        .then(res => res.json())
        .then(data => {
          selectedImageBase64 = data.image_base64;
          displayLoadedImage(selectedImageBase64, "Foto contoh lanskap ufuk terpasang");
        })
        .catch(err => {
          alert("Gagal memuat contoh foto: " + err.message);
        });
    }

    let currentCameraDeviceId = null;

    function toggleHpCameraGuide() {
      const guide = document.getElementById('hpCamGuide');
      if (guide) {
        guide.style.display = guide.style.display === 'none' ? 'block' : 'none';
      }
    }

    async function updateCameraDeviceList() {
      const sel = document.getElementById('cameraSourceSelect');
      if (!sel || !navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
      try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoDevices = devices.filter(d => d.kind === 'videoinput');
        if (videoDevices.length === 0) return;

        sel.innerHTML = "";
        videoDevices.forEach((dev, idx) => {
          const opt = document.createElement('option');
          opt.value = dev.deviceId;
          let label = dev.label || `Kamera ${idx + 1}`;
          if (/iriun/i.test(label)) label = "📱 " + label + " (Kamera HP)";
          else if (/droid/i.test(label)) label = "📱 " + label + " (Kamera HP)";
          else if (/camo|epoc/i.test(label)) label = "📱 " + label + " (Kamera HP)";
          else if (/integrated|built-in/i.test(label)) label = "💻 " + label + " (Webcam Laptop)";
          else if (/usb/i.test(label)) label = "🔭 " + label + " (USB/Teleskop)";
          opt.text = label;
          if (currentCameraDeviceId && dev.deviceId === currentCameraDeviceId) {
            opt.selected = true;
          }
          sel.appendChild(opt);
        });
      } catch (e) {
        console.warn("Gagal membaca daftar kamera:", e);
      }
    }

    async function onCameraDeviceSelected(deviceId) {
      if (!deviceId) return;
      currentCameraDeviceId = deviceId;
      if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
      }
      await startLiveCamera(deviceId);
    }

    async function startLiveCamera(preferredDeviceId) {
      const wrapper = document.getElementById('liveCamWrapper');
      const video = document.getElementById('cameraVideo');
      wrapper.style.display = 'block';

      try {
        const targetId = preferredDeviceId || currentCameraDeviceId;
        const videoConstraints = {
          width: { ideal: 1280 },
          height: { ideal: 720 }
        };
        if (targetId) {
          videoConstraints.deviceId = { exact: targetId };
        } else {
          videoConstraints.facingMode = { ideal: "environment" };
        }

        cameraStream = await navigator.mediaDevices.getUserMedia({
          video: videoConstraints,
          audio: false
        });
        video.srcObject = cameraStream;
        video.onloadedmetadata = () => {
          video.play();
          drawLiveHudLoop();
          updateCameraDeviceList();
        };
      } catch (err) {
        alert("Tidak dapat membuka kamera: " + err.message + ". Pastikan izin kamera browser diaktifkan atau aplikasi webcam (Iriun/DroidCam) sudah berjalan.");
        wrapper.style.display = 'none';
      }
    }

    function stopLiveCamera() {
      if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
      }
      if (animFrameId) {
        cancelAnimationFrame(animFrameId);
        animFrameId = null;
      }
      document.getElementById('liveCamWrapper').style.display = 'none';
    }

    function drawLiveHudLoop(timestamp) {
      const video = document.getElementById('cameraVideo');
      const canvas = document.getElementById('cameraOverlay');
      if (!cameraStream || video.paused || video.ended) return;

      if (!timestamp || timestamp - lastHudDrawTime > 32) {
        lastHudDrawTime = timestamp || 0;

        if (video.videoWidth > 0 && video.videoHeight > 0) {
          if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
          }

          const ctx = canvas.getContext('2d');
          const w = canvas.width;
          const h = canvas.height;
          ctx.clearRect(0, 0, w, h);

          const cy = h / 2.0;
          const cx = w / 2.0;

          ctx.strokeStyle = "rgba(255, 255, 255, 0.2)";
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(w / 3, 0); ctx.lineTo(w / 3, h);
          ctx.moveTo(2 * w / 3, 0); ctx.lineTo(2 * w / 3, h);
          ctx.moveTo(0, h / 3); ctx.lineTo(w, h / 3);
          ctx.moveTo(0, 2 * h / 3); ctx.lineTo(w, 2 * h / 3);
          ctx.stroke();

          ctx.strokeStyle = "#38bdf8";
          ctx.lineWidth = 2;
          ctx.setLineDash([12, 8]);
          ctx.beginPath();
          ctx.moveTo(0, cy);
          ctx.lineTo(w, cy);
          ctx.stroke();
          ctx.setLineDash([]);

          ctx.fillStyle = "#38bdf8";
          ctx.font = "bold 18px sans-serif";
          ctx.fillText("── Ufuk Hakiki (0.00°) ──", 20, cy - 8);

          const dipY = cy + (h * 0.025);
          ctx.strokeStyle = "#fbbf24";
          ctx.lineWidth = 1.5;
          ctx.setLineDash([6, 6]);
          ctx.beginPath();
          ctx.moveTo(0, dipY);
          ctx.lineTo(w, dipY);
          ctx.stroke();
          ctx.setLineDash([]);

          ctx.fillStyle = "#fbbf24";
          ctx.font = "bold 15px sans-serif";
          ctx.fillText("── Ufuk Laut Dip (-0.20°) ──", 20, dipY + 20);

          ctx.strokeStyle = "#ef4444";
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.moveTo(cx - 20, cy); ctx.lineTo(cx + 20, cy);
          ctx.moveTo(cx, cy - 20); ctx.lineTo(cx, cy + 20);
          ctx.stroke();

          ctx.beginPath();
          ctx.arc(cx, cy, 12, 0, 2 * Math.PI);
          ctx.strokeStyle = "rgba(255, 255, 255, 0.85)";
          ctx.stroke();

          ctx.fillStyle = "rgba(15, 23, 42, 0.75)";
          ctx.fillRect(w / 2 - 150, 14, 300, 38);
          ctx.strokeStyle = "#38bdf8";
          ctx.strokeRect(w / 2 - 150, 14, 300, 38);

          ctx.fillStyle = "#ffffff";
          ctx.font = "bold 15px sans-serif";
          ctx.textAlign = "center";
          ctx.fillText("🧭 BIDIKAN BARAT 270.0° • LIVE", w / 2, 38);
          ctx.textAlign = "left";
        }
      }

      animFrameId = requestAnimationFrame(drawLiveHudLoop);
    }

    function captureLiveFrame() {
      const video = document.getElementById('cameraVideo');
      if (!cameraStream || video.videoWidth === 0) return;

      const hiddenCanvas = document.createElement('canvas');
      hiddenCanvas.width = video.videoWidth;
      hiddenCanvas.height = video.videoHeight;
      const ctx = hiddenCanvas.getContext('2d');
      ctx.drawImage(video, 0, 0, hiddenCanvas.width, hiddenCanvas.height);

      selectedImageBase64 = hiddenCanvas.toDataURL('image/jpeg', 0.86);
      displayLoadedImage(selectedImageBase64, "Foto berhasil dipotret dari Kamera Live");
    }

    function getGPS() {
      if (!navigator.geolocation) {
        alert("Geolocation tidak didukung pada browser ini.");
        return;
      }
      navigator.geolocation.getCurrentPosition(
        pos => {
          document.getElementById('inpLat').value = pos.coords.latitude.toFixed(5);
          document.getElementById('inpLon').value = pos.coords.longitude.toFixed(5);
          if (pos.coords.altitude) {
            document.getElementById('inpAlt').value = Math.round(pos.coords.altitude);
          }
          alert("Lokasi GPS berhasil disinkronkan!");
        },
        err => {
          alert("Gagal membaca GPS: " + err.message + ". Silakan isi secara manual.");
        },
        { enableHighAccuracy: true }
      );
    }

    function processImage() {
      if (!selectedImageBase64) {
        alert("Silakan potret foto atau pilih gambar dari galeri terlebih dahulu.");
        return;
      }

      document.getElementById('loadingText').innerText = "Sedang mengekstrak kontur ufuk secara instan...";
      document.getElementById('loading').style.display = 'block';
      document.getElementById('btnProcess').disabled = true;

      const payload = {
        image_base64: selectedImageBase64,
        azimuth: parseFloat(document.getElementById('inpAzimuth').value) || 270.0,
        tilt: parseFloat(document.getElementById('inpTilt').value) || 0.0,
        latitude: parseFloat(document.getElementById('inpLat').value) || -7.98,
        longitude: parseFloat(document.getElementById('inpLon').value) || 110.306,
        altitude: parseFloat(document.getElementById('inpAlt').value) || 45.0
      };

      fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(res => res.json())
      .then(data => {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('btnProcess').disabled = false;

        if (data.error) {
          alert("Gagal memproses gambar: " + data.error);
          return;
        }

        currentProfileData = data;
        clientProfileCurve = {
          azimuths: data.profile_curve.az,
          elevations: data.profile_curve.el,
          dip_deg: data.target_analysis.dip_deg || 0.20
        };

        document.getElementById('resOverlayImg').src = data.overlay_base64;
        document.getElementById('resPlotImg').src = data.plot_base64;
        
        const slider = document.getElementById('sliderAz');
        slider.min = data.az_min.toFixed(2);
        slider.max = data.az_max.toFixed(2);
        slider.value = payload.azimuth.toFixed(2);
        document.getElementById('lblSliderAz').innerText = payload.azimuth.toFixed(2) + "°";
        if (document.getElementById('lblMinAz')) document.getElementById('lblMinAz').innerText = data.az_min.toFixed(1) + "°";
        if (document.getElementById('lblMaxAz')) document.getElementById('lblMaxAz').innerText = data.az_max.toFixed(1) + "°";

        updateTargetDisplay(payload.azimuth, data.target_analysis);

        if (document.getElementById('rightPlaceholder')) {
          document.getElementById('rightPlaceholder').style.display = 'none';
        }
        document.getElementById('resultSection').style.display = 'block';
        document.getElementById('resultSection').scrollIntoView({ behavior: 'smooth' });
      })
      .catch(err => {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('btnProcess').disabled = false;
        alert("Terjadi kesalahan jaringan atau server.");
      });
    }

    // Zero-latency slider: hitung langsung di ponsel klien dalam 0 milidetik!
    function onSliderTargetChanged(val) {
      const azVal = parseFloat(val);
      document.getElementById('lblSliderAz').innerText = azVal.toFixed(2) + "°";

      if (clientProfileCurve && clientProfileCurve.azimuths) {
        const azs = clientProfileCurve.azimuths;
        const els = clientProfileCurve.elevations;
        let closestIdx = 0;
        let minDiff = 9999;
        for (let i = 0; i < azs.length; i++) {
          const diff = Math.abs(azs[i] - azVal);
          if (diff < minDiff) {
            minDiff = diff;
            closestIdx = i;
          }
        }
        const targetAlt = els[closestIdx];
        const dip = clientProfileCurve.dip_deg;

        // Analisis instan di memori JS ponsel
        let category = "Ufuk Terbuka";
        let status = "Cukup Layak";
        let severity = "Cukup Layak";
        if (targetAlt <= -dip + 0.05) {
          category = "Ufuk Terbuka Bebas"; severity = "Sangat Baik";
        } else if (targetAlt <= 0.0) {
          category = "Ufuk Rendah Terbuka"; severity = "Sangat Baik";
        } else if (targetAlt <= 1.2) {
          category = "Halangan Rendah"; severity = "Cukup Layak";
        } else {
          category = "Halangan Bukit/Gunung"; severity = "Perlu Waspada";
        }

        updateTargetDisplay(azVal, {
          target_alt: targetAlt,
          dip_deg: dip,
          severity: severity,
          category: category
        });
      }

      // Perbarui visual plot latar belakang dengan debounce cepat 90ms
      if (sliderDebounceTimer) clearTimeout(sliderDebounceTimer);
      sliderDebounceTimer = setTimeout(() => {
        fetch('/api/recalculate_target', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target_az: azVal })
        })
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            document.getElementById('resPlotImg').src = data.plot_base64;
            document.getElementById('resOverlayImg').src = data.overlay_base64;
          }
        });
      }, 90);
    }

    function updateTargetDisplay(targetAz, analysis) {
      const altStr = (analysis.target_alt >= 0 ? "+" : "") + analysis.target_alt.toFixed(2) + "°";
      document.getElementById('resTargetAlt').innerText = altStr;
      if (document.getElementById('resTargetAltDms')) {
        document.getElementById('resTargetAltDms').innerText = formatDms(analysis.target_alt);
      }
      const dipVal = analysis.dip_deg || 0.20;
      document.getElementById('resDip').innerText = "-" + dipVal.toFixed(2) + "°";
      if (document.getElementById('resDipDms')) {
        document.getElementById('resDipDms').innerText = formatDms(-dipVal);
      }
      if (document.getElementById('resDeltaHakiki')) {
        const delta = analysis.target_alt - 0.0;
        document.getElementById('resDeltaHakiki').innerText = (delta >= 0 ? "+" : "") + delta.toFixed(2) + "°";
      }
      document.getElementById('resStatusTxt').innerText = analysis.severity || analysis.status || "Layak";
      const cat = analysis.category || analysis.status || "Ufuk Terbuka";
      if (document.getElementById('resCategoryTxt')) {
        document.getElementById('resCategoryTxt').innerText = cat;
      }
      
      const smartDesc = `Berdasarkan ekstraksi kontur computer vision pada azimut bidikan ${targetAz.toFixed(2)}°, diperoleh tinggi rintangan ufuk pada azimut sasaran ${targetAz.toFixed(2)}° sebesar ${altStr}. Kondisi ufuk: ${cat}.`;
      document.getElementById('resDescText').innerText = smartDesc;
      document.getElementById('textDesc').value = smartDesc;

      let smartRec = "";
      if (analysis.target_alt <= 0.0) {
        smartRec = `Lokasi pengamatan REKOMENDED (LAYAK). Tidak terdapat rintangan signifikan pada azimut ${targetAz.toFixed(2)}°. Ufuk mar'i berada di bawah atau sejajar ufuk hakiki sehingga sangat mendukung rukyatul hilal.`;
      } else if (analysis.target_alt <= 1.2) {
        smartRec = `Terdapat siluet halangan rendah setinggi ${altStr}. Hilal dengan ketinggian di atas 1.5° masih aman terpantau.`;
      } else {
        smartRec = `Lokasi pengamatan PERLU DIPERHATIKAN. Terdapat halangan daratan/bukit setinggi ${altStr} pada azimut ${targetAz.toFixed(2)}°. Hilal dengan ketinggian di bawah rintangan ini akan terhalang. Ambang MABIMS 3° berada dekat halangan.`;
      }
      document.getElementById('textRec').value = smartRec;
    }

    function openReportPreview() {
      const modal = document.getElementById('reportPreviewModal');
      const container = document.getElementById('docContainer');
      modal.style.display = 'flex';
      container.innerHTML = "<p style='color: #38bdf8; padding: 40px; font-weight: bold;'>⏳ Sedang merender dokumen PDF resmi...</p>";

      const payload = {
        location_name: document.getElementById('editLocation').value.trim() || "Pos Observasi Falak Lapangan",
        observer_name: document.getElementById('editObserver').value.trim() || "Tim Falak & Astronomi",
        observer_notes: document.getElementById('textDesc').value.trim(),
        recommendation_text: document.getElementById('textRec').value.trim()
      };

      fetch('/api/preview_pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(res => res.json())
      .then(data => {
        if (data.error) {
          container.innerHTML = `<p style="color: #ef4444; padding: 40px;">Gagal memuat dokumen: ${data.error}</p>`;
          return;
        }

        container.innerHTML = "";
        data.pages.forEach((pageB64, idx) => {
          const card = document.createElement('div');
          card.className = "doc-page";
          card.innerHTML = `
            <img src="${pageB64}" alt="Halaman ${idx + 1}" loading="lazy">
            <div class="doc-page-footer">
              Dokumen Berita Acara Falak • Halaman ${idx + 1} dari ${data.pages.length}
            </div>
          `;
          container.appendChild(card);
        });

        resetZoom();
      })
      .catch(err => {
        container.innerHTML = `<p style="color: #ef4444; padding: 40px;">Koneksi gagal: ${err.message}</p>`;
      });
    }

    function closeReportPreview() {
      document.getElementById('reportPreviewModal').style.display = 'none';
    }

    function setZoomScale(scale) {
      currentZoom = Math.max(0.4, Math.min(2.8, scale));
      const container = document.getElementById('docContainer');
      container.style.transform = `scale(${currentZoom})`;
      document.getElementById('lblZoomLevel').innerText = Math.round(currentZoom * 100) + "%";
      document.getElementById('zoomSlider').value = Math.round(currentZoom * 100);
    }

    function stepZoom(delta) {
      setZoomScale(currentZoom + delta);
    }

    function resetZoom() {
      setZoomScale(1.0);
    }

    function fitWidthZoom() {
      const viewport = document.getElementById('docViewport');
      const vw = viewport.clientWidth - 32;
      const scale = Math.max(0.4, Math.min(2.0, vw / 650.0));
      setZoomScale(scale);
    }

    // Dukungan Gestur Sentuh 2 Jari (Pinch-to-Zoom & Pan) pada Layar HP
    let touchStartDist = 0;
    let touchStartZoom = 1.0;

    function getTouchesDist(touches) {
      const dx = touches[0].clientX - touches[1].clientX;
      const dy = touches[0].clientY - touches[1].clientY;
      return Math.sqrt(dx * dx + dy * dy);
    }

    const docView = document.getElementById('docViewport');
    docView.addEventListener('touchstart', function(e) {
      if (e.touches.length === 2) {
        touchStartDist = getTouchesDist(e.touches);
        touchStartZoom = currentZoom;
      }
    }, { passive: true });

    docView.addEventListener('touchmove', function(e) {
      if (e.touches.length === 2 && touchStartDist > 0) {
        const curDist = getTouchesDist(e.touches);
        const factor = curDist / touchStartDist;
        setZoomScale(touchStartZoom * factor);
        e.preventDefault();
      }
    }, { passive: false });

    docView.addEventListener('touchend', function(e) {
      if (e.touches.length < 2) {
        touchStartDist = 0;
      }
    }, { passive: true });

    function downloadCurrentPdf() {
      const loc = encodeURIComponent(document.getElementById('editLocation').value.trim() || "Pos Observasi");
      window.open('/api/download_pdf?loc=' + loc, '_blank');
    }

    function downloadCsv() {
      window.open('/api/download_csv', '_blank');
    }

    function openDataTableModal() {
      if (!clientProfileCurve || !clientProfileCurve.azimuths) {
        alert("Silakan proses foto atau muat gambar terlebih dahulu untuk melihat data numerik.");
        return;
      }
      const modal = document.getElementById('dataTableModal');
      modal.style.display = 'flex';
      renderDataTable(document.getElementById('selTableInterval').value || '0.5');
    }

    function closeDataTableModal() {
      document.getElementById('dataTableModal').style.display = 'none';
    }

    function renderDataTable(mode) {
      if (!clientProfileCurve || !clientProfileCurve.azimuths) return;
      const azs = clientProfileCurve.azimuths;
      const els = clientProfileCurve.elevations;
      const dip = clientProfileCurve.dip_deg || 0.20;

      let minEl = 999, maxEl = -999;
      for (let i = 0; i < els.length; i++) {
        if (els[i] < minEl) minEl = els[i];
        if (els[i] > maxEl) maxEl = els[i];
      }
      const minAz = azs[0];
      const maxAz = azs[azs.length - 1];

      document.getElementById('tblAzRange').innerText = minAz.toFixed(2) + "° s.d. " + maxAz.toFixed(2) + "°";
      document.getElementById('tblDipVal').innerText = "-" + dip.toFixed(2) + "°";
      document.getElementById('tblElevRange').innerText = (minEl >= 0 ? "+" : "") + minEl.toFixed(2) + "° s.d. " + (maxEl >= 0 ? "+" : "") + maxEl.toFixed(2) + "°";

      const tbody = document.getElementById('numericTableBody');
      tbody.innerHTML = "";

      let stepInterval = 0.5;
      if (mode === "0.25") stepInterval = 0.25;
      else if (mode === "0.1") stepInterval = 0.10;
      else if (mode === "all") stepInterval = 0.0;

      let selectedRows = [];
      if (stepInterval === 0.0) {
        for (let i = 0; i < azs.length; i++) {
          selectedRows.push({ az: azs[i], el: els[i] });
        }
      } else {
        let lastTarget = Math.floor(minAz / stepInterval) * stepInterval;
        while (lastTarget <= maxAz + 0.001) {
          if (lastTarget >= minAz - 0.001 && lastTarget <= maxAz + 0.001) {
            let bestIdx = 0, bestDiff = 9999;
            for (let i = 0; i < azs.length; i++) {
              const diff = Math.abs(azs[i] - lastTarget);
              if (diff < bestDiff) {
                bestDiff = diff;
                bestIdx = i;
              }
            }
            selectedRows.push({ az: azs[bestIdx], el: els[bestIdx] });
          }
          lastTarget += stepInterval;
        }
      }

      document.getElementById('tblSampleCount').innerText = selectedRows.length + " Titik Data";

      let html = "";
      selectedRows.forEach((row, idx) => {
        const el = row.el;
        const az = row.az;
        const elStr = (el >= 0 ? "+" : "") + el.toFixed(2) + "°";
        const dmsStr = formatDms(el);
        const deltaHakiki = el - 0.0;
        const deltaHakikiStr = (deltaHakiki >= 0 ? "+" : "") + deltaHakiki.toFixed(2) + "°";
        const deltaDip = el - (-dip);
        const deltaDipStr = (deltaDip >= 0 ? "+" : "") + deltaDip.toFixed(2) + "°";

        let badgeHtml = "";
        if (el <= -dip + 0.05) {
          badgeHtml = '<span class="badge" style="background:#064e3b; color:#34d399; border:1px solid #059669;">Sangat Terbuka (Bebas)</span>';
        } else if (el <= 0.0) {
          badgeHtml = '<span class="badge" style="background:#065f46; color:#a7f3d0; border:1px solid #10b981;">Ufuk Rendah Terbuka</span>';
        } else if (el <= 1.2) {
          badgeHtml = '<span class="badge" style="background:#0c4a6e; color:#38bdf8; border:1px solid #0284c7;">Halangan Rendah (Aman)</span>';
        } else {
          badgeHtml = '<span class="badge" style="background:#451a03; color:#fcd34d; border:1px solid #d97706;">Halangan Tinggi (Waspada)</span>';
        }

        const bgCol = idx % 2 === 0 ? '#131b2a' : '#172235';
        html += `<tr style="background: ${bgCol}; border-bottom: 1px solid #1e293b;">
          <td style="padding: 8px 12px; color: #64748b; font-family: monospace; border-right: 1px solid #1e293b;">${idx + 1}</td>
          <td style="padding: 8px 12px; font-weight: bold; color: #38bdf8; font-family: monospace; border-right: 1px solid #1e293b;">${az.toFixed(2)}°</td>
          <td style="padding: 8px 12px; font-weight: bold; color: #f8fafc; font-family: monospace; border-right: 1px solid #1e293b;">${elStr}</td>
          <td style="padding: 8px 12px; color: #cbd5e1; font-family: monospace; border-right: 1px solid #1e293b;">${dmsStr}</td>
          <td style="padding: 8px 12px; color: #94a3b8; font-family: monospace; border-right: 1px solid #1e293b;">${deltaHakikiStr}</td>
          <td style="padding: 8px 12px; color: #94a3b8; font-family: monospace; border-right: 1px solid #1e293b;">${deltaDipStr}</td>
          <td style="padding: 8px 12px;">${badgeHtml}</td>
        </tr>`;
      });
      tbody.innerHTML = html;
    }

    function copyTableToClipboard() {
      const tbody = document.getElementById('numericTableBody');
      const rows = tbody.querySelectorAll('tr');
      if (rows.length === 0) {
        alert("Tidak ada data untuk disalin.");
        return;
      }
      const headerRow = ["No", "Azimut (°)", "Elevasi Mar'i (°)", "Format DMS", "Selisih Hakiki (Δ0°)", "Selisih Laut (ΔDip)", "Status"].join("\\t");
      let tsv = headerRow + "\\n";
      rows.forEach(r => {
        const cells = Array.from(r.querySelectorAll('td')).map(c => c.innerText.trim());
        tsv += cells.join("\\t") + "\\n";
      });
      navigator.clipboard.writeText(tsv).then(() => {
        alert("Tabel data berhasil disalin ke clipboard! Anda bisa langsung menempelkannya (paste) ke Microsoft Excel atau Google Sheets.");
      }).catch(err => {
        alert("Gagal menyalin: " + err.message);
      });
    }

    function resetObservation() {
      selectedImageBase64 = null;
      document.getElementById('rawPreview').style.display = 'none';
      document.getElementById('resultSection').style.display = 'none';
      if (document.getElementById('rightPlaceholder')) {
        document.getElementById('rightPlaceholder').style.display = 'block';
      }
      document.getElementById('lblPhotoStatus').innerText = "Belum ada foto yang dipilih";
      document.getElementById('lblPhotoStatus').style.color = "#94a3b8";
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/sample_image", methods=["GET"])
def api_sample_image():
    sample_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sample_horizon.jpg")
    if not os.path.exists(sample_path):
        img_bgr = generate_synthetic_horizon(1280, 720)
    else:
        img_bgr = cv2.imread(sample_path)
    
    _, buffer = cv2.imencode(".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    b64_str = "data:image/jpeg;base64," + base64.b64encode(buffer).decode("utf-8")
    return jsonify({"image_base64": b64_str})


def fast_render_plot_image(azimuths, elevations, dip_deg, target_az=None, target_alt=None):
    """Render kurva profil 2D menggunakan OpenCV murni (30 ms vs 2400 ms Matplotlib)."""
    W, H = 680, 310
    img = np.full((H, W, 3), (42, 27, 19), dtype=np.uint8)
    
    lm, rm, tm, bm = 55, 20, 28, 40
    pw = W - lm - rm
    ph = H - tm - bm
    
    cv2.rectangle(img, (lm, tm), (lm + pw, tm + ph), (23, 15, 11), -1)
    
    az_min = float(azimuths[0])
    az_max = float(azimuths[-1])
    min_y = min(-dip_deg - 0.5, float(np.min(elevations)) - 0.5, -1.0)
    max_y = max(float(np.max(elevations)) + 0.8, 2.0)
    
    def to_screen(az, el):
        x = lm + int((az - az_min) / (az_max - az_min + 1e-6) * pw)
        y = tm + int((max_y - el) / (max_y - min_y + 1e-6) * ph)
        return x, y

    y_step = 1.0 if (max_y - min_y) < 6 else 2.0
    for el_val in np.arange(np.ceil(min_y), max_y, y_step):
        _, sy = to_screen(az_min, el_val)
        if tm <= sy <= tm + ph:
            cv2.line(img, (lm, sy), (lm + pw, sy), (55, 40, 30), 1)
            cv2.putText(img, f'{el_val:+.1f}*', (10, sy + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (184, 163, 148), 1, cv2.LINE_AA)

    for frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
        az_val = az_min + frac * (az_max - az_min)
        sx, _ = to_screen(az_val, min_y)
        cv2.line(img, (sx, tm), (sx, tm + ph), (55, 40, 30), 1)
        cv2.putText(img, f'{az_val:.1f}*', (sx - 18, tm + ph + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (184, 163, 148), 1, cv2.LINE_AA)

    _, y_hakiki = to_screen(az_min, 0.0)
    if tm <= y_hakiki <= tm + ph:
        for dx in range(lm, lm + pw, 16):
            cv2.line(img, (dx, y_hakiki), (min(lm + pw, dx + 9), y_hakiki), (248, 189, 56), 1, cv2.LINE_AA)
        cv2.putText(img, 'Ufuk Hakiki (0.00*)', (lm + 8, max(tm + 12, y_hakiki - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (248, 189, 56), 1, cv2.LINE_AA)

    if dip_deg > 0:
        _, y_dip = to_screen(az_min, -dip_deg)
        if tm <= y_dip <= tm + ph:
            for dx in range(lm, lm + pw, 10):
                cv2.line(img, (dx, y_dip), (min(lm + pw, dx + 4), y_dip), (36, 191, 251), 1, cv2.LINE_AA)
            cv2.putText(img, f'Ufuk Laut Dip (-{dip_deg:.2f}*)', (lm + 8, min(tm + ph - 6, y_dip + 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (36, 191, 251), 1, cv2.LINE_AA)

    step = max(1, len(azimuths) // pw)
    pts = [to_screen(azimuths[i], elevations[i]) for i in range(0, len(azimuths), step)]
    if len(pts) > 1:
        pts_arr = np.array(pts, dtype=np.int32)
        poly = np.vstack([pts_arr, [lm + pw, tm + ph], [lm, tm + ph]])
        overlay = img.copy()
        cv2.fillPoly(overlay, [poly], (40, 20, 160))
        cv2.addWeighted(overlay, 0.45, img, 0.55, 0, img)
        cv2.polylines(img, [pts_arr], False, (82, 82, 255), 2, cv2.LINE_AA)

    if target_az is not None:
        t_alt_val = target_alt if target_alt is not None else 0.0
        tx, ty = to_screen(target_az, t_alt_val)
        cv2.line(img, (tx, tm), (tx, tm + ph), (251, 64, 224), 2, cv2.LINE_AA)
        cv2.circle(img, (tx, ty), 5, (251, 64, 224), -1, cv2.LINE_AA)
        cv2.circle(img, (tx, ty), 8, (255, 255, 255), 1, cv2.LINE_AA)

    cv2.rectangle(img, (lm, tm), (lm + pw, tm + ph), (71, 49, 35), 1)
    cv2.putText(img, 'Kurva Profil Elevasi Ufuk Mar-i vs Azimut', (lm, tm - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (248, 189, 56), 1, cv2.LINE_AA)
    
    _, buf = cv2.imencode(".png", img)
    return "data:image/png;base64," + base64.b64encode(buf).decode("utf-8")


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    global LAST_ANALYSIS
    data = request.json or {}
    raw_b64 = data.get("image_base64", "")
    azimuth = float(data.get("azimuth", 270.0))
    tilt = float(data.get("tilt", 0.0))
    lat = float(data.get("latitude", -7.98))
    lon = float(data.get("longitude", 110.3061))
    alt = float(data.get("altitude", 45.0))

    if not raw_b64:
        return jsonify({"error": "Citra kosong"}), 400

    if "," in raw_b64:
        raw_b64 = raw_b64.split(",")[1]
    img_bytes = base64.b64decode(raw_b64)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    image_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if image_bgr is None:
        return jsonify({"error": "Format gambar tidak didukung"}), 400

    h, w = image_bgr.shape[:2]

    # Ekstraksi kontur teroptimasi vektorisasi NumPy
    horizon_y, mask = detector.detect_horizon(
        image_bgr,
        method=detector.METHOD_GRADIENT,
        threshold_offset=0,
        blur_kernel=5,
        smooth_window=15
    )

    profile_data = detector.compute_horizon_profile(
        horizon_y=horizon_y,
        img_w=w,
        img_h=h,
        az_center=azimuth,
        hfov=15.0,
        vfov=8.5,
        tilt_center=tilt,
        elevation_m=alt
    )

    target_az = azimuth
    az_arr = profile_data["azimuths"]
    el_arr = profile_data["elevations"]
    t_idx = int(np.argmin(np.abs(az_arr - target_az)))
    target_alt = float(el_arr[t_idx])
    target_analysis = classify_obstacle(target_alt, profile_data["dip_deg"])
    target_analysis["target_az"] = target_az
    target_analysis["target_alt"] = target_alt
    target_analysis["dip_deg"] = profile_data["dip_deg"]

    overlay_bgr = detector.render_overlay(
        image_bgr=image_bgr,
        horizon_y=horizon_y,
        azimuths=az_arr,
        elevations=el_arr,
        target_az=target_az,
        dip_deg=profile_data["dip_deg"],
        az_center=azimuth,
        hfov=15.0,
        vfov=8.5,
        tilt_center=tilt
    )

    _, ov_buf = cv2.imencode(".jpg", overlay_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    overlay_b64 = "data:image/jpeg;base64," + base64.b64encode(ov_buf).decode("utf-8")

    # Render kurva cepat OpenCV
    plot_b64 = fast_render_plot_image(az_arr, el_arr, profile_data["dip_deg"], target_az, target_alt)

    # Downsample kurva untuk komputasi instan di ponsel klien (150 poin)
    curve_step = max(1, len(az_arr) // 150)
    profile_curve = {
        "az": [float(az_arr[i]) for i in range(0, len(az_arr), curve_step)],
        "el": [float(el_arr[i]) for i in range(0, len(el_arr), curve_step)]
    }

    LAST_ANALYSIS = {
        "image_bgr": image_bgr,
        "overlay_bgr": overlay_bgr,
        "horizon_y": horizon_y,
        "profile_data": profile_data,
        "target_analysis": target_analysis,
        "latitude": lat,
        "longitude": lon,
        "altitude": alt,
        "azimuth": azimuth,
        "tilt": tilt,
        "w": w,
        "h": h,
    }

    return jsonify({
        "success": True,
        "overlay_base64": overlay_b64,
        "plot_base64": plot_b64,
        "az_min": float(az_arr[0]),
        "az_max": float(az_arr[-1]),
        "target_analysis": target_analysis,
        "profile_curve": profile_curve
    })


@app.route("/api/recalculate_target", methods=["POST"])
def api_recalculate_target():
    global LAST_ANALYSIS
    if not LAST_ANALYSIS:
        return jsonify({"error": "Belum ada analisis aktif"}), 400

    data = request.json or {}
    target_az = float(data.get("target_az", LAST_ANALYSIS["azimuth"]))

    prof = LAST_ANALYSIS["profile_data"]
    az_arr = prof["azimuths"]
    el_arr = prof["elevations"]
    t_idx = int(np.argmin(np.abs(az_arr - target_az)))
    target_alt = float(el_arr[t_idx])
    target_analysis = classify_obstacle(target_alt, prof["dip_deg"])
    target_analysis["target_az"] = target_az
    target_analysis["target_alt"] = target_alt
    target_analysis["dip_deg"] = prof["dip_deg"]

    overlay_bgr = detector.render_overlay(
        image_bgr=LAST_ANALYSIS["image_bgr"],
        horizon_y=LAST_ANALYSIS["horizon_y"],
        azimuths=az_arr,
        elevations=el_arr,
        target_az=target_az,
        dip_deg=prof["dip_deg"],
        az_center=LAST_ANALYSIS["azimuth"],
        hfov=15.0,
        vfov=8.5,
        tilt_center=LAST_ANALYSIS["tilt"]
    )
    _, ov_buf = cv2.imencode(".jpg", overlay_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    overlay_b64 = "data:image/jpeg;base64," + base64.b64encode(ov_buf).decode("utf-8")

    plot_b64 = fast_render_plot_image(az_arr, el_arr, prof["dip_deg"], target_az, target_alt)

    LAST_ANALYSIS["overlay_bgr"] = overlay_bgr
    LAST_ANALYSIS["target_analysis"] = target_analysis

    return jsonify({
        "success": True,
        "overlay_base64": overlay_b64,
        "plot_base64": plot_b64,
        "target_analysis": target_analysis
    })


def _generate_current_pdf_path(location_name=None, observer_notes=None, recommendation_text=None) -> str:
    global LAST_ANALYSIS
    if not LAST_ANALYSIS:
        raise ValueError("Belum ada data analisis aktif")

    exports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
    os.makedirs(exports_dir, exist_ok=True)
    pdf_path = os.path.join(exports_dir, f"Laporan_Ufuk_Web_{int(time.time())}.pdf")

    ta = LAST_ANALYSIS["target_analysis"]
    desc = observer_notes or f"Analisis berbasis Computer Vision pada azimut {ta['target_az']:.2f}°. Kondisi: {ta.get('category', 'Ufuk Mar-i')}."
    rec = recommendation_text or ta.get("recommendation", "Lokasi rukyatul hilal tervalidasi.")
    loc = location_name or "Pos Observasi Falak Lapangan"

    export_pdf_report(
        output_pdf_path=pdf_path,
        location_name=loc,
        latitude=LAST_ANALYSIS["latitude"],
        longitude=LAST_ANALYSIS["longitude"],
        elevation_m=LAST_ANALYSIS["altitude"],
        az_center=LAST_ANALYSIS["azimuth"],
        hfov=15.0,
        vfov=8.5,
        tilt_center=LAST_ANALYSIS["tilt"],
        dip_deg=LAST_ANALYSIS["profile_data"]["dip_deg"],
        profile_data=LAST_ANALYSIS["profile_data"],
        overlay_img_bgr=LAST_ANALYSIS["overlay_bgr"],
        target_analysis=ta,
        observer_notes=desc,
        recommendation_text=rec,
    )
    return pdf_path


@app.route("/api/preview_pdf", methods=["POST", "GET"])
def api_preview_pdf():
    try:
        data = request.json or {} if request.method == "POST" else {}
        loc = data.get("location_name") or request.args.get("loc")
        notes = data.get("observer_notes")
        rec = data.get("recommendation_text")

        pdf_path = _generate_current_pdf_path(location_name=loc, observer_notes=notes, recommendation_text=rec)
        pdf = pypdfium2.PdfDocument(pdf_path)
        pages_b64 = []
        for i in range(len(pdf)):
            pil_img = pdf[i].render(scale=1.4).to_pil()
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=80)
            pages_b64.append("data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8"))

        return jsonify({
            "success": True,
            "pages": pages_b64,
            "pdf_url": "/api/download_pdf"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/download_pdf", methods=["GET"])
def api_download_pdf():
    try:
        loc = request.args.get("loc")
        pdf_path = _generate_current_pdf_path(location_name=loc)
        return send_file(pdf_path, as_attachment=True, download_name="Laporan_Ufuk_Mar'i.pdf")
    except Exception as e:
        return f"Gagal membuat PDF: {str(e)}", 400


@app.route("/api/download_csv", methods=["GET"])
def api_download_csv():
    global LAST_ANALYSIS
    if not LAST_ANALYSIS:
        return "Belum ada data analisis aktif", 400

    exports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
    os.makedirs(exports_dir, exist_ok=True)
    csv_path = os.path.join(exports_dir, f"Data_Ufuk_Web_{int(time.time())}.csv")

    export_csv_data(
        output_csv_path=csv_path,
        profile_data=LAST_ANALYSIS["profile_data"],
        location_name="Pos Observasi Falak (Laptop)",
        az_center=LAST_ANALYSIS["azimuth"],
        dip_deg=LAST_ANALYSIS["profile_data"]["dip_deg"],
    )

    return send_file(csv_path, as_attachment=True, download_name="Data_Profil_Ufuk.csv")


def main():
    print("=" * 60)
    print("   APLIKASI PEMETAAN UFUK MAR'I (EDISI LAPTOP & DESKTOP)")
    print("   Buka dari Browser Laptop : http://127.0.0.1:5000")
    print("   Buka dari Jaringan Lokal : http://192.168.x.x:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)


if __name__ == "__main__":
    main()
