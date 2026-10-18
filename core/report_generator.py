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
    PageBreak,
)

from core.falak_calc import format_dms

CALIB_DEG_CM = {
    0: "0,00", 1: "0,52", 2: "1,04", 3: "1,57", 4: "2,09",
    5: "2,62", 6: "3,15", 7: "3,68", 8: "4,21", 9: "4,75",
    10: "5,28", 11: "5,83", 12: "6,37", 13: "6,92", 14: "7,47",
    15: "8,03", 16: "8,60", 17: "9,17", 18: "9,74", 19: "10,32", 20: "10,91"
}

def get_elev_cm_str(deg: float) -> str:
    a = abs(float(deg))
    if a < 0.001:
        return "0,00"
    int_a = int(round(a))
    if abs(a - int_a) < 0.05 and int_a in CALIB_DEG_CM:
        return CALIB_DEG_CM[int_a]
    val = 30.0 * math.tan(math.radians(a))
    floored = math.floor(val * 100) / 100.0
    return f"{floored:.2f}".replace(".", ",")


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
    observer_name: str = "",
    report_title: str = "BERITA ACARA & LAPORAN PEMETAAN PROFIL UFUK MAR'I",
    sub_title: str = "Instrumen Falak Digital Berbasis Computer Vision & Analisis Kelayakan Tempat Rukyat",
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

    # Render grafik profil ufuk khusus untuk laporan PDF (resolusi tajam 220 DPI)
    # matplotlib dimuat LAZY (hanya saat laporan benar-benar dibuat) agar
    # waktu start aplikasi tidak membayar beban impor matplotlib.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    azimuths = profile_data["azimuths"]
    elevations = profile_data["elevations"]

    fig, ax = plt.subplots(figsize=(8.5, 3.6), dpi=220)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#f9f9fb")

    # Kurva kontur digambar polos tanpa label legend dan tanpa garis penanda,
    # sesuai permintaan: tampilan grafik bersih tanpa kurva merah / garis ungu.
    ax.plot(azimuths, elevations, color="#404040", linewidth=1.6)
    ax.fill_between(azimuths, np.maximum(0, elevations), 0, color="#9e9e9e", alpha=0.18)

    # Titik sasaran jika ada (tanpa garis axvline ungu, tanpa anotasi)
    if target_analysis and "target_az" in target_analysis:
        t_az = target_analysis["target_az"]
        t_alt = target_analysis.get("alt_obstacle", target_analysis.get("target_alt", 0.0))
        ax.scatter([t_az], [t_alt], color="#404040", s=45, zorder=5)
        ax.scatter([t_az], [t_alt], color="#ffffff", s=15, zorder=6)

    # Skala sumbu X (Azimut)
    az_min = float(azimuths[0])
    az_max = float(azimuths[-1])
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

    def format_az_tick_report(val):
        deg = val % 360.0 if val >= 360.0 else val
        s = f"{deg:.0f}°"
        if abs((val % 360.0) - 270.0) < 0.2:
            s += " (Barat)"
        return s

    x_labels = [format_az_tick_report(x) for x in x_ticks]
    ax.set_xticks(x_ticks)
    ax.set_xticklabels(x_labels, fontsize=8)

    # Skala sumbu Y (Elevasi 0 s.d 20 derajat) + cm sesuai kalibrasi acuan falak 30cm
    ax.set_ylim(0.0, 20.0)
    calib_deg_cm = {
        0: "0,00", 1: "0,52", 2: "1,04", 3: "1,57", 4: "2,09",
        5: "2,62", 6: "3,15", 7: "3,68", 8: "4,21", 9: "4,75",
        10: "5,28", 11: "5,83", 12: "6,37", 13: "6,92", 14: "7,47",
        15: "8,03", 16: "8,60", 17: "9,17", 18: "9,74", 19: "10,32", 20: "10,91"
    }
    y_ticks = [0, 5, 10, 15, 20]
    y_labels = [f"+{y}° / {calib_deg_cm[y]} cm" if y > 0 else "0° / 0,00 cm" for y in y_ticks]
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels, fontsize=8)

    ax.set_xlabel("Rentang Azimut Bidikan (°)", fontsize=9, fontweight="bold", color="#000000")
    ax.set_ylabel("Elevasi Relatif / Skala Falak (° / cm)", fontsize=9, fontweight="bold", color="#000000")
    ax.set_title("Grafik Elevasi Relatif vs Azimut", fontsize=10, fontweight="bold", color="#000000", pad=6)
    ax.grid(True, linestyle="--", alpha=0.5, color="#bdbdbd")
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
    inst_str = (instansi_name or "").strip().upper()
    title_str = (report_title or "BERITA ACARA & LAPORAN PEMETAAN PROFIL UFUK MAR'I").strip().upper()
    sub_str = (sub_title or "").strip()

    if inst_str:
        elements.append(Paragraph(inst_str, title_style))
        elements.append(Spacer(1, 2))
    if title_str:
        elements.append(Paragraph(title_str, ParagraphStyle("H2", parent=title_style, fontSize=12, leading=14, textColor=colors.black)))
    if sub_str:
        elements.append(Paragraph(sub_str, subtitle_style))
    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.black, spaceBefore=1, spaceAfter=8))

    # Waktu Pengamatan
    now_str = time.strftime("%d %B %Y - %H:%M:%S WIB")
    elements.append(Paragraph(f"<b>Waktu Ekstraksi & Verifikasi:</b> {now_str}", body_style))
    elements.append(Spacer(1, 6))

    # TABEL 1: PARAMETER TITIK PENGAMATAN & OPTIK KAMERA
    elements.append(Paragraph("I. PARAMETER BIDIKAN", section_style))

    dms_lat = format_dms(latitude, is_lat=True)
    dms_lon = format_dms(longitude, is_lon=True)
    stats = profile_data.get("stats", {})
    t_alt_val = target_analysis.get("target_alt", target_analysis.get("alt_obstacle", 0.0)) if target_analysis else 0.0
    elev_str_val = f"{t_alt_val:+.2f}° / {get_elev_cm_str(t_alt_val)} cm".replace(".", ",")

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
            Paragraph("<b>Rentang Azimut:</b>", body_style),
            Paragraph(f"{stats.get('az_range_min', 0):.2f}° s.d. {stats.get('az_range_max', 0):.2f}°", body_style),
        ],
        [
            Paragraph("<b>Bujur Tempat (lambda):</b>", body_style),
            Paragraph(f"{dms_lon} ({longitude:+.5f}°)", body_style),
            Paragraph("<b>Sudut Elevasi / cm:</b>", body_style),
            Paragraph(elev_str_val, body_style),
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
    elements.append(Spacer(1, 4))

    # BAGIAN VISUAL: FOTO OVERLAY & GRAFIK (DIKEMBALIKAN KE BAGIAN II)
    elements.append(Paragraph("II. CITRA & GRAFIK ", section_style))
    elements.append(Paragraph(
        "<b>Referensi elevasi:</b> titik terendah profil ufuk ditetapkan sebagai 0°. "
        "Elevasi objek menyatakan tinggi sudut relatif di atas baseline tersebut.",
        body_style,
    ))
    elements.append(Spacer(1, 4))

    # Ukuran gambar di laporan sesuai dengan ukuran dan aspek rasio gambar hasil deteksi asli agar tidak gepeng/tertarik
    orig_h, orig_w = overlay_img_bgr.shape[:2]
    aspect_img = orig_h / max(1, orig_w)

    w_img = 490.0
    h_img = round(w_img * aspect_img)
    max_h_img = 265.0
    if h_img > max_h_img:
        h_img = max_h_img
        w_img = round(h_img / aspect_img)

    w_plot = 490.0
    h_plot = 175.0

    img_flowable = RLImage(temp_overlay_path, width=w_img, height=h_img)
    img_flowable.hAlign = "CENTER"
    elements.append(img_flowable)
    elements.append(Spacer(1, 4))

    plot_flowable = RLImage(temp_plot_path, width=w_plot, height=h_plot)
    plot_flowable.hAlign = "CENTER"
    elements.append(plot_flowable)
    elements.append(Spacer(1, 4))

    # PINDAH KE HALAMAN 2: DAFTAR OBJEK MENONJOL, REKOMENDASI & PENGESAHAN
    elements.append(PageBreak())

    # TABEL OBJEK HALANGAN MENONJOL (PROMINENT OBSTACLES)
    elements.append(Paragraph("III. DAFTAR OBJEK", section_style))

    body_center = ParagraphStyle("DocBodyCenter", parent=body_style, alignment=1)
    header_style = ParagraphStyle("DocHeaderCenter", parent=body_style, fontName="Helvetica-Bold", alignment=1)

    obs_table_data = [
        [
            Paragraph("<b>No.</b>", header_style),
            Paragraph("<b>Objek</b>", header_style),
            Paragraph("<b>Azimut</b>", header_style),
            Paragraph("<b>Sudut Elevasi / cm</b>", header_style),
        ]
    ]

    prom_obs = profile_data.get("prominent_obstacles", [])
    if prom_obs:
        for obs in prom_obs:
            obs_id = obs.get("id", len(obs_table_data))
            obs_label = obs.get("label", f"Objek {obs_id}")
            az_start_v = obs.get("az_start")
            az_end_v = obs.get("az_end")
            if isinstance(az_start_v, (int, float)) and isinstance(az_end_v, (int, float)) and abs(float(az_end_v) - float(az_start_v)) > 0.05:
                az_str = f"{float(az_start_v):.2f}° – {float(az_end_v):.2f}°".replace(".", ",")
            else:
                az_str = f"{obs.get('azimuth', 0.0):.2f}°".replace(".", ",")
            alt_val = obs.get("elevation", 0.0)
            cm_val = get_elev_cm_str(alt_val)
            elev_cm_str = f"{alt_val:+.2f}° / {cm_val} cm".replace(".", ",")
            obs_table_data.append([
                Paragraph(f"{obs_id}.", body_center),
                Paragraph(obs_label, body_center),
                Paragraph(az_str, body_center),
                Paragraph(elev_cm_str, body_center),
            ])
    else:
        obs_table_data.append([
            Paragraph("-", body_center),
            Paragraph("Tidak terdeteksi objek menonjol signifikan", body_center),
            Paragraph("-", body_center),
            Paragraph("-", body_center),
        ])

    t_obs = Table(obs_table_data, colWidths=[45, 165, 150, 160])
    t_obs.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    elements.append(t_obs)
    elements.append(Spacer(1, 14))

    # BAGIAN CATATAN & REKOMENDASI KELAYAKAN
    elements.append(Paragraph("IV. CATATAN & REKOMENDASI", section_style))

    rec_content = recommendation_text.strip() if recommendation_text.strip() else (
        target_analysis.get("recommendation", "Lokasi memiliki keterbukaan ufuk yang baik.")
        if target_analysis else "Lokasi pengamatan belum dianalisis secara spesifik."
    )
    notes_content = observer_notes.strip() if observer_notes.strip() else "Tidak ada catatan tambahan kondisi atmosfer/lapangan."

    obs_name_str = observer_name.strip() if observer_name and observer_name.strip() else "Tim Falak & Astronomi"

    rec_table_data = [
        [
            Paragraph("<b>Nama Lokasi</b>", body_style),
            Paragraph(location_name or "Pos Observasi Falak Lapangan", body_style),
        ],
        [
            Paragraph("<b>Petugas Pengamat:</b>", body_style),
            Paragraph(obs_name_str, body_style),
        ],
        [
            Paragraph("<b>Evaluasi</b>", body_style),
            Paragraph(rec_content, body_style),
        ],
        [
            Paragraph("<b>Catatan Pengamat:</b>", body_style),
            Paragraph(notes_content, body_style),
        ],
    ]

    t_rec = Table(rec_table_data, colWidths=[160, 360])
    t_rec.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f9f9f9")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    elements.append(t_rec)

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
    Mengekspor data numerik profil ufuk ke file CSV dengan format 5 kolom ringkas
    sesuai tampilan tabel preview (No, Azimut, Elevasi, Data Lokasi, Status Kelayakan).
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
        f.write(f"Sudut Elevasi,\"-{dip_val:.4f}°\"\n")
        f.write(f"Waktu Ekspor,\"{time.strftime('%Y-%m-%d %H:%M:%S')} WIB\"\n")
        f.write("\n")
        f.write("No,Azimut (°),Elevasi / cm,Data Lokasi\n")
        for r in table_rows:
            cm_str = get_elev_cm_str(r['el'])
            el_cm = f"{r['el']:+.2f}° / {cm_str} cm"
            f.write(
                f"{r['no']},{r['az']:.2f},\"{el_cm}\",\"{safe_loc}\"\n"
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
    Mengekspor data numerik profil ufuk ke file Excel (.xlsx) dengan 5 kolom ringkas
    sesuai tampilan preview (No, Azimut, Elevasi, Data Lokasi, Status Kelayakan).
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

    # Title Banner (Row 1) - Merged 4 Columns (A1:D1)
    ws.merge_cells("A1:D1")
    cell_a1 = ws["A1"]
    cell_a1.value = "TABEL DATA NUMERIK PROFIL UFUK MAR'I BERBASIS COMPUTER VISION"
    cell_a1.font = font_title
    cell_a1.fill = fill_title
    cell_a1.alignment = align_center
    ws.row_dimensions[1].height = 28

    # Metadata (Rows 2 - 5) - Merged to Column D
    metadata = [
        ("Data Lokasi / Pos Observasi", location_name),
        ("Azimut Bidikan Utama", f"{az_center:.2f}° (Barat)"),
        ("Sudut Elevasi", f"-{dip_val:.4f}°"),
        ("Waktu Ekspor Data", f"{time.strftime('%Y-%m-%d %H:%M:%S')} WIB"),
    ]
    for row_idx, (lbl, val) in enumerate(metadata, start=2):
        ws.row_dimensions[row_idx].height = 20
        c_lbl = ws.cell(row=row_idx, column=1, value=lbl)
        c_lbl.font = font_meta_lbl
        c_lbl.fill = fill_meta
        c_lbl.border = thin_border

        ws.merge_cells(start_row=row_idx, start_column=2, end_row=row_idx, end_column=4)
        c_val = ws.cell(row=row_idx, column=2, value=val)
        c_val.font = font_meta_val
        c_val.alignment = align_left
        for col_i in range(2, 5):
            ws.cell(row=row_idx, column=col_i).border = thin_border

    # Row 6 blank
    ws.row_dimensions[6].height = 10

    # Table Headers (Row 7) - 4 Kolom (No, Azimut, Elevasi, Data Lokasi)
    headers = [
        "No",
        "Azimut (°)",
        "Elevasi / cm",
        "Data Lokasi",
    ]
    header_row = 7
    ws.row_dimensions[header_row].height = 26
    for col_idx, h_text in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=h_text)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_center
        cell.border = thin_border

    current_row = header_row + 1
    for r in table_rows:
        ws.row_dimensions[current_row].height = 20
        row_fill = fill_white if (r["no"] % 2 == 1) else fill_zebra

        # No
        c_no = ws.cell(row=current_row, column=1, value=r["no"])
        c_no.alignment = align_center

        # Azimut (°)
        c_az = ws.cell(row=current_row, column=2, value=round(r["az"], 2))
        c_az.alignment = align_center
        c_az.number_format = '0.00"°"'

        # Elevasi / cm
        cm_str = get_elev_cm_str(r["el"])
        c_el = ws.cell(row=current_row, column=3, value=f"{r['el']:+.2f}° / {cm_str} cm")
        c_el.alignment = align_center

        # Data Lokasi
        c_loc = ws.cell(row=current_row, column=4, value=location_name)
        c_loc.alignment = align_center

        for col_idx in range(1, 5):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.font = font_data
            cell.fill = row_fill
            cell.border = thin_border

        current_row += 1

    last_data_row = current_row - 1

    # Auto Filter (A7:D)
    ws.auto_filter.ref = f"A{header_row}:D{last_data_row}"

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
        ws.column_dimensions[col_letter].width = max(max_len + 8, 16)

    wb.save(output_excel_path)
    return output_excel_path
