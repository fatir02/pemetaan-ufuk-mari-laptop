"""
report_generator.py
Modul pembuatan laporan PDF resmi untuk pemetaan profil ufuk mar'i menggunakan ReportLab.
Menyusun dokumen formal astronomi/falak lengkap dengan tabel parameter,
foto overlay kontur, grafik kurva elevasi, tabel hasil analisis, dan rekomendasi kelayakan rukyat.
"""

import os
import time
from typing import Dict, Any, Optional
import numpy as np
import cv2
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    KeepTogether,
    HRFlowable,
)

from core.falak_calc import format_dms


def export_pdf_report(
    output_pdf_path: str,
    location_name: str,
    latitude: float,
    longitude: float,
    elevation_m: float,
    az_center: float,
    hfov: float,
    vfov: float,
    tilt_center: float,
    dip_deg: float,
    profile_data: Dict[str, Any],
    overlay_img_bgr: np.ndarray,
    target_analysis: Optional[Dict[str, Any]] = None,
    observer_notes: str = "",
    recommendation_text: str = "",
    instansi_name: str = "FAKULTAS SYARIAH - LABORATORIUM ASTRONOMI & ILMU FALAK",
) -> str:
    """
    Menghasilkan dokumen laporan pemetaan ufuk mar'i dalam format PDF.
    
    Returns:
        output_pdf_path yang telah berhasil disimpan.
    """
    # Pastikan direktori tujuan tersedia
    os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)

    # 1. Simpan gambar overlay dan plot grafik sementara ke disk untuk disisipkan ke PDF
    temp_dir = os.path.join(os.path.dirname(os.path.abspath(output_pdf_path)), "temp_assets")
    os.makedirs(temp_dir, exist_ok=True)
    temp_overlay_path = os.path.join(temp_dir, "temp_overlay.jpg")
    temp_plot_path = os.path.join(temp_dir, "temp_plot.png")

    # Tulis overlay citra
    cv2.imwrite(temp_overlay_path, overlay_img_bgr)

    # Render grafik profil ufuk khusus untuk laporan PDF (resolusi tajam 300 DPI)
    azimuths = profile_data["azimuths"]
    elevations = profile_data["elevations"]

    fig, ax = plt.subplots(figsize=(8.5, 3.6), dpi=220)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#f9f9fb")

    # Garis Ufuk Hakiki (0°)
    ax.axhline(0, color="#1976d2", linestyle="--", linewidth=1.2, label="Ufuk Hakiki (0.00°)")

    # Garis Kerendahan Ufuk Laut (-Dip)
    if dip_deg > 0:
        ax.axhline(-dip_deg, color="#ff8f00", linestyle=":", linewidth=1.3, label=f"Kerendahan Ufuk Laut (-{dip_deg:.2f}°)")

    # Kurva Kontur Ufuk Mar'i
    ax.plot(azimuths, elevations, color="#d32f2f", linewidth=2.0, label="Kontur Ufuk Mar'i")
    ax.fill_between(azimuths, elevations, -10, color="#d32f2f", alpha=0.18)

    # Titik sasaran jika ada
    if target_analysis and "target_az" in target_analysis:
        t_az = target_analysis["target_az"]
        t_alt = target_analysis.get("alt_obstacle", target_analysis.get("target_alt", 0.0))
        ax.axvline(t_az, color="#7b1fa2", linestyle="-.", linewidth=1.5, label=f"Azimut Sasaran ({t_az:.2f}°)")
        ax.scatter([t_az], [t_alt], color="#7b1fa2", s=70, zorder=5)
        ax.annotate(
            f"Halangan: {t_alt:+.2f}°",
            xy=(t_az, t_alt),
            xytext=(t_az + 0.2, t_alt + 0.3),
            fontsize=8,
            fontweight="bold",
            color="#4a148c",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#ede7f6", edgecolor="#7b1fa2", alpha=0.9),
        )

    ax.set_xlim(azimuths[0], azimuths[-1])
    # Batas sumbu Y dengan ruang nafas
    y_min_plot = min(-dip_deg - 0.5, np.min(elevations) - 0.5, -1.0)
    y_max_plot = max(np.max(elevations) + 0.8, 2.0)
    ax.set_ylim(y_min_plot, y_max_plot)

    ax.set_xlabel("Rentang Azimut Bidikan (°)", fontsize=9, fontweight="bold", color="#000000")
    ax.set_ylabel("Sudut Elevasi / Ketinggian (°)", fontsize=9, fontweight="bold", color="#000000")
    ax.set_title("Grafik Profil Elevasi Ufuk Mar'i terhadap Azimut Bidikan", fontsize=10, fontweight="bold", color="#000000", pad=6)
    ax.grid(True, linestyle="--", alpha=0.5, color="#bdbdbd")
    ax.legend(loc="upper right", fontsize=7.5, framealpha=0.9)
    plt.tight_layout()
    fig.savefig(temp_plot_path, dpi=220)
    plt.close(fig)

    # 2. Bangun Dokumen PDF dengan ReportLab
    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=A4,
        rightMargin=28,
        leftMargin=28,
        topMargin=26,
        bottomMargin=26,
    )

    styles = getSampleStyleSheet()
    
    # Custom Typography Styles - Teks Hitam Formal Akademik
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.black,
        alignment=1,  # Center
    )
    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.black,
        alignment=1,
    )
    section_style = ParagraphStyle(
        "DocSection",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=colors.black,
        spaceBefore=8,
        spaceAfter=3,
    )
    body_style = ParagraphStyle(
        "DocBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.black,
    )
    badge_style = ParagraphStyle(
        "DocBadge",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.black,
        alignment=1,
    )

    elements = []

    # HEADER KOP RESMI
    elements.append(Paragraph(instansi_name.upper(), title_style))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph("BERITA ACARA & LAPORAN PEMETAAN PROFIL UFUK MAR'I", ParagraphStyle("H2", parent=title_style, fontSize=12, leading=14, textColor=colors.black)))
    elements.append(Paragraph("Instrumen Falak Digital Berbasis Computer Vision & Analisis Kelayakan Tempat Rukyat", subtitle_style))
    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.black, spaceBefore=1, spaceAfter=8))

    # Waktu Pengamatan
    now_str = time.strftime("%d %B %Y - %H:%M:%S WIB")
    elements.append(Paragraph(f"<b>Waktu Ekstraksi & Verifikasi:</b> {now_str}", body_style))
    elements.append(Spacer(1, 6))

    # TABEL 1: PARAMETER TITIK PENGAMATAN & OPTIK KAMERA
    elements.append(Paragraph("I. PARAMETER GEOGRAFIS & SPESIFIKASI INSTRUMEN OPTIK", section_style))

    dms_lat = format_dms(latitude, is_lat=True)
    dms_lon = format_dms(longitude, is_lon=True)
    stats = profile_data.get("stats", {})

    meta_table_data = [
        [
            Paragraph("<b>Titik Pengamatan:</b>", body_style),
            Paragraph(location_name or "Lokasi Pengamatan Falak", body_style),
            Paragraph("<b>Azimut Bidikan Tengah:</b>", body_style),
            Paragraph(f"{az_center:.2f}° (Barat)", body_style),
        ],
        [
            Paragraph("<b>Lintang Tempat (phi):</b>", body_style),
            Paragraph(f"{dms_lat} ({latitude:+.5f}°)", body_style),
            Paragraph("<b>Field of View (H / V):</b>", body_style),
            Paragraph(f"{hfov:.1f}° / {vfov:.1f}°", body_style),
        ],
        [
            Paragraph("<b>Bujur Tempat (lambda):</b>", body_style),
            Paragraph(f"{dms_lon} ({longitude:+.5f}°)", body_style),
            Paragraph("<b>Rentang Azimut:</b>", body_style),
            Paragraph(f"{stats.get('az_range_min', 0):.2f}° s.d. {stats.get('az_range_max', 0):.2f}°", body_style),
        ],
        [
            Paragraph("<b>Ketinggian Tempat (h):</b>", body_style),
            Paragraph(f"{elevation_m:.1f} m dpl", body_style),
            Paragraph("<b>Kerendahan Ufuk (Dip):</b>", body_style),
            Paragraph(f"{dip_deg:.3f}° ({profile_data.get('dip_arcmin', 0):.2f} menit busur)", body_style),
        ],
    ]

    t_meta = Table(meta_table_data, colWidths=[130, 140, 125, 125])
    t_meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f9f9f9")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_meta)
    elements.append(Spacer(1, 8))

    # BAGIAN VISUAL: FOTO OVERLAY & GRAFIK
    elements.append(Paragraph("II. CITRA LAPANGAN & GRAFIK PROFIL KONTUR UFUK MAR'I", section_style))

    # Tampilkan foto overlay dan grafik dengan ukuran yang pas di halaman A4
    w_img = 490
    h_img = 138
    w_plot = 490
    h_plot = 132

    elements.append(RLImage(temp_overlay_path, width=w_img, height=h_img))
    elements.append(Spacer(1, 3))
    elements.append(RLImage(temp_plot_path, width=w_plot, height=h_plot))
    elements.append(Spacer(1, 4))

    # TABEL 2: ANALISIS TITIK BIDIK SASARAN (Misal Azimut Hilal)
    elements.append(Paragraph("III. HASIL ANALISIS SUDUT HALANGAN UFUK PADA TITIK SASARAN", section_style))

    if target_analysis:
        t_az = target_analysis.get("target_az", az_center)
        t_alt = target_analysis.get("alt_obstacle", 0.0)
        t_status = target_analysis.get("status", "Bebas Halangan")
        t_cat = target_analysis.get("category", "-")
        t_sev = target_analysis.get("severity", "Baik")

        analysis_table_data = [
            [
                Paragraph("<b>Parameter Sasaran</b>", body_style),
                Paragraph("<b>Nilai Kalkulasi</b>", body_style),
                Paragraph("<b>Keterangan Astronomis</b>", body_style),
            ],
            [
                Paragraph("Azimut Bidikan Sasaran:", body_style),
                Paragraph(f"<b>{t_az:.2f}°</b>", body_style),
                Paragraph("Arah kompas target rukyatul hilal / matahari", body_style),
            ],
            [
                Paragraph("Tinggi Halangan Mar'i (Alt):", body_style),
                Paragraph(f"<b>{t_alt:+.3f}°</b> ({format_dms(t_alt)})", body_style),
                Paragraph("Sudut elevasi kontur terhadap ufuk hakiki (0°)", body_style),
            ],
            [
                Paragraph("Selisih thd Ufuk Hakiki (0°):", body_style),
                Paragraph(f"{t_alt:+.3f}°", body_style),
                Paragraph("Halangan di atas (positif) atau di bawah (negatif)", body_style),
            ],
            [
                Paragraph("Selisih thd Ufuk Laut (-Dip):", body_style),
                Paragraph(f"{t_alt - (-dip_deg):+.3f}°", body_style),
                Paragraph(f"Tinggi rintangan relatif terhadap cakrawala air laut (-{dip_deg:.2f}°)", body_style),
            ],
            [
                Paragraph("Status & Klasifikasi Halangan:", body_style),
                Paragraph(f"<b>{t_status}</b> ({t_sev})", body_style),
                Paragraph(t_cat, body_style),
            ],
        ]

        t_analysis = Table(analysis_table_data, colWidths=[150, 160, 210])
        t_analysis.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        elements.append(t_analysis)
    else:
        elements.append(Paragraph("<i>Belum ada titik sasaran azimut yang dipilih.</i>", body_style))

    elements.append(Spacer(1, 6))

    # BAGIAN CATATAN & REKOMENDASI KELAYAKAN
    elements.append(Paragraph("IV. REKOMENDASI KELAYAKAN LOKASI RUKYAT & CATATAN LAPANGAN", section_style))

    rec_content = recommendation_text.strip() if recommendation_text.strip() else (
        target_analysis.get("recommendation", "Lokasi memiliki keterbukaan ufuk yang baik.")
        if target_analysis else "Lokasi pengamatan belum dianalisis secara spesifik."
    )
    notes_content = observer_notes.strip() if observer_notes.strip() else "Tidak ada catatan tambahan kondisi atmosfer/lapangan."

    rec_table_data = [
        [
            Paragraph("<b>Evaluasi Kelayakan Rukyat:</b>", body_style),
            Paragraph(rec_content, body_style),
        ],
        [
            Paragraph("<b>Catatan Manual Pengamat:</b>", body_style),
            Paragraph(notes_content, body_style),
        ],
    ]

    t_rec = Table(rec_table_data, colWidths=[160, 360])
    t_rec.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f9f9f9")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_rec)
    elements.append(Spacer(1, 10))

    # TANDA TANGAN PENGESAHAN
    sig_table_data = [
        [
            Paragraph("Petugas Pengamat / Surveyor Falak,", ParagraphStyle("S1", parent=body_style, alignment=1, textColor=colors.black)),
            Paragraph("Mengetahui / Memvalidasi:<br/>Ketua Laboratorium Falak,", ParagraphStyle("S2", parent=body_style, alignment=1, textColor=colors.black)),
        ],
        [
            Spacer(1, 24),
            Spacer(1, 24),
        ],
        [
            Paragraph("( ...................................................... )", ParagraphStyle("S3", parent=body_style, alignment=1, textColor=colors.black)),
            Paragraph("( ...................................................... )", ParagraphStyle("S4", parent=body_style, alignment=1, textColor=colors.black)),
        ],
    ]
    t_sig = Table(sig_table_data, colWidths=[260, 260])
    t_sig.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    elements.append(KeepTogether(t_sig))

    # Bangun PDF
    doc.build(elements)

    # Bersihkan file sementara
    try:
        if os.path.exists(temp_overlay_path):
            os.remove(temp_overlay_path)
        if os.path.exists(temp_plot_path):
            os.remove(temp_plot_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
    except Exception:
        pass

    return output_pdf_path


def export_csv_data(
    output_csv_path: str,
    location_name: str,
    az_center: float,
    profile_data: Dict[str, Any],
    dip_deg: Optional[float] = None,
) -> str:
    """
    Mengekspor data numerik profil ufuk (Azimuth, Elevation, Horizon_Y) ke file CSV
    dalam format tabel yang rapi, informatif, dan mudah dibaca.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_csv_path)), exist_ok=True)
    azimuths = profile_data["azimuths"]
    elevations = profile_data["elevations"]
    horizon_y = profile_data["horizon_y"]
    dip_val = float(dip_deg) if dip_deg is not None else float(profile_data.get("dip_deg", 0.0))

    with open(output_csv_path, "w", encoding="utf-8") as f:
        f.write("# ==========================================================================\n")
        f.write("# TABEL DATA NUMERIK PROFIL UFUK MAR'I BERBASIS COMPUTER VISION\n")
        f.write(f"# Pos Observasi Falak     : {location_name}\n")
        f.write(f"# Azimut Bidikan Utama    : {az_center:.2f}° (Barat)\n")
        f.write(f"# Kerendahan Ufuk Laut Dip: -{dip_val:.4f}°\n")
        f.write(f"# Waktu Ekspor            : {time.strftime('%Y-%m-%d %H:%M:%S')} WIB\n")
        f.write("# ==========================================================================\n")
        f.write("No,Kolom_Pixel_X,Azimut_deg,Elevasi_Halangan_deg,Elevasi_DMS,Selisih_Hakiki_deg,Selisih_Dip_deg,Status_Rukyat\n")
        for x in range(len(azimuths)):
            el = float(elevations[x])
            az = float(azimuths[x])
            dms = format_dms(el)
            delta_hakiki = el - 0.0
            delta_dip = el - (-dip_val)
            if el <= -dip_val + 0.05:
                status = "Sangat Terbuka"
            elif el <= 0.0:
                status = "Ufuk Rendah Terbuka"
            elif el <= 1.2:
                status = "Halangan Rendah (Aman)"
            else:
                status = "Halangan Tinggi (Waspada)"
            f.write(f"{x + 1},{x},{az:.4f},{el:+.4f},\"{dms}\",{delta_hakiki:+.4f},{delta_dip:+.4f},{status}\n")

    return output_csv_path
