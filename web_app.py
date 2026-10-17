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
import math
import base64
import subprocess
import numpy as np
import cv2
import pypdfium2

from flask import Flask, request, jsonify, send_file, render_template_string

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.cv_engine import HorizonDetector
from core.falak_calc import calculate_dip, classify_obstacle, format_dms
from core.report_generator import export_pdf_report, export_csv_data, export_excel_data
from core.sample_generator import generate_synthetic_horizon
from core.compass_service import compass_service

app = Flask(__name__)
detector = HorizonDetector()
compass_service.start()

# Cache analisis terakhir
LAST_ANALYSIS = {}
PDF_CACHE = {"path": None, "hash": None, "pages": []}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
  <meta http-equiv="Pragma" content="no-cache">
  <meta http-equiv="Expires" content="0">
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

    /* 3 Photo Preview Slots */
    .photo-slots-wrapper {
      margin-top: 12px;
      background: #0f172a;
      border: 1px solid #233147;
      border-radius: 12px;
      padding: 12px;
    }
    .photo-slots-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }
    .photo-slots-title {
      font-size: 0.78rem;
      font-weight: 700;
      color: #94a3b8;
      display: flex;
      align-items: center;
      gap: 5px;
    }
    .btn-slot-del {
      background: transparent;
      color: #ef4444;
      border: 1px solid rgba(239, 68, 68, 0.35);
      border-radius: 6px;
      padding: 3px 10px;
      font-size: 0.72rem;
      cursor: pointer;
      font-weight: 600;
      transition: 0.15s;
    }
    .btn-slot-del:hover {
      background: rgba(239, 68, 68, 0.15);
      border-color: #ef4444;
    }
    .photo-slots-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
    }
    .slot-card {
      position: relative;
      height: 78px;
      background: #18202d;
      border: 1.5px dashed #334155;
      border-radius: 8px;
      cursor: pointer;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      transition: all 0.2s ease;
      user-select: none;
    }
    .slot-card:hover {
      border-color: #38bdf8;
      background: #1e293b;
    }
    .slot-card.active {
      border: 2px solid #38bdf8;
      box-shadow: 0 0 12px rgba(56, 189, 248, 0.4);
      background: #0d243a;
    }
    .slot-card img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }
    .slot-badge-tag {
      position: absolute;
      top: 4px;
      left: 4px;
      background: rgba(15, 23, 42, 0.85);
      color: #cbd5e1;
      font-size: 0.65rem;
      font-weight: 700;
      padding: 1px 6px;
      border-radius: 4px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      z-index: 2;
    }
    .slot-card.active .slot-badge-tag {
      background: #0284c7;
      color: #ffffff;
      border-color: #38bdf8;
    }
    .slot-empty-body {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: #64748b;
      font-size: 0.76rem;
      font-weight: 700;
    }

    /* Prominent Objects Pop-up Panel */
    .prominent-objects-panel {
      margin-top: 12px;
      background: #0f172a;
      border: 1px solid #233147;
      border-radius: 12px;
      padding: 12px 14px;
    }
    .prominent-objects-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
      flex-wrap: wrap;
      gap: 6px;
    }
    .prominent-title {
      font-size: 0.82rem;
      font-weight: 700;
      color: #38bdf8;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .prominent-sub {
      font-size: 0.72rem;
      color: #94a3b8;
    }
    .prominent-objects-list {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .prominent-chip {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 6px 12px;
      color: #e2e8f0;
      font-size: 0.76rem;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: all 0.15s ease;
    }
    .prominent-chip:hover {
      background: #273549;
      border-color: #38bdf8;
      color: #ffffff;
      transform: translateY(-1px);
    }
    .prominent-chip.chip-active {
      background: rgba(2, 132, 199, 0.25);
      border-color: #38bdf8;
      box-shadow: 0 0 8px rgba(56, 189, 248, 0.3);
    }
    .chip-badge {
      background: #0284c7;
      color: #ffffff;
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: 700;
      font-size: 0.68rem;
    }
    .chip-angles {
      font-family: monospace;
      font-size: 0.78rem;
    }
    .chip-angles b {
      color: #38bdf8;
    }
    .badge {
      display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: bold;
    }
    .badge-success { background-color: #064e3b; color: #34d399; border: 1px solid #059669; }
    .badge-info { background-color: #0c4a6e; color: #38bdf8; border: 1px solid #0284c7; }
    .badge-accent { background-color: #1e1b4b; color: #a5b4fc; border: 1px solid #4338ca; }

    /* Result visual layout */
    .visual-card { padding: 14px; margin-bottom: 14px; }
    .img-interactive-container {
      position: relative;
      background: #020617;
      border-radius: 8px;
      overflow: hidden;
      border: 1px solid #334155;
      touch-action: none;
      user-select: none;
      cursor: crosshair;
      min-height: 420px;
      max-height: 640px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .zoom-pan-viewport {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      transform-origin: center center;
      will-change: transform;
    }
    .result-img-interactive {
      max-width: 100%;
      max-height: 620px;
      height: auto;
      object-fit: contain;
      display: block;
      pointer-events: auto;
    }
    .btn-tool {
      background: #1e293b;
      color: #f1f5f9;
      border: 1px solid #475569;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s;
    }
    .btn-tool:hover {
      background: #334155;
    }
    .interactive-hint-badge {
      position: absolute;
      bottom: 8px;
      left: 50%;
      transform: translateX(-50%);
      background: rgba(15, 23, 42, 0.88);
      backdrop-filter: blur(6px);
      border: 1px solid #334155;
      padding: 4px 14px;
      border-radius: 20px;
      font-size: 0.72rem;
      color: #94a3b8;
      pointer-events: none;
      z-index: 5;
      white-space: nowrap;
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
      width: 100%;
      border-radius: 12px;
      overflow: hidden;
      background-color: #0b0f17;
      border: 2px solid #38bdf8;
      margin-bottom: 14px;
      box-shadow: 0 8px 30px rgba(0, 0, 0, 0.7);
    }
    .cam-viewport-box {
      position: relative;
      width: 100%;
      background: #000000;
      overflow: hidden;
      display: block;
    }
    #cameraVideo {
      width: 100%;
      height: 480px;
      display: block;
      object-fit: cover;
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
    .btn-fullscreen-cam {
      background: rgba(15, 23, 42, 0.85);
      color: #38bdf8;
      border: 1px solid #0284c7;
      border-radius: 20px;
      padding: 8px 14px;
      font-size: 0.8rem;
      font-weight: bold;
      cursor: pointer;
      transition: 0.15s;
    }
    .btn-fullscreen-cam:hover {
      background: #0284c7;
      color: #ffffff;
    }

    /* Indikator Status Sensor Minimalis di Sudut Kamera */
    .cam-sensor-badge {
      position: absolute;
      top: 10px;
      left: 12px;
      z-index: 25;
      background: rgba(15, 23, 42, 0.78);
      backdrop-filter: blur(6px);
      -webkit-backdrop-filter: blur(6px);
      border: 1px solid rgba(51, 65, 85, 0.8);
      border-radius: 20px;
      padding: 4px 10px;
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 0.72rem;
      font-weight: 700;
      color: #94a3b8;
      pointer-events: none;
    }
    .status-indicator-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #ef4444;
      display: inline-block;
    }
    .status-indicator-dot.active {
      background: #10b981;
      box-shadow: 0 0 8px #10b981;
      animation: pulse-dot 1.5s infinite;
    }
    @keyframes pulse-dot {
      0% { opacity: 0.7; transform: scale(0.95); }
      50% { opacity: 1; transform: scale(1.15); }
      100% { opacity: 0.7; transform: scale(0.95); }
    }

    /* Saat Kamera Live Aktif: Menyembunyikan Drop Area dan Memenuhi Layar Kiri */
    body.camera-live-active #dropArea,
    body.camera-live-active #rawPreview {
      display: none !important;
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
      /* Mode Kamera Live Aktif: Layar Kiri Diperluas Memenuhi Viewport */
      body.camera-live-active .dashboard-grid {
        grid-template-columns: 1.15fr 0.85fr;
      }
      body.camera-live-active #cameraVideo {
        height: 560px;
        max-height: calc(100vh - 220px);
        min-height: 480px;
      }
      .stats-grid {
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;
      }
      .grid-4 {
        grid-template-columns: 1fr 1fr;
      }
      .result-img-interactive {
        max-height: 580px;
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
            <button type="button" class="btn btn-secondary btn-sm" onclick="stopLiveCamera(); document.getElementById('galleryInput').click()">
              📁 Buka File / Foto Ufuk
            </button>
            <button type="button" class="btn btn-primary btn-sm" onclick="startLiveCamera()">
              📹 Kamera / Webcam Laptop
            </button>
          </div>

          <input type="file" id="galleryInput" accept="image/*" multiple style="display: none;" onchange="onFileSelected(this)">

          <div id="liveCamWrapper">
            <!-- Pilihan Sumber Perangkat Kamera (Muncul saat kamera aktif seperti semula) -->
            <div style="background: rgba(15, 23, 42, 0.95); padding: 8px 12px; display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; border-bottom: 1px solid #334155;">
              <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
                <span style="font-size: 0.78rem; color: #38bdf8; font-weight: bold;">📹 Sumber:</span>
                <select id="cameraSourceSelect" onchange="onCameraDeviceSelected(this.value)" style="width: auto; max-width: 250px; padding: 4px 8px; font-size: 0.75rem; background: #1a2436; border: 1px solid #334155; border-radius: 6px; color: #ffffff;">
                  <option value="">Deteksi Kamera...</option>
                </select>
                <button type="button" id="btnRefreshCam" onclick="refreshCameraDevices()" title="Cari ulang kamera USB yang baru dicolokkan" style="background: #0284c7; border: 1px solid #38bdf8; border-radius: 5px; color: #ffffff; padding: 3px 8px; font-size: 0.74rem; cursor: pointer; display: inline-flex; align-items: center; gap: 3px; font-weight: 600;">
                  🔄 Segarkan
                </button>
              </div>
              <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                <button type="button" onclick="toggleDigicamGuide()" style="background: none; border: none; color: #fbbf24; font-size: 0.74rem; cursor: pointer; text-decoration: underline; font-weight: 600;">
                  📷 Petunjuk Pocket
                </button>
                <button type="button" onclick="toggleHpCameraGuide()" style="background: none; border: none; color: #38bdf8; font-size: 0.74rem; cursor: pointer; text-decoration: underline;">
                  📲 Cara Hubungkan Kamera HP
                </button>
              </div>
            </div>

            <!-- Petunjuk Kamera Digicam / Pocket -->
            <div id="digicamGuide" style="display: none; background: #172554; padding: 10px 14px; border-bottom: 1px solid #3b82f6; font-size: 0.75rem; color: #e2e8f0; line-height: 1.5;">
              <b style="color: #fbbf24; display: block; margin-bottom: 4px;">📷 Cara Menghubungkan Kamera Saku / Digicam USB:</b>
              <p>Jika layar kamera menampilkan tulisan <b>"Penyimpanan Massal"</b>, kamera saat ini masih berfungsi sebagai <i>Flashdisk</i> (akses SD card), bukan Webcam. Agar muncul di pilihan sumber:</p>
              <ul style="margin: 4px 0 6px 18px; padding: 0;">
                <li><b>Opsi 1 (Colok Ulang):</b> Cabut kabel USB dan colok kembali. Saat layar kamera menyala, gunakan tombol <b>Panah Bawah / Atas</b> di kamera untuk memilih <b>"Kamera PC" (PC Camera)</b>, lalu tekan <b>OK</b>.</li>
                <li><b>Opsi 2 (Tombol Kamera):</b> Saat layar kamera bertuliskan "Penyimpanan Massal", coba tekan 1x tombol <b>Power</b>, tombol <b>Mode</b>, atau tombol <b>Shutter</b> pada kamera untuk berganti ke mode Webcam.</li>
                <li><b>Opsi 3 (Menu Kamera):</b> Cabut kabel USB, nyalakan kamera, buka <b>Menu &gt; Pengaturan (Setup) &gt; Mode USB</b>, ubah ke <b>"Kamera PC"</b>, lalu colokkan kembali kabel USB ke laptop.</li>
              </ul>
              <p style="color: #38bdf8; margin-top: 4px;">Setelah mode kamera beralih ke Kamera PC, klik tombol <b>🔄 Segarkan</b> di atas. Kamera akan otomatis muncul sebagai <b>GENERAL-A-VIDEO / Kamera Saku USB</b>.</p>
            </div>

            <!-- Petunjuk Cepat Hubungkan HP -->
            <div id="hpCamGuide" style="display: none; background: #0f172a; padding: 10px 14px; border-bottom: 1px solid #233147; font-size: 0.75rem; color: #cbd5e1; line-height: 1.5;">
              <b style="color: #38bdf8; display: block; margin-bottom: 4px;">📲 Hubungkan Kamera HP ke Laptop (Webcam Sementara):</b>
              <p>1. Unduh aplikasi <b>Iriun Webcam</b> atau <b>DroidCam</b> di HP & Laptop Anda.</p>
              <p>2. Sambungkan HP ke Laptop via Wi-Fi yang sama atau kabel USB.</p>
              <p>3. Kamera HP otomatis terdeteksi pada pilihan <b>Sumber</b> di atas!</p>
              <p style="color: #64748b; margin-top: 4px;"><i>Nanti saat sudah memiliki alat teleskop / USB eyepiece camera khusus, cukup colok kabel USB ke laptop dan pilih dari dropdown yang sama.</i></p>
            </div>

            <!-- Banner Peringatan jika Digicam masih dalam mode Penyimpanan Massal -->
            <div id="digicamNotice" style="display: none; background: #7c2d12; border: 1px solid #ea580c; border-radius: 8px; padding: 10px 14px; margin: 8px 12px; font-size: 0.76rem; color: #ffedd5; line-height: 1.45;">
              ⚠️ <b style="color: #fef08a;">Kamera Saku Terdeteksi dalam Mode "Penyimpanan Massal":</b><br>
              Kamera tercolok sebagai kartu memori/flashdisk (bukan webcam). Silakan ubah ke mode <b>"Kamera PC"</b> pada kamera (cabut-colok lalu pilih Kamera PC, atau tekan tombol Power/Mode/Shutter di kamera), lalu klik tombol <b>🔄 Segarkan</b>.
            </div>

            <!-- Frame Viewport Kamera Mandiri (Overlay Canvas Terkunci di Dalam Frame Video) -->
            <div id="liveSensorBanner" style="padding: 7px 12px; margin-bottom: 8px; border-radius: 8px; font-size: 0.78rem; display: flex; align-items: center; justify-content: space-between; background: #1e293b; border: 1px solid #334155; color: #94a3b8;">
              <span id="sensorBannerText">🧭 Memeriksa koneksi sensor hardware...</span>
              <span id="sensorBannerCalib" style="font-size: 0.72rem; color: #64748b;"></span>
            </div>

            <!-- Toolbar Kontrol Lensa & Video Kamera Live (Zoom In/Out, Kecerahan, Kontras) -->
            <div style="background: rgba(15, 23, 42, 0.95); padding: 8px 12px; margin-bottom: 10px; border-radius: 8px; border: 1px solid #334155; display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; font-size: 0.75rem;">
              <div style="display: flex; align-items: center; gap: 6px;">
                <span style="color: #38bdf8; font-weight: bold;">🔍 Zoom:</span>
                <button type="button" onclick="stepLiveCamZoom(-0.2)" title="Perkecil Zoom" style="background: #1e293b; border: 1px solid #475569; color: #fff; border-radius: 5px; padding: 2px 8px; cursor: pointer; font-weight: bold; font-size: 0.8rem;">➖</button>
                <input type="range" id="camZoomSlider" min="1.0" max="4.0" step="0.1" value="1.0" oninput="setLiveCamZoom(this.value)" style="width: 85px; accent-color: #38bdf8; cursor: pointer;">
                <button type="button" onclick="stepLiveCamZoom(0.2)" title="Perbesar Zoom" style="background: #1e293b; border: 1px solid #475569; color: #fff; border-radius: 5px; padding: 2px 8px; cursor: pointer; font-weight: bold; font-size: 0.8rem;">➕</button>
                <b id="lblLiveZoomVal" style="color: #38bdf8; font-family: monospace; min-width: 35px;">1.0x</b>
              </div>

              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <div style="display: flex; align-items: center; gap: 4px;">
                  <span style="color: #e2e8f0;">☀️ Terang:</span>
                  <input type="range" id="camBrightnessSlider" min="60" max="160" step="5" value="100" oninput="setLiveCamBrightness(this.value)" style="width: 70px; accent-color: #facc15; cursor: pointer;" title="Atur kecerahan video">
                </div>
                <div style="display: flex; align-items: center; gap: 4px;">
                  <span style="color: #e2e8f0;">🌓 Kontras:</span>
                  <input type="range" id="camContrastSlider" min="60" max="160" step="5" value="100" oninput="setLiveCamContrast(this.value)" style="width: 70px; accent-color: #38bdf8; cursor: pointer;" title="Atur kontras video">
                </div>
                <button type="button" onclick="resetLiveCamFilters()" style="background: #1e293b; border: 1px solid #475569; color: #94a3b8; border-radius: 5px; padding: 2px 8px; cursor: pointer; font-size: 0.72rem;" title="Kembalikan Zoom & Pengaturan Video ke Normal">↺ Normal</button>
              </div>
            </div>

            <div class="cam-viewport-box">
              <video id="cameraVideo" playsinline autoplay muted></video>
              <canvas id="cameraOverlay"></canvas>

              <div class="cam-controls">
                <button type="button" class="btn-shutter" onclick="captureLiveFrame()" title="Ambil frame foto atau tekan Spasi di keyboard">
                  📸 AMBIL FRAME (SPASI)
                </button>
                <button type="button" class="btn-zero-tilt" onclick="zeroCurrentTilt()" title="Nolkan kemiringan kamera saat ini sebagai 0.0° Level" style="background: #0f766e; border: 1px solid #14b8a6; color: #ffffff; padding: 6px 12px; font-size: 0.78rem; border-radius: 6px; cursor: pointer; font-weight: bold; display: inline-flex; align-items: center; gap: 4px;">
                  🎯 Nolkan Tilt (0.0°)
                </button>
                <button type="button" class="btn-fullscreen-cam" onclick="toggleCameraFullscreen()">
                  ⛶ Layar Penuh
                </button>
                <button type="button" class="btn-close-cam" onclick="stopLiveCamera()">
                  ✖️ Tutup Kamera
                </button>
              </div>
            </div>
          </div>

          <div class="photo-area" id="dropArea" onclick="stopLiveCamera(); document.getElementById('galleryInput').click()" style="cursor: pointer;" title="Klik untuk membuka file atau seret file gambar ke sini (Bisa Drag & Drop / Ctrl+V Paste)">
            <p style="font-size: 1.8rem; margin-bottom: 4px;">🏞️</p>
            <p style="font-weight: 700; color: #38bdf8; font-size: 0.88rem;" id="lblPhotoStatus">Belum ada foto yang dipilih</p>
            <p style="font-size: 0.74rem; color: #64748b; margin-top: 3px;">Klik 'Buka File', klik area ini, atau Drag & Drop / Paste foto</p>
          </div>

          <img id="rawPreview" class="preview-img" alt="Preview Foto Aktif" onclick="document.getElementById('galleryInput').click()" style="cursor: pointer;" title="Klik foto untuk mengganti gambar">

          <!-- PREVIEW 3 FOTO (SLOT FOTO & PILIHAN FOTO) -->
          <div class="photo-slots-wrapper">
            <div class="photo-slots-header">
              <span class="photo-slots-title">🖼️ Pilihan 3 Foto (Klik slot untuk memilih foto aktif):</span>
              <button type="button" class="btn-slot-del" onclick="deleteActivePhotoSlot()" title="Hapus foto pada slot terpilih">🗑️ Hapus Foto</button>
            </div>
            <div class="photo-slots-grid">
              <div class="slot-card active" id="slotCard0" onclick="selectPhotoSlot(0)">
                <span class="slot-badge-tag" id="slotBadge0">Slot 1</span>
                <div class="slot-empty-body" id="slotEmpty0">
                  <span>Slot 1</span>
                </div>
                <img id="slotImg0" style="display: none;" alt="Slot 1">
              </div>
              <div class="slot-card" id="slotCard1" onclick="selectPhotoSlot(1)">
                <span class="slot-badge-tag" id="slotBadge1">Slot 2</span>
                <div class="slot-empty-body" id="slotEmpty1">
                  <span>Slot 2</span>
                </div>
                <img id="slotImg1" style="display: none;" alt="Slot 2">
              </div>
              <div class="slot-card" id="slotCard2" onclick="selectPhotoSlot(2)">
                <span class="slot-badge-tag" id="slotBadge2">Slot 3</span>
                <div class="slot-empty-body" id="slotEmpty2">
                  <span>Slot 3</span>
                </div>
                <img id="slotImg2" style="display: none;" alt="Slot 3">
              </div>
            </div>
          </div>
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
          <div id="compassLiveBadge" style="margin-bottom: 12px; padding: 6px 12px; background: #0f172a; border: 1px solid #334155; border-radius: 8px; font-size: 0.78rem; display: flex; align-items: center; justify-content: space-between;">
            <span id="compassStatusText" style="color: #94a3b8;">🧭 Kompas Hardware: Memeriksa COM7...</span>
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
          <input type="hidden" id="inpHfov" value="60.0">

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
          
          <!-- CITRA HASIL KONTUR UFUK MAR'I INTERAKTIF (FULL WIDTH) -->
          <div class="card visual-card">
            <div class="card-title" style="flex-wrap: wrap; gap: 8px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span>⛰️ 3. Citra Hasil Kontur Ufuk Mar'i</span>
                <span id="resBadge" class="badge badge-success">Analisis Selesai</span>
              </div>
              <div style="display: flex; align-items: center; gap: 6px;">
                <button type="button" class="btn-tool" onclick="zoomInImg()" title="Perbesar (Zoom In)">🔍 +</button>
                <button type="button" class="btn-tool" onclick="zoomOutImg()" title="Perkecil (Zoom Out)">🔍 -</button>
                <button type="button" class="btn-tool" onclick="resetImgZoom()" title="Kembali ke 100%">↺ 100%</button>
                <span id="zoomLevelBadge" class="badge badge-info" style="font-size: 0.72rem;">100%</span>
              </div>
            </div>
            <div class="img-interactive-container" id="imgInteractiveContainer">
              <div class="zoom-pan-viewport" id="zoomPanViewport">
                <img id="resOverlayImg" class="result-img-interactive" alt="Hasil Kontur Ufuk Mar'i" draggable="false">
              </div>
              <div class="interactive-hint-badge">
                <span>👆 Sentuh/Geser Titik Azimut di Gambar &bull; 🤏 2 Jari / Scroll untuk Zoom & Pan</span>
              </div>
            </div>

            <!-- POP UP / CHIPS OBJEK MENONJOL (ANGKA DERAJAT HORIZONTAL & VERTIKAL) -->
            <div id="prominentObjectsContainer" class="prominent-objects-panel" style="display: none;">
              <div class="prominent-objects-header">
                <span class="prominent-title">📍 Objek Menonjol Terdeteksi (Pop-up Derajat Horisontal &amp; Vertikal):</span>
                <span class="prominent-sub">Klik objek untuk bidik langsung</span>
              </div>
              <div id="prominentObjectsList" class="prominent-objects-list"></div>
            </div>
          </div>

          <!-- KURVA PROFIL ELEVASI VS AZIMUTH (DENGAN SLIDER ATUR SASARAN LANGSUNG DI DALAM FRAME) -->
          <div class="card visual-card" style="margin-bottom: 14px;">
            <div class="card-title">
              <span>📈 4. Kurva Profil Elevasi vs Azimuth</span>
              <span style="font-size: 0.78rem; color: #38bdf8; font-weight: normal;">🎯 Klik garis merah / grafik untuk atur sasaran</span>
            </div>
            <div class="img-wrapper" id="plotInteractiveWrapper" style="position: relative; background: #020617; border-radius: 8px; overflow: hidden; border: 1px solid #334155; text-align: center; cursor: crosshair;" title="Klik atau seret pada garis merah grafik untuk membidik azimut sasaran">
              <img id="resPlotImg" style="width: 100%; max-height: 400px; object-fit: contain; display: block; user-select: none;" alt="Grafik Profil Elevasi vs Azimuth" draggable="false">
            </div>

            <div class="slider-container" style="margin-top: 12px; padding: 10px 14px; background: #0f172a; border: 1px solid #1e293b; border-radius: 8px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <label style="margin: 0; font-size: 0.82rem; color: #cbd5e1; font-weight: 600;">Titik Azimut Sasaran:</label>
                <b id="lblSliderAz" style="color: #38bdf8; font-size: 1.05rem; background: #020617; padding: 2px 10px; border-radius: 6px; border: 1px solid #334155;">270.00°</b>
              </div>
              <input type="range" id="sliderAz" min="240.0" max="300.0" step="0.05" value="270.0" oninput="onSliderTargetChanged(this.value)">
              <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: #64748b; margin-top: 4px;">
                <span id="lblMinAz">240.0°</span>
                <span>Tengah (Barat)</span>
                <span id="lblMaxAz">300.0°</span>
              </div>
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
                  📊 Buka Tabel & Ekspor Data (Excel / CSV)
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
        <button type="button" class="doc-btn" style="background: #10b981; color: #fff; font-weight: bold;" onclick="downloadExcel()">📊 Unduh Excel (.xlsx)</button>
        <button type="button" class="doc-btn" style="background: #0284c7; color: #fff;" onclick="downloadCsv()">📥 Unduh CSV</button>
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
              <th style="padding: 10px 12px; font-weight: bold; border-right: 1px solid #1e293b; width: 60px; text-align: center;">No</th>
              <th style="padding: 10px 12px; font-weight: bold; border-right: 1px solid #1e293b; text-align: center;">Azimut (°)</th>
              <th style="padding: 10px 12px; font-weight: bold; border-right: 1px solid #1e293b; text-align: center;">Elevasi / cm</th>
              <th style="padding: 10px 12px; font-weight: bold; text-align: center;">Data Lokasi</th>
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
    let liveCompassConnected = false;
    let liveCompassAzimuth = 270.0;
    let liveCompassTilt = 0.0;
    let liveCompassStatus = "";
    let liveCompassPort = "";
    let liveCompassMag = 0;
    let liveCompassGyro = 0;

    // Tabel kalibrasi presisi derajat ke sentimeter (cm) sesuai acuan pengukuran optik falak jarak 30cm:
    // 1°/0,52cm, 2°/1,04cm, 3°/1,57cm, 4°/2,09cm, 5°/2,62cm, 10°/5,28cm, 15°/8,03cm, 20°/10,91cm
    const CALIB_DEG_CM = {
      1: "0,52", 2: "1,04", 3: "1,57", 4: "2,09", 5: "2,62",
      6: "3,15", 7: "3,68", 8: "4,21", 9: "4,75", 10: "5,28",
      11: "5,83", 12: "6,37", 13: "6,92", 14: "7,47", 15: "8,03",
      16: "8,60", 17: "9,17", 18: "9,74", 19: "10,32", 20: "10,91"
    };

    function getElevCmStr(d) {
      const a = Math.abs(d);
      if (a < 0.001) return "0,00";
      const intA = Math.round(a);
      if (Math.abs(a - intA) < 0.05 && CALIB_DEG_CM[intA]) {
        return CALIB_DEG_CM[intA];
      }
      // Rumus tangen jarak 30 cm: 30 * tan(theta)
      const cm = 30.0 * Math.tan((a * Math.PI) / 180.0);
      const floored = Math.floor(cm * 100) / 100;
      return floored.toFixed(2).replace('.', ',');
    }

    function getCardinalDirection(deg) {
      deg = ((deg % 360) + 360) % 360;
      if (deg >= 337.5 || deg < 22.5) return "UTARA";
      if (deg >= 22.5 && deg < 67.5) return "TIMUR LAUT";
      if (deg >= 67.5 && deg < 112.5) return "TIMUR";
      if (deg >= 112.5 && deg < 157.5) return "TENGGARA";
      if (deg >= 157.5 && deg < 202.5) return "SELATAN";
      if (deg >= 202.5 && deg < 247.5) return "BARAT DAYA";
      if (deg >= 247.5 && deg < 292.5) return "BARAT";
      return "BARAT LAUT";
    }

    async function pollCompassData() {
      try {
        const res = await fetch('/api/compass');
        if (!res.ok) return;
        const data = await res.json();
        const badge = document.getElementById('compassLiveBadge');
        const banner = document.getElementById('liveSensorBanner');
        const bannerText = document.getElementById('sensorBannerText');
        const bannerCalib = document.getElementById('sensorBannerCalib');

        liveCompassConnected = Boolean(data.connected);
        liveCompassStatus = data.status || "";
        liveCompassPort = data.port || "";
        liveCompassMag = data.cal_mag || 0;
        liveCompassGyro = data.cal_gyro || 0;

        if (data.connected) {
          liveCompassAzimuth = (data.azimuth !== undefined && data.azimuth !== null) ? Number(data.azimuth) : 270.0;
          liveCompassTilt = (data.tilt !== undefined && data.tilt !== null) ? Number(data.tilt) : 0.0;
          const azInp = document.getElementById('inpAzimuth');
          const tiltInp = document.getElementById('inpTilt');
          if (azInp && document.activeElement !== azInp) {
            azInp.value = liveCompassAzimuth.toFixed(1);
          }
          if (tiltInp && document.activeElement !== tiltInp) {
            tiltInp.value = liveCompassTilt.toFixed(1);
          }

          const isWest = Math.abs(liveCompassAzimuth - 270.0) <= 2.5;
          const cardName = getCardinalDirection(liveCompassAzimuth);

          if (banner) {
            banner.style.background = isWest ? 'rgba(6, 78, 59, 0.4)' : 'rgba(14, 116, 144, 0.25)';
            banner.style.borderColor = isWest ? '#10b981' : '#0284c7';
          }
          if (bannerText) {
            bannerText.innerHTML = `<b style="color:${isWest ? '#34d399' : '#38bdf8'}">🟢 ${data.port || 'COM'} TERHUBUNG:</b> ${liveCompassAzimuth.toFixed(1)}° (${cardName}) | Tilt ${liveCompassTilt > 0 ? '+' : ''}${liveCompassTilt.toFixed(1)}°`;
          }
          if (bannerCalib) {
            bannerCalib.innerHTML = `<span style="color:#facc15">Mag: ${data.cal_mag || 0}/3</span> | <span style="color:#38bdf8">Gyro: ${data.cal_gyro || 0}/3</span>`;
          }

          if (badge) {
            badge.style.borderColor = isWest ? '#10b981' : '#0284c7';
            badge.innerHTML = '<span style="color:' + (isWest ? '#10b981' : '#38bdf8') + '; font-weight: 700;">' +
              (isWest ? '🎯 TERKUNCI BARAT: ' : '🧭 ') + data.port + ': ' + liveCompassAzimuth.toFixed(1) + '° (' + cardName + ' | Tilt ' +
              (liveCompassTilt > 0 ? '+' : '') + liveCompassTilt.toFixed(1) + '°)</span>' +
              '<span style="color: #94a3b8; font-size: 0.72rem;">Mag: ' + (data.cal_mag || 0) + '/3 | Gyro: ' + (data.cal_gyro || 0) + '/3</span>';
          }
        } else {
          const isBusy = (data.status || '').includes('sibuk') || (data.status || '').includes('terkunci');
          if (banner) {
            banner.style.background = isBusy ? 'rgba(153, 27, 27, 0.35)' : 'rgba(30, 41, 59, 0.6)';
            banner.style.borderColor = isBusy ? '#ef4444' : '#475569';
          }
          if (bannerText) {
            bannerText.innerHTML = isBusy 
              ? `<b style="color:#f87171">⚠️ ${data.status}</b>` 
              : `<span style="color: #94a3b8;">⚠️ ${data.status || 'Sensor terputus'}</span>`;
          }
          if (bannerCalib) {
            bannerCalib.innerHTML = isBusy ? '<span style="color:#fca5a5; font-size: 0.72rem;">(Tutup window Serial Monitor)</span>' : '';
          }

          if (badge) {
            badge.style.borderColor = isBusy ? '#ef4444' : '#334155';
            badge.innerHTML = '<span style="color: ' + (isBusy ? '#f87171' : '#94a3b8') + ';">⚠️ ' + (data.status || 'Kompas tidak terdeteksi') + '</span>';
          }
        }
      } catch (err) {}
    }
    setInterval(pollCompassData, 200);

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

    // Pengelolaan 3 Slot Foto & Pilihan Foto
    let photoSlots = [null, null, null];
    let activeSlotIndex = 0;

    function updatePhotoSlotsUI() {
      for (let i = 0; i < 3; i++) {
        const card = document.getElementById('slotCard' + i);
        const img = document.getElementById('slotImg' + i);
        const empty = document.getElementById('slotEmpty' + i);
        const badge = document.getElementById('slotBadge' + i);
        if (!card) continue;

        if (i === activeSlotIndex) {
          card.classList.add('active');
        } else {
          card.classList.remove('active');
        }

        if (photoSlots[i] && photoSlots[i].b64) {
          img.src = photoSlots[i].b64;
          img.style.display = 'block';
          if (empty) empty.style.display = 'none';
          if (badge) badge.innerText = `Slot ${i + 1}`;
        } else {
          img.src = '';
          img.style.display = 'none';
          if (empty) empty.style.display = 'flex';
          if (badge) badge.innerText = `Slot ${i + 1} (Kosong)`;
        }
      }

      // Perbarui preview foto utama
      const preview = document.getElementById('rawPreview');
      const dropArea = document.getElementById('dropArea');
      const lblStatus = document.getElementById('lblPhotoStatus');
      const activeSlot = photoSlots[activeSlotIndex];

      if (activeSlot && activeSlot.b64) {
        selectedImageBase64 = activeSlot.b64;
        if (preview) {
          preview.src = activeSlot.b64;
          preview.style.display = 'block';
        }
        if (dropArea) {
          dropArea.style.display = 'none';
        }
      } else {
        selectedImageBase64 = null;
        if (preview) {
          preview.src = '';
          preview.style.display = 'none';
        }
        if (dropArea) {
          dropArea.style.display = 'block';
          dropArea.classList.remove('active');
        }
        if (lblStatus) {
          lblStatus.innerText = `Slot ${activeSlotIndex + 1} kosong - Silakan pilih / muat foto`;
          lblStatus.style.color = '#38bdf8';
        }
      }
    }

    function selectPhotoSlot(idx) {
      if (idx < 0 || idx >= 3) return;
      activeSlotIndex = idx;
      if (!photoSlots[idx] || !photoSlots[idx].b64) {
        // Jika slot masih kosong, langsung buka dialog pemilihan file untuk mengisi slot ini
        document.getElementById('galleryInput').click();
      } else {
        updatePhotoSlotsUI();
      }
    }

    function deleteActivePhotoSlot() {
      if (!photoSlots[activeSlotIndex]) {
        alert("Slot " + (activeSlotIndex + 1) + " memang masih kosong.");
        return;
      }
      photoSlots[activeSlotIndex] = null;
      // Otomatis pindah ke slot lain yang masih terisi jika ada
      let nextIdx = photoSlots.findIndex(s => s && s.b64);
      if (nextIdx !== -1) {
        activeSlotIndex = nextIdx;
      }
      updatePhotoSlotsUI();
    }

    function setPhotoToSlot(slotIdx, b64, statusText) {
      photoSlots[slotIdx] = {
        b64: b64,
        status: statusText || ("Foto Slot " + (slotIdx + 1))
      };
      activeSlotIndex = slotIdx;
      updatePhotoSlotsUI();
    }

    function displayLoadedImage(b64, statusText) {
      setPhotoToSlot(activeSlotIndex, b64, statusText);
      stopLiveCamera();
    }

    function compressAndSetImage(file, targetSlot, statusText) {
      const reader = new FileReader();
      reader.onload = function(e) {
        const dataUrl = e.target.result;
        setPhotoToSlot(targetSlot, dataUrl, statusText);

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
            const compressed = canvas.toDataURL('image/jpeg', 0.86);
            if (photoSlots[targetSlot]) {
              photoSlots[targetSlot].b64 = compressed;
              if (activeSlotIndex === targetSlot) {
                selectedImageBase64 = compressed;
                const prev = document.getElementById('rawPreview');
                if (prev) prev.src = compressed;
              }
              const slotImg = document.getElementById('slotImg' + targetSlot);
              if (slotImg) slotImg.src = compressed;
            }
          }
        };
        img.src = dataUrl;
      };
      reader.readAsDataURL(file);
    }

    function onFileSelected(input) {
      if (input.files && input.files.length > 0) {
        const files = Array.from(input.files).slice(0, 3);
        const sourceName = input.id === 'galleryInput' ? 'Penyimpanan Berkas' : 'Kamera / Webcam';

        files.forEach((file, fIdx) => {
          let slotTarget = activeSlotIndex;
          if (fIdx > 0) {
            const emptyIdx = photoSlots.findIndex((s, idx) => (!s || !s.b64) && idx !== activeSlotIndex);
            if (emptyIdx !== -1) {
              slotTarget = emptyIdx;
            } else {
              slotTarget = (activeSlotIndex + fIdx) % 3;
            }
          }
          compressAndSetImage(file, slotTarget, file.name || ("Foto " + sourceName));
        });
        input.value = "";
        stopLiveCamera();
      }
    }

    function loadSamplePhoto() {
      fetch('/api/sample_image')
        .then(res => res.json())
        .then(data => {
          setPhotoToSlot(activeSlotIndex, data.image_base64, "Foto contoh lanskap ufuk terpasang");
        })
        .catch(err => {
          alert("Gagal memuat contoh foto: " + err.message);
        });
    }

    // Render pop up chips objek menonjol (angka derajat horizontal dan vertikal)
    function renderProminentObjects(objects) {
      const container = document.getElementById('prominentObjectsContainer');
      const list = document.getElementById('prominentObjectsList');
      if (!container || !list) return;

      if (!objects || objects.length === 0) {
        container.style.display = 'none';
        list.innerHTML = '';
        return;
      }

      container.style.display = 'block';
      list.innerHTML = '';
      objects.forEach(obj => {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'prominent-chip';
        chip.dataset.az = obj.azimuth.toFixed(2);
        chip.title = `Bidik langsung ${obj.label}: Azimut ${obj.azimuth.toFixed(2)}°, Elevasi ${obj.elevation >= 0 ? '+' : ''}${obj.elevation.toFixed(2)}°`;
        chip.innerHTML = `
          <span class="chip-badge">${obj.label}</span>
          <span class="chip-angles">H (Az): <b>${obj.azimuth.toFixed(2)}°</b> | V (Alt): <b>${(obj.elevation >= 0 ? '+' : '') + obj.elevation.toFixed(2)}°</b></span>
        `;
        chip.onclick = function() {
          jumpToAzimuth(obj.azimuth);
        };
        list.appendChild(chip);
      });
    }

    function jumpToAzimuth(azVal) {
      const slider = document.getElementById('sliderAz');
      if (slider) {
        slider.value = azVal.toFixed(2);
      }
      onSliderTargetChanged(azVal);
      // Tandai visual chip yang aktif
      document.querySelectorAll('.prominent-chip').forEach(btn => {
        if (Math.abs(parseFloat(btn.dataset.az) - azVal) < 0.15) {
          btn.classList.add('chip-active');
        } else {
          btn.classList.remove('chip-active');
        }
      });
    }

    let currentCameraDeviceId = null;

    function toggleHpCameraGuide() {
      const guide = document.getElementById('hpCamGuide');
      if (guide) {
        guide.style.display = guide.style.display === 'none' ? 'block' : 'none';
      }
    }

    function toggleDigicamGuide() {
      const guide = document.getElementById('digicamGuide');
      if (guide) {
        guide.style.display = guide.style.display === 'none' ? 'block' : 'none';
      }
    }

    async function checkCameraHardwareStatus() {
      try {
        const res = await fetch('/api/check_cameras');
        if (!res.ok) return;
        const data = await res.json();
        const notice = document.getElementById('digicamNotice');
        if (notice) {
          if (data.digicam_state === 'storage_mode') {
            notice.style.display = 'block';
          } else {
            notice.style.display = 'none';
          }
        }
      } catch (e) {
        console.warn("Gagal cek status hardware kamera:", e);
      }
    }

    async function refreshCameraDevices() {
      const btn = document.getElementById('btnRefreshCam');
      if (btn) {
        btn.innerHTML = '⏳ Memindai...';
        btn.disabled = true;
      }
      try {
        await checkCameraHardwareStatus();
        await updateCameraDeviceList();
      } catch (err) {
        console.warn("Refresh kamera error:", err);
      } finally {
        if (btn) {
          btn.innerHTML = '🔄 Segarkan';
          btn.disabled = false;
        }
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
        let autoPickIdx = -1;

        videoDevices.forEach((dev, idx) => {
          const opt = document.createElement('option');
          opt.value = dev.deviceId;
          let label = dev.label || `Kamera ${idx + 1}`;

          const isGeneral = /general-a-video|general|1b3f|genplus/i.test(label);
          const isLogi = /logi|c270|c920|c922|brio/i.test(label);
          const isIriun = /iriun/i.test(label);
          const isDroid = /droid/i.test(label);
          const isCamo = /camo|epoc/i.test(label);
          const isInternal = /1bcf:28c4|integrated|built-in|pc camera/i.test(label);
          const isUsb = /usb/i.test(label);

          if (isGeneral) {
            label = "📷 " + label + " (Kamera Saku / Digicam USB)";
            if (autoPickIdx === -1) autoPickIdx = idx;
          } else if (isLogi) {
            label = "🎥 " + label + " (Logitech Eksternal HD)";
            if (autoPickIdx === -1) autoPickIdx = idx;
          } else if (isUsb && !isInternal) {
            label = "🔭 " + label + " (USB Eksternal / Teleskop)";
            if (autoPickIdx === -1) autoPickIdx = idx;
          } else if (isIriun || isDroid || isCamo) {
            label = "📱 " + label + " (Kamera HP)";
          } else if (isInternal) {
            label = "💻 " + label + " (Webcam Laptop)";
          }

          opt.text = label;
          if (currentCameraDeviceId && dev.deviceId === currentCameraDeviceId) {
            opt.selected = true;
          }
          sel.appendChild(opt);
        });

        // Otomatis prioritaskan Digicam/USB eksternal jika pengguna belum memilih kamera tertentu
        if (!currentCameraDeviceId && autoPickIdx !== -1) {
          sel.selectedIndex = autoPickIdx;
          currentCameraDeviceId = videoDevices[autoPickIdx].deviceId;
        }
      } catch (e) {
        console.warn("Gagal membaca daftar kamera:", e);
      }
    }

    if (navigator.mediaDevices && typeof navigator.mediaDevices.addEventListener === 'function') {
      navigator.mediaDevices.addEventListener('devicechange', async () => {
        await checkCameraHardwareStatus();
        await updateCameraDeviceList();
      });
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
      document.body.classList.add('camera-live-active');
      checkCameraHardwareStatus();

      // Hentikan stream yang sedang berjalan terlebih dahulu
      if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
      }

      try {
        let targetId = preferredDeviceId || currentCameraDeviceId;
        if (!targetId && navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
          try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            const videoDevices = devices.filter(d => d.kind === 'videoinput');
            const extCam = videoDevices.find(d => 
              /general|genplus|1b3f|logi|c270|c920|c922|brio|teleskop|eyepiece|usb/i.test(d.label) &&
              !/1bcf:28c4|integrated|built-in/i.test(d.label)
            );
            if (extCam && extCam.deviceId) {
              targetId = extCam.deviceId;
              currentCameraDeviceId = targetId;
            }
          } catch (e) {}
        }

        let constraints;
        if (targetId) {
          constraints = {
            video: {
              deviceId: { exact: targetId },
              width: { ideal: 1280 },
              height: { ideal: 720 }
            },
            audio: false
          };
        } else {
          constraints = {
            video: {
              width: { ideal: 1280 },
              height: { ideal: 720 },
              facingMode: { ideal: "environment" }
            },
            audio: false
          };
        }

        try {
          cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
        } catch (strictErr) {
          console.warn("Kamera gagal dengan constraint ideal, mencoba konfigurasi fleksibel:", strictErr);
          try {
            cameraStream = await navigator.mediaDevices.getUserMedia({
              video: targetId ? { deviceId: { ideal: targetId } } : true,
              audio: false
            });
          } catch (looseErr) {
            console.warn("Mencoba kamera default:", looseErr);
            cameraStream = await navigator.mediaDevices.getUserMedia({
              video: true,
              audio: false
            });
          }
        }

        try {
          const vTracks = cameraStream.getVideoTracks();
          if (vTracks && vTracks.length > 0 && vTracks[0].getSettings) {
            const settings = vTracks[0].getSettings();
            if (settings.deviceId) {
              currentCameraDeviceId = settings.deviceId;
            }
          }
        } catch (e) {}

        video.srcObject = cameraStream;
        await updateCameraDeviceList();

        video.onloadedmetadata = () => {
          video.play().catch(e => console.warn(e));
          applyLiveCamFilters();
          drawLiveHudLoop();
          updateCameraDeviceList();
          checkCameraHardwareStatus();
        };
      } catch (err) {
        alert("Tidak dapat membuka kamera: " + err.message + ". Pastikan izin kamera browser diaktifkan atau kamera tidak sedang dipakai aplikasi lain.");
        wrapper.style.display = 'none';
        document.body.classList.remove('camera-live-active');
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
      document.body.classList.remove('camera-live-active');
    }

    function toggleCameraFullscreen() {
      const wrapper = document.getElementById('liveCamWrapper');
      if (!wrapper) return;
      if (!document.fullscreenElement) {
        if (wrapper.requestFullscreen) {
          wrapper.requestFullscreen().catch(err => console.warn(err));
        } else if (wrapper.webkitRequestFullscreen) {
          wrapper.webkitRequestFullscreen();
        }
      } else {
        if (document.exitFullscreen) {
          document.exitFullscreen().catch(err => console.warn(err));
        }
      }
    }

    // Pengaturan Zoom, Kecerahan, dan Kontras Kamera Live
    let camLiveZoom = 1.0;
    let camLiveBrightness = 100;
    let camLiveContrast = 100;

    function applyLiveCamFilters() {
      const video = document.getElementById('cameraVideo');
      if (video) {
        video.style.transform = `scale(${camLiveZoom})`;
        video.style.transformOrigin = 'center center';
        video.style.filter = `brightness(${camLiveBrightness}%) contrast(${camLiveContrast}%)`;
      }
    }

    async function setLiveCamZoom(val) {
      camLiveZoom = parseFloat(val);
      const lbl = document.getElementById('lblLiveZoomVal');
      if (lbl) lbl.innerText = camLiveZoom.toFixed(1) + 'x';
      const slider = document.getElementById('camZoomSlider');
      if (slider && Math.abs(parseFloat(slider.value) - camLiveZoom) > 0.05) slider.value = camLiveZoom.toFixed(1);
      applyLiveCamFilters();

      // Kirim PTZ Hardware Zoom ke driver UVC jika didukung perangkat
      try {
        if (cameraStream) {
          const track = cameraStream.getVideoTracks()[0];
          if (track && track.getCapabilities) {
            const caps = track.getCapabilities();
            if (caps.zoom) {
              const clamped = Math.min(caps.zoom.max, Math.max(caps.zoom.min, camLiveZoom));
              await track.applyConstraints({ advanced: [{ zoom: clamped }] });
            }
          }
        }
      } catch (e) {}
    }

    function stepLiveCamZoom(delta) {
      let next = Math.max(1.0, Math.min(4.0, Math.round((camLiveZoom + delta) * 10) / 10));
      setLiveCamZoom(next);
    }

    function setLiveCamBrightness(val) {
      camLiveBrightness = parseInt(val);
      applyLiveCamFilters();
    }

    function setLiveCamContrast(val) {
      camLiveContrast = parseInt(val);
      applyLiveCamFilters();
    }

    function resetLiveCamFilters() {
      camLiveZoom = 1.0;
      camLiveBrightness = 100;
      camLiveContrast = 100;
      const sZoom = document.getElementById('camZoomSlider');
      if (sZoom) sZoom.value = "1.0";
      const sB = document.getElementById('camBrightnessSlider');
      if (sB) sB.value = "100";
      const sC = document.getElementById('camContrastSlider');
      if (sC) sC.value = "100";
      const lbl = document.getElementById('lblLiveZoomVal');
      if (lbl) lbl.innerText = "1.0x";
      applyLiveCamFilters();
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

          const scale = Math.max(1, w / 960);
          const cx = w / 2.0;

          const tapeY = 10 * scale;
          const tapeH = 34 * scale;
          const vBarTop = tapeY + tapeH + (32 * scale);
          const vBarBot = h - (36 * scale);
          const vBarH = vBarBot - vBarTop;
          const vFovDeg = 47.0; // Kalibrasi rentang pandang vertikal (interval 20° pas dengan kaca atas & bawah)
          const pxPerDegV = vBarH / vFovDeg;

          // Titik acuan level 0° dan crosshair tengah disesuaikan presisi (+0.9° / pxPerDegV, diturunkan 0.1° dari sebelumnya) agar pas di tengah garis hitam
          const cy = (h / 2.0) + (h * 0.0516) - (0.9 * pxPerDegV);

          const curAz = liveCompassConnected ? liveCompassAzimuth : (parseFloat(document.getElementById('inpAzimuth').value) || 270.0);
          const curTilt = liveCompassConnected ? liveCompassTilt : (parseFloat(document.getElementById('inpTilt').value) || 0.0);
          const isWestLocked = Math.abs(curAz - 270.0) <= 2.5;
          const isLevel = Math.abs(curTilt) <= 0.8;

          // ==========================================================
          // 1. KOMPAS HORIZONTAL ARAH MATA ANGIN (Rentang 240° s.d. 300°)
          // ==========================================================
          const visibleFov = 64; // Menampilkan rentang derajat dari 240° (kiri) hingga 300° (kanan) saat bidik 270°
          const tapeW = Math.min(w * 0.72, 640 * scale); // Garis proporsional, rapi di tengah dan tidak penuh layar
          const tapeX = cx - (tapeW / 2); // Titik awal dihitung agar simetris di tengah

          ctx.save();
          // Baseline garis kompas horizontal sepanjang tapeW
          ctx.strokeStyle = "rgba(255, 255, 255, 0.28)";
          ctx.lineWidth = 1 * scale;
          ctx.beginPath();
          ctx.moveTo(tapeX, tapeY + tapeH);
          ctx.lineTo(tapeX + tapeW, tapeY + tapeH);
          ctx.stroke();

          // Skala derajat dihitung sesuai rentang FOV
          const pxPerDeg = tapeW / visibleFov;
          const startDeg = Math.floor(curAz - (visibleFov / 2) - 2);
          const endDeg = Math.ceil(curAz + (visibleFov / 2) + 2);

          for (let d = startDeg; d <= endDeg; d++) {
            const xPos = cx + (d - curAz) * pxPerDeg;
            // Batasi agar angka dan garis derajat tidak digambar di luar pita
            if (xPos < tapeX || xPos > tapeX + tapeW) continue;


            const normDeg = ((d % 360) + 360) % 360;

            if (normDeg % 45 === 0) {
              // Arah Mata Angin Utama (N, NE, E, SE, S, SW, W, NW)
              let card = "";
              if (normDeg === 0) card = "U";
              else if (normDeg === 45) card = "TL";
              else if (normDeg === 90) card = "T";
              else if (normDeg === 135) card = "TG";
              else if (normDeg === 180) card = "S";
              else if (normDeg === 225) card = "BD";
              else if (normDeg === 270) card = "B";
              else if (normDeg === 315) card = "BL";

              const isTargetWest = normDeg === 270;
              ctx.strokeStyle = isTargetWest ? "#10b981" : "#38bdf8";
              ctx.lineWidth = isTargetWest ? 2.5 * scale : 1.8 * scale;
              ctx.beginPath();
              ctx.moveTo(xPos, tapeY + tapeH);
              ctx.lineTo(xPos, tapeY + tapeH - (18 * scale));
              ctx.stroke();

              ctx.fillStyle = isTargetWest ? "#34d399" : "#38bdf8";
              ctx.font = `bold ${Math.round((isTargetWest ? 13 : 11) * scale)}px sans-serif`;
              ctx.textAlign = "center";
              ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
              ctx.shadowBlur = 4;
              ctx.fillText(isTargetWest ? "270° B" : card, xPos, tapeY + tapeH - (20 * scale));
              ctx.shadowBlur = 0;
            } else if (normDeg % 15 === 0) {
              // Angka derajat setiap 15°
              ctx.strokeStyle = "rgba(226, 232, 240, 0.85)";
              ctx.lineWidth = 1.2 * scale;
              ctx.beginPath();
              ctx.moveTo(xPos, tapeY + tapeH);
              ctx.lineTo(xPos, tapeY + tapeH - (12 * scale));
              ctx.stroke();

              ctx.fillStyle = "#cbd5e1";
              ctx.font = `bold ${Math.round(10 * scale)}px monospace`;
              ctx.textAlign = "center";
              ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
              ctx.shadowBlur = 3;
              ctx.fillText(String(normDeg), xPos, tapeY + tapeH - (14 * scale));
              ctx.shadowBlur = 0;
            } else if (normDeg % 5 === 0) {
              // Garis menengah setiap 5°
              ctx.strokeStyle = "rgba(255, 255, 255, 0.5)";
              ctx.lineWidth = 1 * scale;
              ctx.beginPath();
              ctx.moveTo(xPos, tapeY + tapeH);
              ctx.lineTo(xPos, tapeY + tapeH - (7 * scale));
              ctx.stroke();
            } else {
              // Garis mikro per 1°
              ctx.strokeStyle = "rgba(255, 255, 255, 0.2)";
              ctx.lineWidth = 0.8 * scale;
              ctx.beginPath();
              ctx.moveTo(xPos, tapeY + tapeH);
              ctx.lineTo(xPos, tapeY + tapeH - (3.5 * scale));
              ctx.stroke();
            }
          }
          ctx.restore();

          // Jarum penunjuk tengah kompas (Segitiga ▼)
          ctx.beginPath();
          ctx.moveTo(cx - (7 * scale), tapeY + (4 * scale));
          ctx.lineTo(cx + (7 * scale), tapeY + (4 * scale));
          ctx.lineTo(cx, tapeY + (14 * scale));
          ctx.closePath();
          ctx.fillStyle = isWestLocked ? "#10b981" : "#38bdf8";
          ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
          ctx.shadowBlur = 4;
          ctx.fill();
          ctx.shadowBlur = 0;

          // Nilai Angka Derajat Utama di Bawah Pita Kompas
          ctx.fillStyle = isWestLocked ? "#34d399" : "#ffffff";
          ctx.font = `bold ${Math.round(13 * scale)}px monospace`;
          ctx.textAlign = "center";
          ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
          ctx.shadowBlur = 4;
          const cardName = getCardinalDirection(curAz);
          const westIcon = isWestLocked ? "🎯 " : "";
          ctx.fillText(`${westIcon}${curAz.toFixed(1)}° ${cardName}`, cx, tapeY + tapeH + (18 * scale));
          ctx.shadowBlur = 0;

          // ==========================================================
          // 2. BAR VERTIKAL DERAJAT KEMIRINGAN (ELEVASI / TILT) DI SISI KIRI
          // ==========================================================
          const vBarX = Math.round(112 * scale); // Garis baseline vertikal di kiri layar (memberi ruang untuk label derajat/cm)

          ctx.save();
          // Baseline garis vertikal di sisi kiri layar
          ctx.strokeStyle = "rgba(255, 255, 255, 0.25)";
          ctx.lineWidth = 1 * scale;
          ctx.beginPath();
          ctx.moveTo(vBarX, vBarTop);
          ctx.lineTo(vBarX, vBarBot);
          ctx.stroke();

          // Skala derajat bergerak live mengikuti sudut curTilt
          const startPitch = Math.floor(curTilt - (vFovDeg / 2) - 2);
          const endPitch = Math.ceil(curTilt + (vFovDeg / 2) + 2);

          for (let p = startPitch; p <= endPitch; p++) {
            // Dalam fisika optik: sudut positif (menengadah ke langit) berada di atas cy
            const yPos = cy - (p - curTilt) * pxPerDegV;
            if (yPos < vBarTop || yPos > vBarBot) continue;

            const isZero = (p === 0);
            const isMajor = (p % 10 === 0);
            const isMedium = (p % 5 === 0);

            // Garis penanda skala (Tick Mark)
            ctx.beginPath();
            if (isZero) {
              ctx.strokeStyle = isLevel ? "#10b981" : "#38bdf8";
              ctx.lineWidth = 2.5 * scale;
              ctx.moveTo(vBarX - (24 * scale), yPos);
              ctx.lineTo(vBarX + (8 * scale), yPos);
            } else if (isMajor) {
              ctx.strokeStyle = "rgba(226, 232, 240, 0.9)";
              ctx.lineWidth = 1.5 * scale;
              ctx.moveTo(vBarX - (18 * scale), yPos);
              ctx.lineTo(vBarX + (4 * scale), yPos);
            } else if (isMedium) {
              ctx.strokeStyle = "rgba(255, 255, 255, 0.75)";
              ctx.lineWidth = 1.2 * scale;
              ctx.moveTo(vBarX - (14 * scale), yPos);
              ctx.lineTo(vBarX + (2 * scale), yPos);
            } else {
              // Garis mikro per 1° (tanpa teks angka agar tidak berdempetan)
              ctx.strokeStyle = "rgba(255, 255, 255, 0.25)";
              ctx.lineWidth = 0.8 * scale;
              ctx.moveTo(vBarX - (6 * scale), yPos);
              ctx.lineTo(vBarX, yPos);
            }
            ctx.stroke();

            // Label teks derajat dan sentimeter (Hanya untuk 0° UFUK dan kelipatan 5°: 5°, 10°, 15°, 20°)
            // Tidak menampilkan teks +1, +2, +3, -1, -2, -3 agar layar bersih
            if (isZero) {
              ctx.fillStyle = isLevel ? "#34d399" : "#38bdf8";
              ctx.font = `bold ${Math.round(10.5 * scale)}px sans-serif`;
              ctx.textAlign = "right";
              ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
              ctx.shadowBlur = 4;
              ctx.fillText("0°/0,00cm UFUK", vBarX - (28 * scale), yPos + (3.5 * scale));
              ctx.shadowBlur = 0;
            } else if (isMajor || isMedium) {
              const sign = p > 0 ? "+" : "-";
              const absP = Math.abs(p);
              const txt = `${sign}${absP}°/${getElevCmStr(absP)}cm`;

              ctx.fillStyle = isMajor ? "#f8fafc" : "#cbd5e1";
              ctx.font = `bold ${Math.round((isMajor ? 10 : 9) * scale)}px monospace`;
              ctx.textAlign = "right";
              ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
              ctx.shadowBlur = 3;
              ctx.fillText(txt, vBarX - (20 * scale), yPos + (3.5 * scale));
              ctx.shadowBlur = 0;
            }
          }
          ctx.restore();

          // Jarum penunjuk tetap di tengah tinggi layar (Segitiga ▶ menunjuk baseline)
          ctx.save();
          ctx.beginPath();
          ctx.moveTo(vBarX + (3 * scale), cy);
          ctx.lineTo(vBarX + (13 * scale), cy - (6 * scale));
          ctx.lineTo(vBarX + (13 * scale), cy + (6 * scale));
          ctx.closePath();
          ctx.fillStyle = isLevel ? "#10b981" : "#38bdf8";
          ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
          ctx.shadowBlur = 4;
          ctx.fill();
          ctx.shadowBlur = 0;

          // Label Nilai Derajat Kemiringan Vertikal Digital di samping jarum penunjuk
          ctx.fillStyle = isLevel ? "#34d399" : "#ffffff";
          ctx.font = `bold ${Math.round(11.5 * scale)}px monospace`;
          ctx.textAlign = "left";
          ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
          ctx.shadowBlur = 4;
          const tiltPrefix = curTilt > 0 ? "+" : (curTilt < 0 ? "-" : "");
          const absTilt = Math.abs(curTilt);
          const liveTiltCm = getElevCmStr(absTilt);
          ctx.fillText(`${tiltPrefix}${absTilt.toFixed(1)}°/${liveTiltCm}cm`, vBarX + (17 * scale), cy + (4 * scale));
          ctx.shadowBlur = 0;
          ctx.restore();

          // ==========================================================
          // 3. RETIKEL TITIK BIDIK TELESKOP BERSIH DI TENGAH LAYAR
          // ==========================================================
          // Menggantikan lingkaran besar dengan crosshair optik bersih tanpa menutupi ufuk
          const chGap = 6 * scale;
          const chLen = 16 * scale;
          ctx.strokeStyle = isLevel ? "#10b981" : "rgba(56, 189, 248, 0.75)";
          ctx.lineWidth = isLevel ? 1.8 * scale : 1.2 * scale;
          if (isLevel) {
            ctx.shadowColor = "rgba(16, 185, 129, 0.8)";
            ctx.shadowBlur = 6 * scale;
          }
          ctx.beginPath();
          // Garis horizontal kiri & kanan
          ctx.moveTo(cx - chGap - chLen, cy);
          ctx.lineTo(cx - chGap, cy);
          ctx.moveTo(cx + chGap, cy);
          ctx.lineTo(cx + chGap + chLen, cy);
          // Garis vertikal atas & bawah
          ctx.moveTo(cx, cy - chGap - chLen);
          ctx.lineTo(cx, cy - chGap);
          ctx.moveTo(cx, cy + chGap);
          ctx.lineTo(cx, cy + chGap + chLen);
          ctx.stroke();

          // Titik pusat bidik mikro di cx, cy
          ctx.beginPath();
          ctx.arc(cx, cy, 1.8 * scale, 0, 2 * Math.PI);
          ctx.fillStyle = isLevel ? "#34d399" : "#38bdf8";
          ctx.fill();
          ctx.shadowBlur = 0;
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

      // Terapkan penyesuaian kecerahan dan kontras
      if (typeof ctx.filter !== 'undefined') {
        ctx.filter = `brightness(${camLiveBrightness}%) contrast(${camLiveContrast}%)`;
      }

      // Jika pengguna melakukan zoom in, crop bagian tengah secara digital beresolusi penuh
      if (camLiveZoom > 1.01) {
        const cropW = video.videoWidth / camLiveZoom;
        const cropH = video.videoHeight / camLiveZoom;
        const cropX = (video.videoWidth - cropW) / 2;
        const cropY = (video.videoHeight - cropH) / 2;
        ctx.drawImage(video, cropX, cropY, cropW, cropH, 0, 0, hiddenCanvas.width, hiddenCanvas.height);
      } else {
        ctx.drawImage(video, 0, 0, hiddenCanvas.width, hiddenCanvas.height);
      }
      if (typeof ctx.filter !== 'undefined') {
        ctx.filter = 'none';
      }

      const b64 = hiddenCanvas.toDataURL('image/jpeg', 0.95);
      const slotNum = activeSlotIndex + 1;
      setPhotoToSlot(activeSlotIndex, b64, `Jepretan Kamera (Slot ${slotNum})`);
      stopLiveCamera();

      // Dapatkan azimuth saat ini
      const azVal = (typeof currentLiveCompassAzimuth !== 'undefined' && currentLiveCompassAzimuth !== null) ? currentLiveCompassAzimuth : (parseFloat(document.getElementById('inpAzimuth')?.value) || 270.0);

      // Simpan langsung ke folder 'hasil_jepretan' di disk laptop
      const lbl = document.getElementById('lblLastSavedCapture');
      if (lbl) {
        lbl.innerHTML = `⏳ Sedang menyimpan file ke <b>hasil_jepretan/</b>...`;
      }

      fetch('/api/save_capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_base64: b64,
          slot_index: activeSlotIndex,
          azimuth: azVal
        })
      })
      .then(r => r.json())
      .then(res => {
        if (res.status === 'success') {
          if (lbl) {
            lbl.innerHTML = `Tersimpan: <b style="color: #4ade80;">${res.filename}</b> (${res.size_kb} KB, ${res.resolution}) di <b>hasil_jepretan/</b>`;
          }
        } else {
          if (lbl) lbl.innerText = "Gagal simpan: " + (res.message || "Error");
        }
      })
      .catch(e => {
        console.warn("Gagal simpan capture:", e);
        if (lbl) lbl.innerText = "Error menyimpan file jepretan";
      });
    }

    async function openCapturesFolder() {
      try {
        const res = await fetch('/api/open_captures_folder', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
          console.log("Folder dibuka:", data.folder);
        }
      } catch (e) {
        alert("Gagal membuka folder: " + e.message);
      }
    }

    async function importFromSdCard() {
      try {
        const lbl = document.getElementById('lblLastSavedCapture');
        if (lbl) lbl.innerHTML = "⏳ Memeriksa kartu SD / drive kamera...";
        const res = await fetch('/api/import_sdcard_photos', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
          if (data.copied_count > 0) {
            alert(`Berhasil mengimpor ${data.copied_count} foto dari kamera ke folder 'hasil_jepretan'!\\n\\nFile:\\n${data.files.join('\\n')}`);
            if (lbl) {
              lbl.innerHTML = `Berhasil impor <b style="color: #4ade80;">${data.copied_count} foto</b> dari SD card ke <b>hasil_jepretan/</b>`;
            }
            openCapturesFolder();
          } else {
            alert("Tidak ditemukan file foto baru di kartu SD kamera yang terpasang.\\n\\nTips: Saat kamera berada di mode Webcam, foto diambil menggunakan tombol 'AMBIL FRAME (SPASI)' dan otomatis tersimpan.");
            if (lbl) {
              lbl.innerHTML = `hasil_jepretan/ (Tidak ada foto baru di kartu SD)`;
            }
          }
        }
      } catch (e) {
        alert("Gagal impor dari SD Card: " + e.message);
      }
    }

    async function zeroCurrentTilt() {
      try {
        const res = await fetch('/api/compass/zero_tilt', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
          liveCompassTilt = data.tilt || 0.0;
          const inp = document.getElementById('inpTilt');
          if (inp) inp.value = (data.tilt || 0.0).toFixed(1);
          alert(`🎯 Kalibrasi Kemiringan Sukses!\\nPosisi kamera fisik saat ini berhasil dinolkan menjadi 0.0° Level (Datar).\\nOffset tersimpan: ${data.tilt_offset}°`);
        }
      } catch (err) {
        alert("Gagal mengalibrasi kemiringan: " + err.message);
      }
    }

    // Tombol Spasi & Enter untuk memicu jepretan saat kamera live aktif
    window.addEventListener('keydown', function(e) {
      const liveWrapper = document.getElementById('liveCamWrapper');
      if (liveWrapper && liveWrapper.style.display !== 'none') {
        const activeTag = document.activeElement ? document.activeElement.tagName.toUpperCase() : '';
        if (activeTag === 'INPUT' || activeTag === 'TEXTAREA' || activeTag === 'SELECT') return;
        if (e.code === 'Space' || e.key === ' ' || e.code === 'Enter') {
          e.preventDefault();
          captureLiveFrame();
        }
      }
    });

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
        hfov: parseFloat(document.getElementById('inpHfov')?.value) || 60.0,
        latitude: parseFloat(document.getElementById('inpLat').value) || -7.98,
        longitude: parseFloat(document.getElementById('inpLon').value) || 110.306,
        altitude: parseFloat(document.getElementById('inpAlt')?.value) || 45.0
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
        const elPlot = document.getElementById('resPlotImg');
        if (elPlot) elPlot.src = data.plot_base64;
        resetImgZoom();
        
        const slider = document.getElementById('sliderAz');
        slider.min = data.az_min.toFixed(2);
        slider.max = data.az_max.toFixed(2);
        slider.value = payload.azimuth.toFixed(2);
        document.getElementById('lblSliderAz').innerText = payload.azimuth.toFixed(2) + "°";
        if (document.getElementById('lblMinAz')) document.getElementById('lblMinAz').innerText = data.az_min.toFixed(1) + "°";
        if (document.getElementById('lblMaxAz')) document.getElementById('lblMaxAz').innerText = data.az_max.toFixed(1) + "°";

        updateTargetDisplay(payload.azimuth, data.target_analysis);
        if (data.prominent_objects) {
          renderProminentObjects(data.prominent_objects);
        }

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
            const elPlot = document.getElementById('resPlotImg');
            if (elPlot) elPlot.src = data.plot_base64;
            document.getElementById('resOverlayImg').src = data.overlay_base64;
            if (data.prominent_objects) {
              renderProminentObjects(data.prominent_objects);
            }
          }
        });
      }, 90);
    }

    function updateTargetDisplay(targetAz, analysis) {
      const altStr = (analysis.target_alt >= 0 ? "+" : "") + analysis.target_alt.toFixed(2) + "°";
      if (document.getElementById('resTargetAlt')) {
        document.getElementById('resTargetAlt').innerText = altStr;
      }
      if (document.getElementById('resTargetAltDms')) {
        document.getElementById('resTargetAltDms').innerText = formatDms(analysis.target_alt);
      }
      const dipVal = analysis.dip_deg || 0.20;
      if (document.getElementById('resDip')) {
        document.getElementById('resDip').innerText = "-" + dipVal.toFixed(2) + "°";
      }
      if (document.getElementById('resDipDms')) {
        document.getElementById('resDipDms').innerText = formatDms(-dipVal);
      }
      if (document.getElementById('resDeltaHakiki')) {
        const delta = analysis.target_alt - 0.0;
        document.getElementById('resDeltaHakiki').innerText = (delta >= 0 ? "+" : "") + delta.toFixed(2) + "°";
      }
      if (document.getElementById('resStatusTxt')) {
        document.getElementById('resStatusTxt').innerText = analysis.severity || analysis.status || "Layak";
      }
      const cat = analysis.category || analysis.status || "Ufuk Terbuka";
      if (document.getElementById('resCategoryTxt')) {
        document.getElementById('resCategoryTxt').innerText = cat;
      }
      
      const smartDesc = `Berdasarkan ekstraksi kontur computer vision pada azimut bidikan ${targetAz.toFixed(2)}°, diperoleh tinggi rintangan ufuk pada azimut sasaran ${targetAz.toFixed(2)}° sebesar ${altStr}. Kondisi ufuk: ${cat}.`;
      if (document.getElementById('resDescText')) {
        document.getElementById('resDescText').innerText = smartDesc;
      }
      if (document.getElementById('textDesc')) {
        document.getElementById('textDesc').value = smartDesc;
      }

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
      const obs = encodeURIComponent(document.getElementById('editObserver')?.value.trim() || "Tim Falak & Astronomi");
      window.open('/api/download_pdf?loc=' + loc + '&obs=' + obs, '_blank');
    }

    function downloadExcel() {
      const loc = encodeURIComponent(document.getElementById('editLocation').value.trim() || "Pos Observasi");
      const step = document.getElementById('selTableInterval').value || '0.5';
      window.open('/api/download_excel?loc=' + loc + '&step=' + step, '_blank');
    }

    function downloadCsv() {
      const loc = encodeURIComponent(document.getElementById('editLocation').value.trim() || "Pos Observasi");
      const step = document.getElementById('selTableInterval').value || '0.5';
      window.open('/api/download_csv?loc=' + loc + '&step=' + step, '_blank');
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

      const latVal = parseFloat(document.getElementById('inpLat')?.value) || -7.98;
      const lonVal = parseFloat(document.getElementById('inpLon')?.value) || 110.3061;
      const altVal = parseFloat(document.getElementById('inpAlt')?.value) || 45;
      const locStr = (clientProfileCurve && clientProfileCurve.location_str)
        ? clientProfileCurve.location_str
        : `${latVal.toFixed(4)}°, ${lonVal.toFixed(4)}° (${Math.round(altVal)}m)`;

      let html = "";
      selectedRows.forEach((row, idx) => {
        const el = row.el;
        const az = row.az;
        const elStr = (el >= 0 ? "+" : "") + el.toFixed(2) + "°";
        const cmStr = getElevCmStr(el);
        const elevDisplay = `${elStr} / ${cmStr} cm`;

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
          <td style="padding: 8px 12px; color: #64748b; font-family: monospace; border-right: 1px solid #1e293b; text-align: center;">${idx + 1}</td>
          <td style="padding: 8px 12px; font-weight: bold; color: #38bdf8; font-family: monospace; border-right: 1px solid #1e293b; text-align: center;">${az.toFixed(2)}°</td>
          <td style="padding: 8px 12px; font-weight: bold; color: #f8fafc; font-family: monospace; border-right: 1px solid #1e293b; text-align: center;">${elevDisplay}</td>
          <td style="padding: 8px 12px; color: #cbd5e1; font-family: monospace; text-align: center;">${locStr}</td>
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
      const headerRow = ["No", "Azimut (°)", "Elevasi / cm", "Data Lokasi"].join("\\t");
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
      const dropArea = document.getElementById('dropArea');
      if (dropArea) {
        dropArea.style.display = 'block';
        dropArea.classList.remove('active');
      }
      document.getElementById('lblPhotoStatus').innerText = "Belum ada foto yang dipilih";
      document.getElementById('lblPhotoStatus').style.color = "#94a3b8";
      resetImgZoom();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // ==========================================
    // INTERACTIVE IMAGE: PINCH-ZOOM & AZIMUTH DRAG
    // ==========================================
    let imgZoomScale = 1.0;
    let imgPanX = 0, imgPanY = 0;
    let imgInitialPinchDist = null;
    let imgInitialZoom = 1.0;
    let isInteractingAzimuth = false;
    let isPanningImg = false;
    let imgPanStartX = 0, imgPanStartY = 0;

    function applyImgZoomTransform() {
      const vp = document.getElementById('zoomPanViewport');
      const badge = document.getElementById('zoomLevelBadge');
      if (vp) {
        vp.style.transform = "translate(" + imgPanX + "px, " + imgPanY + "px) scale(" + imgZoomScale + ")";
      }
      if (badge) {
        badge.innerText = Math.round(imgZoomScale * 100) + "%";
      }
    }

    function zoomInImg() {
      imgZoomScale = Math.min(4.0, imgZoomScale + 0.3);
      applyImgZoomTransform();
    }

    function zoomOutImg() {
      imgZoomScale = Math.max(1.0, imgZoomScale - 0.3);
      if (imgZoomScale <= 1.05) {
        imgZoomScale = 1.0;
        imgPanX = 0;
        imgPanY = 0;
      }
      applyImgZoomTransform();
    }

    function resetImgZoom() {
      imgZoomScale = 1.0;
      imgPanX = 0;
      imgPanY = 0;
      applyImgZoomTransform();
    }

    function getNormalizedImgX(clientX) {
      const img = document.getElementById('resOverlayImg');
      if (!img) return null;
      const rect = img.getBoundingClientRect();
      if (rect.width <= 0) return null;
      const relX = (clientX - rect.left) / rect.width;
      return Math.max(0.0, Math.min(1.0, relX));
    }

    function updateAzimuthFromImageX(clientX) {
      const relX = getNormalizedImgX(clientX);
      if (relX === null) return;
      const slider = document.getElementById('sliderAz');
      if (!slider) return;
      const minAz = parseFloat(slider.min) || 262.5;
      const maxAz = parseFloat(slider.max) || 277.5;
      const newAz = minAz + relX * (maxAz - minAz);
      slider.value = newAz.toFixed(2);
      onSliderTargetChanged(newAz);
    }

    function initInteractiveImage() {
      const container = document.getElementById('imgInteractiveContainer');
      if (!container) return;

      container.addEventListener('touchstart', function(e) {
        if (e.touches.length === 1) {
          if (imgZoomScale <= 1.1) {
            isInteractingAzimuth = true;
            updateAzimuthFromImageX(e.touches[0].clientX);
          } else {
            isPanningImg = true;
            imgPanStartX = e.touches[0].clientX - imgPanX;
            imgPanStartY = e.touches[0].clientY - imgPanY;
          }
        } else if (e.touches.length === 2) {
          isInteractingAzimuth = false;
          isPanningImg = false;
          const dx = e.touches[0].clientX - e.touches[1].clientX;
          const dy = e.touches[0].clientY - e.touches[1].clientY;
          imgInitialPinchDist = Math.hypot(dx, dy);
          imgInitialZoom = imgZoomScale;
        }
      }, { passive: false });

      container.addEventListener('touchmove', function(e) {
        e.preventDefault();
        if (e.touches.length === 1) {
          if (isInteractingAzimuth) {
            updateAzimuthFromImageX(e.touches[0].clientX);
          } else if (isPanningImg) {
            imgPanX = e.touches[0].clientX - imgPanStartX;
            imgPanY = e.touches[0].clientY - imgPanStartY;
            applyImgZoomTransform();
          }
        } else if (e.touches.length === 2 && imgInitialPinchDist) {
          const dx = e.touches[0].clientX - e.touches[1].clientX;
          const dy = e.touches[0].clientY - e.touches[1].clientY;
          const dist = Math.hypot(dx, dy);
          const factor = dist / imgInitialPinchDist;
          imgZoomScale = Math.min(4.5, Math.max(1.0, imgInitialZoom * factor));
          applyImgZoomTransform();
        }
      }, { passive: false });

      container.addEventListener('touchend', function(e) {
        if (e.touches.length === 0) {
          isInteractingAzimuth = false;
          isPanningImg = false;
          imgInitialPinchDist = null;
          if (imgZoomScale <= 1.05) {
            imgZoomScale = 1.0;
            imgPanX = 0;
            imgPanY = 0;
            applyImgZoomTransform();
          }
        } else if (e.touches.length === 1 && imgZoomScale > 1.0) {
          isPanningImg = true;
          imgPanStartX = e.touches[0].clientX - imgPanX;
          imgPanStartY = e.touches[0].clientY - imgPanY;
        }
      });

      let isMouseDown = false;
      container.addEventListener('mousedown', function(e) {
        if (e.button !== 0) return;
        isMouseDown = true;
        if (imgZoomScale <= 1.1) {
          updateAzimuthFromImageX(e.clientX);
        } else {
          isPanningImg = true;
          imgPanStartX = e.clientX - imgPanX;
          imgPanStartY = e.clientY - imgPanY;
        }
      });

      window.addEventListener('mousemove', function(e) {
        if (!isMouseDown) return;
        if (imgZoomScale <= 1.1) {
          updateAzimuthFromImageX(e.clientX);
        } else if (isPanningImg) {
          imgPanX = e.clientX - imgPanStartX;
          imgPanY = e.clientY - imgPanStartY;
          applyImgZoomTransform();
        }
      });

      window.addEventListener('mouseup', function() {
        isMouseDown = false;
        isPanningImg = false;
      });

      container.addEventListener('wheel', function(e) {
        e.preventDefault();
        const delta = e.deltaY < 0 ? 0.25 : -0.25;
        imgZoomScale = Math.min(4.5, Math.max(1.0, imgZoomScale + delta));
        if (imgZoomScale <= 1.05) {
          imgZoomScale = 1.0;
          imgPanX = 0;
          imgPanY = 0;
        }
        applyImgZoomTransform();
      }, { passive: false });

      container.addEventListener('dblclick', function() {
        resetImgZoom();
      });
    }

    // Interaksi klik & seret langsung pada Grafik Kurva Profil Elevasi vs Azimut
    function updateAzimuthFromPlotClientX(clientX) {
      const img = document.getElementById('resPlotImg');
      if (!img) return;
      const rect = img.getBoundingClientRect();
      if (rect.width <= 0) return;

      const relX = (clientX - rect.left) / rect.width;

      // Sumbu plot Matplotlib: left = 0.13, right = 0.96 (lebar area koordinat = 0.83)
      const leftBound = 0.13;
      const rightBound = 0.96;
      const plotWidth = rightBound - leftBound;

      const clampedX = Math.max(leftBound, Math.min(rightBound, relX));
      const axisFraction = (clampedX - leftBound) / plotWidth;

      const slider = document.getElementById('sliderAz');
      if (!slider) return;
      const minAz = parseFloat(slider.min) || 240.0;
      const maxAz = parseFloat(slider.max) || 300.0;

      const newAz = minAz + axisFraction * (maxAz - minAz);
      slider.value = newAz.toFixed(2);
      onSliderTargetChanged(newAz);
    }

    function initInteractivePlot() {
      const wrapper = document.getElementById('plotInteractiveWrapper');
      const img = document.getElementById('resPlotImg');
      const targetEl = wrapper || img;
      if (!targetEl) return;

      let isPlotMouseDown = false;

      targetEl.addEventListener('mousedown', function(e) {
        if (e.button !== 0) return;
        isPlotMouseDown = true;
        updateAzimuthFromPlotClientX(e.clientX);
      });

      window.addEventListener('mousemove', function(e) {
        if (!isPlotMouseDown) return;
        updateAzimuthFromPlotClientX(e.clientX);
      });

      window.addEventListener('mouseup', function() {
        isPlotMouseDown = false;
      });

      targetEl.addEventListener('touchstart', function(e) {
        if (e.touches.length === 1) {
          updateAzimuthFromPlotClientX(e.touches[0].clientX);
        }
      }, { passive: true });

      targetEl.addEventListener('touchmove', function(e) {
        if (e.touches.length === 1) {
          updateAzimuthFromPlotClientX(e.touches[0].clientX);
        }
      }, { passive: true });
    }

    // Dukungan Drag & Drop pada area pemilihan foto
    const dropAreaEl = document.getElementById('dropArea');
    if (dropAreaEl) {
      ['dragenter', 'dragover'].forEach(evt => {
        dropAreaEl.addEventListener(evt, e => {
          e.preventDefault();
          e.stopPropagation();
          dropAreaEl.style.borderColor = '#38bdf8';
          dropAreaEl.style.backgroundColor = '#1e293b';
        }, false);
      });
      ['dragleave', 'drop'].forEach(evt => {
        dropAreaEl.addEventListener(evt, e => {
          e.preventDefault();
          e.stopPropagation();
          dropAreaEl.style.borderColor = '#334155';
          dropAreaEl.style.backgroundColor = '#0f172a';
        }, false);
      });
      dropAreaEl.addEventListener('drop', e => {
        const dt = e.dataTransfer;
        if (dt && dt.files && dt.files.length > 0) {
          const fakeInput = { files: dt.files, id: 'galleryInput' };
          onFileSelected(fakeInput);
        }
      });
    }

    // Dukungan paste gambar langsung (Ctrl+V) dari clipboard
    window.addEventListener('paste', function(e) {
      const items = (e.clipboardData || (e.originalEvent && e.originalEvent.clipboardData) || {}).items;
      if (!items) return;
      for (let i = 0; i < items.length; i++) {
        if (items[i].kind === 'file' && items[i].type.startsWith('image/')) {
          const file = items[i].getAsFile();
          if (file) {
            compressAndSetImage(file, activeSlotIndex, "Foto Hasil Tempel (Paste Clipboard)");
            stopLiveCamera();
          }
          break;
        }
      }
    });

    document.addEventListener('DOMContentLoaded', function() {
      initInteractiveImage();
      initInteractivePlot();
      updatePhotoSlotsUI();
    });
  </script>
</body>
</html>
"""


@app.route("/api/check_cameras", methods=["GET"])
def api_check_cameras():
    result = {
        "cameras": [],
        "digicam_state": "not_detected",
        "message": ""
    }
    try:
        cmd = ["wmic", "path", "Win32_PnPEntity", "where", "DeviceID like \"%1B3F%\" and Status=\"OK\"", "get", "Caption,DeviceID", "/format:csv"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        out = r.stdout
        if "PID_2005" in out or "GENERAL-A-VIDEO" in out:
            result["digicam_state"] = "ready"
            result["message"] = "Kamera saku (GENERAL-A-VIDEO) aktif dalam mode Kamera PC/Webcam."
        elif "PID_8301" in out or "Mass Storage" in out:
            result["digicam_state"] = "storage_mode"
            result["message"] = "Kamera saku terdeteksi dalam mode Penyimpanan Massal."

        cmd_cam = ["wmic", "path", "Win32_PnPEntity", "where", "PNPClass=\"Camera\" and Status=\"OK\"", "get", "Caption,DeviceID", "/format:csv"]
        r_cam = subprocess.run(cmd_cam, capture_output=True, text=True, timeout=3)
        for line in r_cam.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("Node,") or line.startswith("Caption,"):
                continue
            parts = [p.strip() for p in line.split(",") if p.strip()]
            if len(parts) >= 2:
                caption = parts[1]
                dev_id = parts[2] if len(parts) > 2 else ""
                result["cameras"].append({"caption": caption, "device_id": dev_id})
    except Exception as e:
        result["error"] = str(e)
    return jsonify(result)


@app.route("/api/save_capture", methods=["POST"])
def api_save_capture():
    try:
        data = request.get_json(force=True)
        b64_data = data.get("image_base64", "")
        slot_idx = int(data.get("slot_index", 0)) + 1
        az_val = float(data.get("azimuth", 270.0))
        
        if not b64_data:
            return jsonify({"status": "error", "message": "Tidak ada data gambar"}), 400
        
        if "," in b64_data:
            b64_data = b64_data.split(",", 1)[1]
            
        img_bytes = base64.b64decode(b64_data)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        if img_bgr is None:
            return jsonify({"status": "error", "message": "Gagal decode gambar"}), 400
            
        h, w = img_bgr.shape[:2]
        captures_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hasil_jepretan")
        os.makedirs(captures_dir, exist_ok=True)
        
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        filename = f"jepretan_{timestamp_str}_Slot{slot_idx}_az{az_val:.1f}.jpg"
        filepath = os.path.join(captures_dir, filename)
        
        # Simpan dengan kualitas JPEG tinggi (95)
        cv2.imwrite(filepath, img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        file_size_kb = round(os.path.getsize(filepath) / 1024, 1)
        
        return jsonify({
            "status": "success",
            "filename": filename,
            "filepath": filepath,
            "relative_path": f"hasil_jepretan/{filename}",
            "resolution": f"{w}x{h}",
            "size_kb": file_size_kb,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/open_captures_folder", methods=["POST", "GET"])
def api_open_captures_folder():
    captures_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hasil_jepretan")
    os.makedirs(captures_dir, exist_ok=True)
    try:
        if sys.platform.startswith("win"):
            os.startfile(captures_dir)
        elif sys.platform.startswith("darwin"):
            subprocess.run(["open", captures_dir])
        else:
            subprocess.run(["xdg-open", captures_dir])
        return jsonify({"status": "success", "folder": captures_dir})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/import_sdcard_photos", methods=["POST", "GET"])
def api_import_sdcard_photos():
    captures_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hasil_jepretan")
    os.makedirs(captures_dir, exist_ok=True)
    copied = []
    import shutil
    
    for letter in "EFGHIJKLMNOPQRSTUVWXYZ":
        root_path = f"{letter}:\\"
        if os.path.exists(root_path):
            dcim_path = os.path.join(root_path, "DCIM")
            search_dir = dcim_path if os.path.exists(dcim_path) else root_path
            try:
                for root, _, files in os.walk(search_dir):
                    for f in files:
                        if f.lower().endswith((".jpg", ".jpeg", ".png")):
                            src = os.path.join(root, f)
                            dst_name = f"sdcard_{f}"
                            dst = os.path.join(captures_dir, dst_name)
                            if not os.path.exists(dst):
                                shutil.copy2(src, dst)
                                copied.append(dst_name)
            except Exception:
                pass
    return jsonify({"status": "success", "copied_count": len(copied), "files": copied})


@app.route("/api/compass", methods=["GET"])
def api_compass():
    return jsonify(compass_service.get_data())


@app.route("/api/compass/zero_tilt", methods=["POST", "GET"])
def api_compass_zero_tilt():
    new_offset = compass_service.set_zero_tilt()
    cur_data = compass_service.get_data()
    return jsonify({
        "status": "success",
        "tilt_offset": new_offset,
        "tilt": cur_data.get("tilt", 0.0),
        "message": f"Kemiringan berhasil dinolkan (Offset {new_offset:.1f}° disimpan sebagai 0.0° Level)"
    })


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


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
    """Render kurva profil 2D menggunakan Matplotlib Agg berresolusi tinggi dan presisi falak."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    CALIB_DEG_CM = {
        0: "0,00", 1: "0,52", 2: "1,04", 3: "1,57", 4: "2,09",
        5: "2,62", 6: "3,15", 7: "3,68", 8: "4,21", 9: "4,75",
        10: "5,28", 11: "5,83", 12: "6,37", 13: "6,92", 14: "7,47",
        15: "8,03", 16: "8,60", 17: "9,17", 18: "9,74", 19: "10,32", 20: "10,91"
    }

    fig, ax = plt.subplots(figsize=(8.0, 3.4), dpi=120)
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#020617")
    fig.subplots_adjust(left=0.13, right=0.96, top=0.88, bottom=0.15)

    az_arr = np.asarray(azimuths)
    el_arr = np.asarray(elevations)

    # Kurva Kontur Ufuk Mar'i (Garis Merah dan Area Arsiran mulai dari 0°)
    c_curve = "#ef4444"
    ax.plot(az_arr, el_arr, color=c_curve, linewidth=2.2, label="Kontur Ufuk Mar'i")
    ax.fill_between(az_arr, np.maximum(0, el_arr), 0, color=c_curve, alpha=0.22)

    # Titik sasaran jika ada
    if target_az is not None:
        t_alt = float(target_alt) if target_alt is not None else 0.0
        c_target = "#d946ef"
        ax.axvline(target_az, color=c_target, linestyle="-.", linewidth=1.5, label=f"Azimut Sasaran ({target_az:.2f}°)")
        ax.scatter([target_az], [t_alt], color=c_target, s=60, zorder=5)
        ax.scatter([target_az], [t_alt], color="#ffffff", s=20, zorder=6)
        ax.annotate(
            f"Halangan: {t_alt:+.2f}°",
            xy=(target_az, t_alt),
            xytext=(target_az + 0.35, t_alt + 0.5),
            fontsize=8,
            fontweight="bold",
            color="#fae8ff",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="#1e1b4b", edgecolor="#c026d3", alpha=0.9),
        )

    # Skala sumbu X (Azimut)
    az_min = float(az_arr[0])
    az_max = float(az_arr[-1])
    ax.set_xlim(az_min, az_max)
    if abs((az_max - az_min) - 60.0) < 5.0 and abs(az_min - 240.0) < 5.0:
        x_ticks = [240.0, 250.0, 260.0, 270.0, 280.0, 290.0, 300.0]
    else:
        az_step = 10.0 if (az_max - az_min) >= 30.0 else 5.0
        x_ticks = list(np.arange(np.ceil(az_min / az_step) * az_step, az_max, az_step))
        if not any(abs(t - az_min) < 3.0 for t in x_ticks):
            x_ticks.insert(0, az_min)
        if not any(abs(t - az_max) < 3.0 for t in x_ticks):
            x_ticks.append(az_max)

    def format_az_tick(val):
        deg = val % 360.0 if val >= 360.0 else val
        s = f"{deg:.0f}°"
        if abs((val % 360.0) - 270.0) < 0.2:
            s += " (Barat)"
        return s

    x_labels = [format_az_tick(x) for x in x_ticks]
    ax.set_xticks(x_ticks)
    ax.set_xticklabels(x_labels, fontsize=8, color="#cbd5e1")

    # Skala sumbu Y (Elevasi 0 s.d 20 derajat) + cm sesuai kalibrasi acuan falak 30cm
    ax.set_ylim(0.0, 20.0)
    y_ticks = [0, 5, 10, 15, 20]
    y_labels = [f"+{y}° / {CALIB_DEG_CM[y]} cm" if y > 0 else "0° / 0,00 cm" for y in y_ticks]
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels, fontsize=8, color="#f8fafc")

    ax.set_xlabel("Rentang Azimut Bidikan (°)", fontsize=8.5, fontweight="bold", color="#94a3b8")
    ax.set_ylabel("Sudut Elevasi / Skala Falak (° / cm)", fontsize=8.5, fontweight="bold", color="#94a3b8")
    ax.set_title("Kurva Profil Elevasi Ufuk Mar'i vs Azimut", fontsize=9.5, fontweight="bold", color="#38bdf8", pad=6)
    ax.grid(True, linestyle="--", alpha=0.4, color="#334155")
    ax.legend(loc="upper right", fontsize=7.5, framealpha=0.85)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor(), dpi=120)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


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
    hfov_val = float(data.get("hfov", 60.0))
    if hfov_val <= 0:
        hfov_val = 60.0
    hfov_rad = math.radians(hfov_val)
    vfov_val = math.degrees(2.0 * math.atan((h / w) * math.tan(hfov_rad / 2.0)))

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
        hfov=hfov_val,
        vfov=vfov_val,
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
        hfov=hfov_val,
        vfov=vfov_val,
        tilt_center=tilt,
        prominent_obstacles=profile_data.get("prominent_obstacles", []),
        show_prominent_peaks=True,
    )

    _, ov_buf = cv2.imencode(".jpg", overlay_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    overlay_b64 = "data:image/jpeg;base64," + base64.b64encode(ov_buf).decode("utf-8")

    # Render kurva cepat OpenCV
    plot_b64 = fast_render_plot_image(az_arr, el_arr, profile_data["dip_deg"], target_az, target_alt)

    # Downsample kurva untuk komputasi instan di ponsel klien (termasuk titik batas awal dan akhir)
    curve_step = max(1, len(az_arr) // 160)
    indices = list(range(0, len(az_arr), curve_step))
    if indices[-1] != len(az_arr) - 1:
        indices.append(len(az_arr) - 1)
    profile_curve = {
        "az": [float(az_arr[i]) for i in indices],
        "el": [float(el_arr[i]) for i in indices]
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
        "hfov": hfov_val,
        "vfov": vfov_val,
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
        "profile_curve": profile_curve,
        "prominent_objects": profile_data.get("prominent_obstacles", []),
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

    hfov_val = float(LAST_ANALYSIS.get("hfov", 60.0))
    vfov_val = float(LAST_ANALYSIS.get("vfov", 36.0))

    overlay_bgr = detector.render_overlay(
        image_bgr=LAST_ANALYSIS["image_bgr"],
        horizon_y=LAST_ANALYSIS["horizon_y"],
        azimuths=az_arr,
        elevations=el_arr,
        target_az=target_az,
        dip_deg=prof["dip_deg"],
        az_center=LAST_ANALYSIS["azimuth"],
        hfov=hfov_val,
        vfov=vfov_val,
        tilt_center=LAST_ANALYSIS["tilt"],
        prominent_obstacles=prof.get("prominent_obstacles", []),
        show_prominent_peaks=True,
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
        "target_analysis": target_analysis,
        "prominent_objects": prof.get("prominent_obstacles", []),
    })


def _generate_current_pdf_path(location_name=None, observer_name=None, observer_notes=None, recommendation_text=None) -> str:
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
    obs = observer_name or "Tim Falak & Astronomi"

    hfov_val = float(LAST_ANALYSIS.get("hfov", 60.0))
    vfov_val = float(LAST_ANALYSIS.get("vfov", 36.0))

    export_pdf_report(
        output_pdf_path=pdf_path,
        location_name=loc,
        latitude=LAST_ANALYSIS["latitude"],
        longitude=LAST_ANALYSIS["longitude"],
        elevation_m=LAST_ANALYSIS["altitude"],
        az_center=LAST_ANALYSIS["azimuth"],
        hfov=hfov_val,
        vfov=vfov_val,
        tilt_center=LAST_ANALYSIS["tilt"],
        dip_deg=LAST_ANALYSIS["profile_data"]["dip_deg"],
        profile_data=LAST_ANALYSIS["profile_data"],
        overlay_img_bgr=LAST_ANALYSIS["overlay_bgr"],
        target_analysis=ta,
        observer_notes=desc,
        recommendation_text=rec,
        observer_name=obs,
    )
    return pdf_path


@app.route("/api/preview_pdf", methods=["POST", "GET"])
def api_preview_pdf():
    try:
        data = request.json or {} if request.method == "POST" else {}
        loc = data.get("location_name") or request.args.get("loc")
        obs = data.get("observer_name") or request.args.get("obs")
        notes = data.get("observer_notes")
        rec = data.get("recommendation_text")

        pdf_path = _generate_current_pdf_path(location_name=loc, observer_name=obs, observer_notes=notes, recommendation_text=rec)
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
        obs = request.args.get("obs")
        pdf_path = _generate_current_pdf_path(location_name=loc, observer_name=obs)
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

    lat = LAST_ANALYSIS.get("latitude", -7.98)
    lon = LAST_ANALYSIS.get("longitude", 110.3061)
    alt = LAST_ANALYSIS.get("altitude", 45.0)
    data_loc = f"{lat:.4f}°, {lon:.4f}° ({int(alt)}m)"

    step_arg = request.args.get("step", None)
    sampling_step = None
    if step_arg and step_arg != "all":
        try:
            sampling_step = float(step_arg)
        except ValueError:
            sampling_step = None

    export_csv_data(
        output_csv_path=csv_path,
        profile_data=LAST_ANALYSIS["profile_data"],
        location_name=data_loc,
        az_center=LAST_ANALYSIS["azimuth"],
        dip_deg=LAST_ANALYSIS["profile_data"]["dip_deg"],
        sampling_step=sampling_step,
    )

    return send_file(csv_path, as_attachment=True, download_name="Data_Profil_Ufuk.csv")


@app.route("/api/download_excel", methods=["GET"])
def api_download_excel():
    global LAST_ANALYSIS
    if not LAST_ANALYSIS:
        return "Belum ada data analisis aktif", 400

    exports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
    os.makedirs(exports_dir, exist_ok=True)
    excel_path = os.path.join(exports_dir, f"Data_Ufuk_Web_{int(time.time())}.xlsx")

    lat = LAST_ANALYSIS.get("latitude", -7.98)
    lon = LAST_ANALYSIS.get("longitude", 110.3061)
    alt = LAST_ANALYSIS.get("altitude", 45.0)
    data_loc = f"{lat:.4f}°, {lon:.4f}° ({int(alt)}m)"

    step_arg = request.args.get("step", "0.5")
    sampling_step = None
    if step_arg and step_arg != "all":
        try:
            sampling_step = float(step_arg)
        except ValueError:
            sampling_step = None

    export_excel_data(
        output_excel_path=excel_path,
        profile_data=LAST_ANALYSIS["profile_data"],
        location_name=data_loc,
        az_center=LAST_ANALYSIS["azimuth"],
        dip_deg=LAST_ANALYSIS["profile_data"]["dip_deg"],
        sampling_step=sampling_step,
    )

    return send_file(
        excel_path,
        as_attachment=True,
        download_name="Data_Profil_Ufuk_Tabel_Excel.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def main():
    import socket
    lan_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            lan_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            pass

    print("=" * 60)
    print("   APLIKASI PEMETAAN UFUK MAR'I (EDISI LAPTOP & DESKTOP)")
    print("   Buka dari Browser Laptop : http://127.0.0.1:5000")
    print(f"   Buka dari HP / WiFi Lain  : http://{lan_ip}:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)


if __name__ == "__main__":
    main()
