"""
report_generator.py
Modul pembuatan laporan PDF resmi untuk pemetaan profil ufuk mar'i menggunakan ReportLab.
Menyusun dokumen formal astronomi/falak lengkap dengan tabel parameter,
foto overlay kontur, grafik kurva elevasi, tabel hasil analisis, dan rekomendasi kelayakan rukyat.
"""

import os
import time
import math
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


def _prepare_table_rows(
    profile_data: Dict[str, Any],
    dip_val: float,
    sampling_step: Optional[float] = None,
):
    azimuths = profile_data["azimuths"]
    elevations = profile_data["elevations"]

    rows = []
    if sampling_step is not None and sampling_step > 0.0:
        min_az = float(azimuths[0])
        max_az = float(azimuths[-1])
        last_target = math.floor(min_az / sampling_step) * sampling_step
        while last_target <= max_az + 0.0001:
            if last_target >= min_az - 0.0001 and last_target <= max_az + 0.0001:
                best_idx = 0
                best_diff = 9999.0
                for i in range(len(azimuths)):
                    diff = abs(float(azimuths[i]) - last_target)
                    if diff < best_diff:
                        best_diff = diff
                        best_idx = i
                rows.append((best_idx, float(azimuths[best_idx]), float(elevations[best_idx])))
            last_target += sampling_step
    else:
        for x in range(len(azimuths)):
            rows.append((x, float(azimuths[x]), float(elevations[x])))

    result = []
    for num, (col_x, az, el) in enumerate(rows, start=1):
        dms = format_dms(el)
        delta_hakiki = el - 0.0
        delta_dip = el - (-dip_val)
        if el <= -dip_val + 0.05:
            status = "Sangat Terbuka (Bebas)"
        elif el <= 0.0:
            status = "Ufuk Rendah Terbuka"
        elif el <= 1.2:
            status = "Halangan Rendah (Aman)"
        else:
            status = "Halangan Tinggi (Waspada)"
        result.append({
            "no": num,
            "col_x": col_x,
            "az": az,
            "el": el,
            "dms": dms,
            "delta_hakiki": delta_hakiki,
            "delta_dip": delta_dip,
            "status": status,
        })
    return result


