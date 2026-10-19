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

from flask import Flask, request, jsonify, send_file, render_template

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.cv_engine import HorizonDetector
from core.falak_calc import calculate_dip, classify_obstacle, format_dms
from core.report_generator import export_pdf_report, export_csv_data, export_excel_data
from core.sample_generator import generate_synthetic_horizon
from core.compass_service import compass_service

# Template UI dipecah ke web/templates agar berkas ini tetap fokus pada API.
# Saat dibungkus PyInstaller, aset berada di direktori sementara _MEIPASS.
if getattr(sys, "frozen", False):
    APP_BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
else:
    APP_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(APP_BASE_DIR, "web")

app = Flask(
    __name__,
    template_folder=os.path.join(WEB_DIR, "templates"),
    static_folder=os.path.join(WEB_DIR, "static"),
)
# Batasi payload mentah untuk mencegah foto tak sengaja berukuran ekstrem.
# Klien resmi mengirim maksimum 2560 px, tetapi API tetap menerima gambar dari
# integrasi lain sampai batas yang aman ini.
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024
app.jinja_loader.searchpath.insert(0, os.path.join(WEB_DIR, "templates"))
detector = HorizonDetector()
compass_service.start()

# Cache analisis terakhir
LAST_ANALYSIS = {}
PDF_CACHE = {"path": None, "hash": None, "pages": []}



_cached_camera_check = {"time": 0, "result": None}

@app.route("/api/check_cameras", methods=["GET"])
def api_check_cameras():
    global _cached_camera_check
    now = time.time()
    if _cached_camera_check["result"] and (now - _cached_camera_check["time"] < 3.0):
        return jsonify(_cached_camera_check["result"])

    result = {
        "cameras": [],
        "digicam_state": "not_detected",
        "message": ""
    }
    try:
        no_win = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        if sys.platform == "darwin":
            scan = subprocess.run(
                ["system_profiler", "SPCameraDataType"],
                capture_output=True, text=True, timeout=8,
            ).stdout
            names = [
                line.strip()[:-1] for line in scan.splitlines()
                if line.startswith("    ") and not line.startswith("      ") and line.strip().endswith(":")
            ]
            for name in names:
                result["cameras"].append({"caption": name, "device_id": ""})
            if "GENERAL-A-VIDEO" in scan or "VendorID_6975 ProductID_8197" in scan:
                result["digicam_state"] = "ready"
                result["message"] = "GENERAL-A-VIDEO terdeteksi macOS sebagai kamera UVC/PC Camera."
            _cached_camera_check = {"time": now, "result": result}
            return jsonify(result)

        if os.name != "nt":
            _cached_camera_check = {"time": now, "result": result}
            return jsonify(result)

        cmd = ["wmic", "path", "Win32_PnPEntity", "where", "DeviceID like \"%1B3F%\" and Status=\"OK\"", "get", "Caption,DeviceID", "/format:csv"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3, creationflags=no_win)
        out = r.stdout
        if "PID_2005" in out or "GENERAL-A-VIDEO" in out:
            result["digicam_state"] = "ready"
            result["message"] = "Kamera saku (GENERAL-A-VIDEO) aktif dalam mode Kamera PC/Webcam."
        elif "PID_8301" in out or "Mass Storage" in out:
            result["digicam_state"] = "storage_mode"
            result["message"] = "Kamera saku terdeteksi dalam mode Penyimpanan Massal."

        cmd_cam = ["wmic", "path", "Win32_PnPEntity", "where", "PNPClass=\"Camera\" and Status=\"OK\"", "get", "Caption,DeviceID", "/format:csv"]
        r_cam = subprocess.run(cmd_cam, capture_output=True, text=True, timeout=3, creationflags=no_win)
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

    _cached_camera_check = {"time": now, "result": result}
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
    return render_template("app.html")


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
    fig.subplots_adjust(left=0.115, right=0.975, top=0.87, bottom=0.17)

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
        # Tempatkan label di sisi berlawanan dari garis agar tidak menutupi
        # kurva dan tidak terpotong tepi grafik.
        az_min_view = float(az_arr[0])
        az_max_view = float(az_arr[-1])
        span_view = max(1e-6, az_max_view - az_min_view)
        to_right = (target_az - az_min_view) < span_view * 0.5
        dx = span_view * 0.035 * (1 if to_right else -1)
        ax.annotate(
            f"Halangan: {t_alt:+.2f}°",
            xy=(target_az, t_alt),
            xytext=(target_az + dx, t_alt + 0.9),
            fontsize=8,
            fontweight="bold",
            color="#fae8ff",
            ha="left" if to_right else "right",
            va="bottom",
            bbox=dict(boxstyle="round,pad=0.28", facecolor="#1e1b4b", edgecolor="#c026d3", alpha=0.92),
            arrowprops=dict(arrowstyle="-", color="#c026d3", linewidth=0.8, alpha=0.8),
            zorder=7,
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

    # Skala sumbu Y menyesuaikan data agar kurva rendah tidak menempel di dasar
    el_max = float(np.max(el_arr)) if el_arr.size else 0.0
    y_top = max(5.0, min(20.0, math.ceil((el_max + 1.0) / 5.0) * 5.0))
    ax.set_ylim(0.0, y_top)
    y_step = 5.0 if y_top >= 15.0 else (2.5 if y_top >= 7.5 else 1.0)
    y_ticks = list(np.arange(0.0, y_top + 1e-6, y_step))

    def format_y_tick(val):
        cm = 30.0 * math.tan(math.radians(abs(val)))
        return f"+{val:.0f}° / {cm:.2f} cm".replace(".", ",") if val > 0 else "0° / 0,00 cm"

    y_labels = [format_y_tick(y) for y in y_ticks]
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels, fontsize=8, color="#f8fafc")

    ax.set_xlabel("Rentang Azimut Bidikan (°)", fontsize=8.5, fontweight="bold", color="#94a3b8", labelpad=2)
    ax.set_ylabel("Elevasi Relatif / Skala Falak (° / cm)", fontsize=8.5, fontweight="bold", color="#94a3b8", labelpad=4)
    ax.set_title("Grafik Elevasi Relatif vs Azimut", fontsize=9.5, fontweight="bold", color="#38bdf8", pad=8)
    ax.grid(True, linestyle="--", alpha=0.35, color="#334155", linewidth=0.7)
    ax.tick_params(axis="both", length=2.5, pad=2)
    for spine in ax.spines.values():
        spine.set_color("#334155")
        spine.set_linewidth(0.8)
    ax.legend(loc="upper right", fontsize=7, framealpha=0.9, borderpad=0.4,
              labelspacing=0.35, handlelength=1.6)

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
    # Guard backend untuk input API non-UI. Pertahankan detail sebanyak mungkin
    # (maksimum 4096 px), jauh di atas batas lama 1280 px.
    max_backend_dim = 4096
    if max(h, w) > max_backend_dim or (h * w) > 20_000_000:
        scale = min(max_backend_dim / float(max(h, w)), math.sqrt(20_000_000 / float(h * w)))
        image_bgr = cv2.resize(
            image_bgr,
            (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
            interpolation=cv2.INTER_AREA,
        )
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
    _, raw_buf = cv2.imencode(".jpg", image_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    raw_image_b64 = "data:image/jpeg;base64," + base64.b64encode(raw_buf).decode("utf-8")

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
        "raw_base64": raw_image_b64,
        "horizon_y": [float(v) for v in horizon_y],
        "image_width": int(w),
        "image_height": int(h),
    })