def export_csv_data(
    output_csv_path: str,
    location_name: str,
    az_center: float,
    profile_data: Dict[str, Any],
    dip_deg: Optional[float] = None,
    sampling_step: Optional[float] = None,
) -> str:
    """
    Mengekspor data numerik profil ufuk (Azimuth, Elevation, Horizon_Y) ke file CSV
    dalam format tabel yang rapi, berstandar Excel (UTF-8 BOM + auto-delimiter sep=,).
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_csv_path)), exist_ok=True)
    dip_val = float(dip_deg) if dip_deg is not None else float(profile_data.get("dip_deg", 0.0))
    table_rows = _prepare_table_rows(profile_data, dip_val, sampling_step)

    with open(output_csv_path, "w", encoding="utf-8-sig") as f:
        f.write("sep=,\n")
        f.write("TABEL DATA NUMERIK PROFIL UFUK MAR'I BERBASIS COMPUTER VISION\n")
        safe_loc = location_name.replace('"', '""')
        f.write(f"Pos Observasi Falak,\"{safe_loc}\"\n")
        f.write(f"Azimut Bidikan Utama,\"{az_center:.2f}° (Barat)\"\n")
        f.write(f"Kerendahan Ufuk Laut Dip,\"-{dip_val:.4f}°\"\n")
        f.write(f"Waktu Ekspor,\"{time.strftime('%Y-%m-%d %H:%M:%S')} WIB\"\n")
        f.write("\n")
        f.write("No,Kolom (Pixel X),Azimut (°),Elevasi Halangan (°),Elevasi (DMS),Selisih Hakiki (Δ0°),Selisih Laut (ΔDip),Status Kelayakan Rukyat\n")
        for r in table_rows:
            f.write(
                f"{r['no']},{r['col_x']},{r['az']:.4f},{r['el']:+.4f},\"{r['dms']}\","
                f"{r['delta_hakiki']:+.4f},{r['delta_dip']:+.4f},\"{r['status']}\"\n"
            )

    return output_csv_path


def export_excel_data(
    output_excel_path: str,
    location_name: str,
    az_center: float,
    profile_data: Dict[str, Any],
    dip_deg: Optional[float] = None,
    sampling_step: Optional[float] = None,
) -> str:
    """
    Mengekspor data numerik profil ufuk ke file Excel (.xlsx) dengan format tabel
    profesional, grid border, header berwarna, auto-width, dan filter aktif.
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    os.makedirs(os.path.dirname(os.path.abspath(output_excel_path)), exist_ok=True)
    dip_val = float(dip_deg) if dip_deg is not None else float(profile_data.get("dip_deg", 0.0))
    table_rows = _prepare_table_rows(profile_data, dip_val, sampling_step)

    wb = openpyxl.Workbook()
    ws = wb.active
    if ws is None:
        ws = wb.create_sheet("Profil Ufuk Mar'i")
    else:
        ws.title = "Profil Ufuk Mar'i"
    ws.views.sheetView[0].showGridLines = True

    font_title = Font(name="Segoe UI", size=13, bold=True, color="FFFFFF")
    fill_title = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")

    font_meta_lbl = Font(name="Segoe UI", size=10, bold=True, color="334155")
    font_meta_val = Font(name="Segoe UI", size=10, bold=False, color="0F172A")
    fill_meta = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

    font_header = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    fill_header = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")

    font_data = Font(name="Consolas", size=10, color="0F172A")
    fill_zebra = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    fill_white = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    align_center = Alignment(horizontal="center", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")

    # Title Banner (Row 1)
    ws.merge_cells("A1:H1")
    cell_a1 = ws["A1"]
    cell_a1.value = "TABEL DATA NUMERIK PROFIL UFUK MAR'I BERBASIS COMPUTER VISION"
    cell_a1.font = font_title
    cell_a1.fill = fill_title
    cell_a1.alignment = align_center
    ws.row_dimensions[1].height = 28

    # Metadata (Rows 2 - 5)
    metadata = [
        ("Pos Observasi Falak", location_name),
        ("Azimut Bidikan Utama", f"{az_center:.2f}° (Barat)"),
        ("Kerendahan Ufuk Laut (Dip)", f"-{dip_val:.4f}°"),
        ("Waktu Ekspor Data", f"{time.strftime('%Y-%m-%d %H:%M:%S')} WIB"),
    ]
    for row_idx, (lbl, val) in enumerate(metadata, start=2):
        ws.row_dimensions[row_idx].height = 20
        c_lbl = ws.cell(row=row_idx, column=1, value=lbl)
        c_lbl.font = font_meta_lbl
        c_lbl.fill = fill_meta
        c_lbl.border = thin_border

        ws.merge_cells(start_row=row_idx, start_column=2, end_row=row_idx, end_column=8)
        c_val = ws.cell(row=row_idx, column=2, value=val)
        c_val.font = font_meta_val
        c_val.alignment = align_left
        for col_i in range(2, 9):
            ws.cell(row=row_idx, column=col_i).border = thin_border

    # Row 6 blank
    ws.row_dimensions[6].height = 10

    # Table Headers (Row 7)
    headers = [
        "No",
        "Kolom (Pixel X)",
        "Azimut (°)",
        "Elevasi Halangan (°)",
        "Elevasi (DMS)",
        "Selisih Hakiki (Δ0°)",
        "Selisih Laut (ΔDip)",
        "Status Kelayakan Rukyat",
    ]
    header_row = 7
    ws.row_dimensions[header_row].height = 26
    for col_idx, h_text in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=h_text)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_center
        cell.border = thin_border

    # Status styles
    status_styles = {
        "Sangat Terbuka (Bebas)": (
            PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid"),
            Font(name="Segoe UI", size=10, bold=True, color="166534"),
        ),
        "Ufuk Rendah Terbuka": (
            PatternFill(start_color="E0F2FE", end_color="E0F2FE", fill_type="solid"),
            Font(name="Segoe UI", size=10, bold=True, color="0369A1"),
        ),
        "Halangan Rendah (Aman)": (
            PatternFill(start_color="E0F2FE", end_color="E0F2FE", fill_type="solid"),
            Font(name="Segoe UI", size=10, bold=True, color="0284C7"),
        ),
        "Halangan Tinggi (Waspada)": (
            PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid"),
            Font(name="Segoe UI", size=10, bold=True, color="92400E"),
        ),
    }

    current_row = header_row + 1
    for r in table_rows:
        ws.row_dimensions[current_row].height = 20
        row_fill = fill_white if (r["no"] % 2 == 1) else fill_zebra

        # No
        c_no = ws.cell(row=current_row, column=1, value=r["no"])
        c_no.alignment = align_center

        # Kolom X
        c_col = ws.cell(row=current_row, column=2, value=r["col_x"])
        c_col.alignment = align_center

        # Azimut
        c_az = ws.cell(row=current_row, column=3, value=round(r["az"], 4))
        c_az.alignment = align_right
        c_az.number_format = '0.0000"°"'

        # Elevasi
        c_el = ws.cell(row=current_row, column=4, value=round(r["el"], 4))
        c_el.alignment = align_right
        c_el.number_format = '+0.0000"°";-0.0000"°";0.0000"°"'

        # DMS
        c_dms = ws.cell(row=current_row, column=5, value=r["dms"])
        c_dms.alignment = align_center

        # Selisih Hakiki
        c_dh = ws.cell(row=current_row, column=6, value=round(r["delta_hakiki"], 4))
        c_dh.alignment = align_right
        c_dh.number_format = '+0.0000"°";-0.0000"°";0.0000"°"'

        # Selisih Dip
        c_dd = ws.cell(row=current_row, column=7, value=round(r["delta_dip"], 4))
        c_dd.alignment = align_right
        c_dd.number_format = '+0.0000"°";-0.0000"°";0.0000"°"'

        # Status
        st = r["status"]
        c_st = ws.cell(row=current_row, column=8, value=st)
        c_st.alignment = align_center
        if st in status_styles:
            c_st.fill, c_st.font = status_styles[st]
        else:
            c_st.font = font_data
            c_st.fill = row_fill

        for col_idx in range(1, 8):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.font = font_data
            cell.fill = row_fill
            cell.border = thin_border
        c_st.border = thin_border

        current_row += 1

    last_data_row = current_row - 1

    # Auto Filter
    ws.auto_filter.ref = f"A{header_row}:H{last_data_row}"

    # Auto column width
    for col in ws.columns:
        col_idx = col[0].column
        if not isinstance(col_idx, int):
            continue
        col_letter = get_column_letter(col_idx)
        max_len = 0
        for cell in col:
            if cell.row < header_row:
                continue
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    wb.save(output_excel_path)
    return output_excel_path