@app.route("/api/rename_objects", methods=["POST"])
def api_rename_objects():
    """Terapkan nama objek manual ke overlay gambar & data laporan (PDF/Excel)."""
    global LAST_ANALYSIS
    try:
        if not LAST_ANALYSIS:
            return jsonify({"error": "Belum ada data analisis aktif"}), 400

        data = request.get_json(force=True) or {}
        renamed = data.get("objects") or []
        if not isinstance(renamed, list) or not renamed:
            return jsonify({"error": "Daftar objek tidak valid"}), 400

        profile_data = LAST_ANALYSIS["profile_data"]
        obstacles = profile_data.get("prominent_obstacles", []) or []

        # Petakan berdasarkan indeks; label diambil dari input pengguna
        for i, obs in enumerate(obstacles):
            if i < len(renamed):
                new_label = str(renamed[i].get("label", "")).strip()
                if new_label:
                    obs["label"] = new_label
                    az_s = obs.get("az_start")
                    az_e = obs.get("az_end")
                    if isinstance(az_s, (int, float)) and isinstance(az_e, (int, float)) and abs(float(az_e) - float(az_s)) > 0.05:
                        az_txt = f"{float(az_s):.2f}-{float(az_e):.2f} deg"
                    else:
                        az_txt = f"{obs['azimuth']:.2f} deg"
                    obs["text"] = f"{new_label}: Az {az_txt} | Alt {obs['elevation']:+.2f} deg"

        # Render ulang overlay dengan nama objek terbaru
        overlay_bgr = detector.render_overlay(
            image_bgr=LAST_ANALYSIS["image_bgr"],
            horizon_y=LAST_ANALYSIS["horizon_y"],
            azimuths=LAST_ANALYSIS["profile_data"]["azimuths"],
            elevations=LAST_ANALYSIS["profile_data"]["elevations"],
            target_az=LAST_ANALYSIS["target_analysis"].get("target_az"),
            dip_deg=profile_data["dip_deg"],
            az_center=LAST_ANALYSIS["azimuth"],
            hfov=LAST_ANALYSIS["hfov"],
            vfov=LAST_ANALYSIS["vfov"],
            tilt_center=LAST_ANALYSIS["tilt"],
            prominent_obstacles=obstacles,
            show_prominent_peaks=True,
        )
        LAST_ANALYSIS["overlay_bgr"] = overlay_bgr

        _, ov_buf = cv2.imencode(".jpg", overlay_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        overlay_b64 = "data:image/jpeg;base64," + base64.b64encode(ov_buf).decode("utf-8")

        return jsonify({
            "success": True,
            "overlay_base64": overlay_b64,
            "prominent_objects": obstacles,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


def _render_current_web_analysis(target_az=None):
    """Render payload web terbaru dari state analisis yang telah dikoreksi."""
    prof = LAST_ANALYSIS["profile_data"]
    az_arr = np.asarray(prof["azimuths"], dtype=np.float64)
    el_arr = np.asarray(prof["elevations"], dtype=np.float64)
    if target_az is None:
        target_az = LAST_ANALYSIS["target_analysis"].get("target_az", LAST_ANALYSIS["azimuth"])
    t_idx = int(np.argmin(np.abs(az_arr - float(target_az))))
    target_alt = float(el_arr[t_idx])
    target_analysis = classify_obstacle(target_alt, prof["dip_deg"])
    target_analysis.update(target_az=float(target_az), target_alt=target_alt, dip_deg=prof["dip_deg"])
    overlay = detector.render_overlay(
        image_bgr=LAST_ANALYSIS["image_bgr"], horizon_y=LAST_ANALYSIS["horizon_y"],
        azimuths=az_arr, elevations=el_arr, target_az=float(target_az), dip_deg=prof["dip_deg"],
        az_center=LAST_ANALYSIS["azimuth"], hfov=LAST_ANALYSIS["hfov"], vfov=LAST_ANALYSIS["vfov"],
        tilt_center=LAST_ANALYSIS["tilt"], prominent_obstacles=prof.get("prominent_obstacles", []),
        show_prominent_peaks=True,
    )
    LAST_ANALYSIS["overlay_bgr"] = overlay
    LAST_ANALYSIS["target_analysis"] = target_analysis
    _, buf = cv2.imencode(".jpg", overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    step = max(1, len(az_arr) // 320)
    indices = list(range(0, len(az_arr), step))
    if indices[-1] != len(az_arr) - 1:
        indices.append(len(az_arr) - 1)
    return {
        "success": True,
        "overlay_base64": "data:image/jpeg;base64," + base64.b64encode(buf).decode("utf-8"),
        "plot_base64": fast_render_plot_image(az_arr, el_arr, prof["dip_deg"], float(target_az), target_alt),
        "target_analysis": target_analysis,
        "profile_curve": {"az": [float(az_arr[i]) for i in indices], "el": [float(el_arr[i]) for i in indices]},
        "prominent_objects": prof.get("prominent_obstacles", []),
        "horizon_y": [float(v) for v in LAST_ANALYSIS["horizon_y"]],
    }


@app.route("/api/update_skyline", methods=["POST"])
def api_update_skyline():
    """Simpan Pen Tool, resize rentang H, dan objek manual dari viewer web."""
    global LAST_ANALYSIS
    if not LAST_ANALYSIS:
        return jsonify({"error": "Belum ada analisis aktif"}), 400
    try:
        data = request.get_json(force=True) or {}
        edited = np.asarray(data.get("horizon_y", []), dtype=np.float64)
        width = int(LAST_ANALYSIS["w"])
        if edited.ndim != 1 or len(edited) != width or not np.all(np.isfinite(edited)):
            return jsonify({"error": "Data garis ufuk tidak valid"}), 400
        edited = np.clip(edited, 0, LAST_ANALYSIS["h"] - 1)
        profile = detector.compute_horizon_profile(
            horizon_y=edited, img_w=width, img_h=LAST_ANALYSIS["h"],
            az_center=LAST_ANALYSIS["azimuth"], hfov=LAST_ANALYSIS["hfov"],
            vfov=LAST_ANALYSIS["vfov"], tilt_center=LAST_ANALYSIS["tilt"],
            elevation_m=LAST_ANALYSIS["altitude"],
        )
        supplied = data.get("objects") or []
        az_arr, el_arr = profile["azimuths"], profile["elevations"]
        normalized = []
        for i, incoming in enumerate(supplied):
            obj = dict(incoming or {})
            xs = max(0, min(width - 2, int(round(float(obj.get("x_start", obj.get("x", 0)))))))
            xe = max(xs + 1, min(width - 1, int(round(float(obj.get("x_end", obj.get("x", xs + 1)))))))
            x = max(xs, min(xe, int(round(float(obj.get("x", (xs + xe) / 2))))))
            obj.update(
                id=i + 1, x=x, x_start=xs, x_end=xe,
                y=int(round(float(edited[x]))),
                azimuth=float(az_arr[x]), az_start=float(az_arr[xs]), az_end=float(az_arr[xe]),
                az_span=float(az_arr[xe] - az_arr[xs]), elevation=float(el_arr[x]),
            )
            obj["label"] = str(obj.get("label") or obj.get("object_class") or f"Objek {i+1}")
            obj["text"] = f"{obj['label']}: Az {obj['az_start']:.2f}-{obj['az_end']:.2f} deg | Alt {obj['elevation']:+.2f} deg"
            normalized.append(obj)
        profile["prominent_obstacles"] = normalized
        LAST_ANALYSIS["horizon_y"] = edited
        LAST_ANALYSIS["profile_data"] = profile
        return jsonify(_render_current_web_analysis(data.get("target_az")))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


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


def _apply_object_labels(renamed_objects) -> None:
    """Terapkan nama objek manual dari klien ke data analisis aktif (dipakai PDF/Excel)."""
    global LAST_ANALYSIS
    if not LAST_ANALYSIS or not renamed_objects:
        return
    profile_data = LAST_ANALYSIS.get("profile_data") or {}
    obstacles = profile_data.get("prominent_obstacles") or []
    for i, obs in enumerate(obstacles):
        if i < len(renamed_objects):
            new_label = str((renamed_objects[i] or {}).get("label", "")).strip()
            if new_label:
                obs["label"] = new_label
                az_s = obs.get("az_start")
                az_e = obs.get("az_end")
                if isinstance(az_s, (int, float)) and isinstance(az_e, (int, float)) and abs(float(az_e) - float(az_s)) > 0.05:
                    az_txt = f"{float(az_s):.2f}-{float(az_e):.2f} deg"
                else:
                    az_txt = f"{obs.get('azimuth', 0.0):.2f} deg"
                obs["text"] = f"{new_label}: Az {az_txt} | Alt {obs.get('elevation', 0.0):+.2f} deg"


def _generate_current_pdf_path(location_name=None, observer_name=None, observer_notes=None, recommendation_text=None, report_title=None, instansi_name=None, renamed_objects=None) -> str:
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
    rep_title = report_title or "BERITA ACARA & LAPORAN PEMETAAN PROFIL UFUK MAR'I"
    inst_name = instansi_name or "FAKULTAS SYARIAH - LABORATORIUM ASTRONOMI & ILMU FALAK"

    hfov_val = float(LAST_ANALYSIS.get("hfov", 60.0))
    vfov_val = float(LAST_ANALYSIS.get("vfov", 36.0))

    # Terapkan nama objek manual sebelum dokumen dibuat
    _apply_object_labels(renamed_objects)

    # Render overlay khusus laporan: TANPA garis merah meridian sasaran
    # agar dokumentasi citra di dalam laporan PDF bersih dan rapi
    report_overlay_bgr = detector.render_overlay(
        image_bgr=LAST_ANALYSIS["image_bgr"],
        horizon_y=LAST_ANALYSIS["horizon_y"],
        azimuths=LAST_ANALYSIS["profile_data"]["azimuths"],
        elevations=LAST_ANALYSIS["profile_data"]["elevations"],
        target_az=ta.get("target_az"),
        dip_deg=LAST_ANALYSIS["profile_data"]["dip_deg"],
        az_center=LAST_ANALYSIS["azimuth"],
        hfov=hfov_val,
        vfov=vfov_val,
        tilt_center=LAST_ANALYSIS["tilt"],
        prominent_obstacles=LAST_ANALYSIS["profile_data"].get("prominent_obstacles", []),
        show_prominent_peaks=True,
        show_target_meridian=False,
    )

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
        overlay_img_bgr=report_overlay_bgr,
        target_analysis=ta,
        observer_notes=desc,
        recommendation_text=rec,
        instansi_name=inst_name,
        observer_name=obs,
        report_title=rep_title,
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
        rep_title = data.get("report_title") or request.args.get("title")
        inst_name = data.get("instansi_name") or request.args.get("inst")
        renamed_objs = data.get("objects")

        pdf_path = _generate_current_pdf_path(
            location_name=loc,
            observer_name=obs,
            observer_notes=notes,
            recommendation_text=rec,
            report_title=rep_title,
            instansi_name=inst_name,
            renamed_objects=renamed_objs,
        )
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
        rep_title = request.args.get("title")
        inst_name = request.args.get("inst")
        pdf_path = _generate_current_pdf_path(
            location_name=loc,
            observer_name=obs,
            report_title=rep_title,
            instansi_name=inst_name,
        )
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
