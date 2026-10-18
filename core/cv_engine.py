"""
cv_engine.py
Engine Computer Vision untuk segmentasi dan ekstraksi profil kontur ufuk mar'i.
Mengidentifikasi batas pertemuan langit (sky) dan daratan/halangan (ground/terrain)
per kolom horizontal, mengonversi ke profil elevasi sudut astronomi.
"""

from typing import Tuple, Dict, Any, Optional, List
from itertools import groupby
from operator import itemgetter
import numpy as np
import cv2
from scipy.signal import medfilt

from core.falak_calc import (
    pixel_to_azimuth_elevation,
    calculate_dip,
    classify_obstacle,
)


class HorizonDetector:
    """
    Kelas pendeteksi ufuk mar'i dengan beberapa algoritma computer vision:
    1. Gradien Vertikal (Optimal untuk senja, siluet bukit, dan ufuk rukyat)
    2. Adaptive / Otsu Thresholding (Segmentasi biner intensitas)
    3. Canny Edge + Morfologi Kontur
    """

    METHOD_GRADIENT = "Gradien Vertikal (Optimal Senja/Siluet)"
    METHOD_OTSU = "Otsu Adaptive Threshold"
    METHOD_CANNY = "Canny Edge + Morfologi"

    ALL_METHODS = [METHOD_GRADIENT, METHOD_OTSU, METHOD_CANNY]

    def __init__(self):
        self.last_horizon_y = None
        self.last_azimuths = None
        self.last_elevations = None
        self.last_bw_data = None

    def preprocess_bw(self, image_bgr: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Pengolahan citra ilmiah menggunakan OpenCV untuk akurasi maksimal:
        1. Konversi ke Grayscale (hitam-putih).
        2. CLAHE (Contrast Limited Adaptive Histogram Equalization) untuk menonjolkan
           kontras tipis batas langit mendung vs bukit/daratan.
        3. Bilateral Filter untuk menghilangkan noise sensor tanpa mengaburkan tepi batas ufuk.
        4. Otsu Adaptive Binarization untuk segmentasi biner hitam-putih.

        Returns:
            Dict dengan:
            - 'enhanced_bw': Citra grayscale kontras tinggi 3-channel BGR.
            - 'binary_bw': Citra biner hitam-putih murni 3-channel BGR.
            - 'gray': Citra 1-channel grayscale untuk kalkulasi gradien presisi.
        """
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

        # 1. CLAHE untuk mendongkrak kontras lokal
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # 2. Bilateral Filter: pereduksi noise yang menjaga ketajaman garis tepi ufuk
        # ponytail: fixed bilateral kernel (d=7); upgrade to adaptive sigma if high-ISO raw plates added
        denoised = cv2.bilateralFilter(gray, d=7, sigmaColor=40, sigmaSpace=40)
        enhanced_denoised = cv2.bilateralFilter(enhanced, d=7, sigmaColor=40, sigmaSpace=40)

        # 3. Segmentasi Biner Otsu
        _, binary = cv2.threshold(enhanced_denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        binary_clean = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        enhanced_bgr = cv2.cvtColor(enhanced_denoised, cv2.COLOR_GRAY2BGR)
        binary_bgr = cv2.cvtColor(binary_clean, cv2.COLOR_GRAY2BGR)

        return {
            "enhanced_bw": enhanced_bgr,
            "binary_bw": binary_bgr,
            "gray": denoised,
        }

    def detect_horizon(
        self,
        image_bgr: np.ndarray,
        method: str = METHOD_GRADIENT,
        threshold_offset: int = 0,
        blur_kernel: int = 5,
        smooth_window: int = 15,
        invert_mask: bool = False,
        roi_top_pct: float = 0.08,
        roi_bottom_pct: float = 0.95,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Mendeteksi batas ufuk mar'i untuk setiap kolom horizontal citra.
        Menggunakan pra-pengolahan citra hitam-putih OpenCV (CLAHE + Bilateral)
        untuk menjamin akurasi tinggi pada kondisi langit apapun.
        """
        h, w = image_bgr.shape[:2]
        if h < 20 or w < 20:
            raise ValueError("Dimensi gambar terlalu kecil untuk ekstraksi ufuk.")

        # Jalankan pra-pengolahan citra hitam-putih OpenCV
        bw_data = self.preprocess_bw(image_bgr)
        self.last_bw_data = bw_data
        gray = bw_data["gray"]

        y_min = int(h * np.clip(roi_top_pct, 0.0, 0.4))
        y_max = int(h * np.clip(roi_bottom_pct, 0.6, 1.0))
        if y_max <= y_min + 10:
            y_min, y_max = int(h * 0.1), int(h * 0.9)

        mask = np.zeros((h, w), dtype=np.uint8)
        horizon_y = np.full(w, int(h * 0.5), dtype=np.int32)

        # Deteksi kolom aktif untuk mengabaikan padding letterbox hitam dari kamera/screenshot
        col_mean = np.mean(image_bgr, axis=(0, 2))
        col_valid = col_mean > 3.0
        if np.any(col_valid):
            x_start = int(np.min(np.where(col_valid)[0]))
            x_end = int(np.max(np.where(col_valid)[0]))
        else:
            x_start, x_end = 0, w - 1

        if method == self.METHOD_GRADIENT:
            # Algoritma Multi-Spectral OpenCV + Dynamic Programming (DP) Skyline Extraction
            # 1. Konversi ke ruang warna Lab untuk mengekstraksi Luminance (L) dan opponent color b*
            #    (langit senja memiliki pendaran kuning keemasan kuat pada kanal b*, sedangkan daratan/bukit gelap)
            lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
            # ponytail: gaussian blur (5x5, s=1.0) on L/b suppresses sensor speckle; upgrade to guided filter if sharp masts present
            l_chan = cv2.GaussianBlur(lab[:, :, 0], (5, 5), 1.0)
            b_chan = cv2.GaussianBlur(lab[:, :, 2], (5, 5), 1.0)

            sign = -1.0 if not invert_mask else 1.0

            # Hitung gradien vertikal OpenCV Sobel ksize=5 (menggunakan float32 teroptimasi SIMD)
            sobel_l = cv2.Sobel(l_chan, cv2.CV_32F, 0, 1, ksize=5)
            sobel_gray = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=5)
            sobel_b = cv2.Sobel(b_chan, cv2.CV_32F, 0, 1, ksize=5)

            gl_pos = np.clip(sign * sobel_l[y_min:y_max, :], 0, None)
            gg_pos = np.clip(sign * sobel_gray[y_min:y_max, :], 0, None)
            gb_pos = np.clip(sign * sobel_b[y_min:y_max, :], 0, None)

            # 2. Filter Step-Edge Vertikal OpenCV untuk menekan rumbai awan tipis (cloud bands)
            k_size = 17
            k_half = k_size // 2
            step_kernel = np.zeros((k_size, 1), dtype=np.float32)
            # Response positif saat langit atas terang bertransisi ke daratan gelap di bawah
            step_sign = 1.0 if not invert_mask else -1.0
            step_kernel[:k_half, 0] = step_sign / float(k_half)
            step_kernel[k_half + 1:, 0] = -step_sign / float(k_half)
            step_resp = cv2.filter2D(gray.astype(np.float32), -1, step_kernel)[y_min:y_max, :]
            step_pos = np.clip(step_resp, 0, None)

            # Normalisasi robust setiap komponen sebelum fusi (strided percentile untuk efisiensi tinggi)
            def _norm_energy(mat: np.ndarray) -> np.ndarray:
                p995 = float(np.percentile(mat[::2, ::2], 99.5))
                return mat / p995 if p995 > 1e-4 else np.zeros_like(mat)

            e_l = _norm_energy(gl_pos)
            e_gray = _norm_energy(gg_pos)
            e_b = _norm_energy(gb_pos)
            e_step = _norm_energy(step_pos)

            # Fusi energi multi-spektral astronomis
            energy = 0.35 * e_l + 0.25 * e_gray + 0.25 * e_b + 0.15 * e_step

            # Prioritas batas teratas (Zenith-to-Nadir Skyline Prior):
            # Ufuk mar'i sejati adalah batas transisi pertama dari kubah langit terbuka ke daratan.
            # Kontur/tepi objek di bawah batas pertama (atap bangunan foreground, ekskavator, jalan, pantulan air)
            # ditekan secara eksponensial seiring bertambahnya energi kumulatif dari atas.
            # ponytail: exponential decay rate 4.5; upgrade to sky semantic mask if dense cloud shadows mimic skyline
            cum_energy = np.cumsum(energy, axis=0)
            max_cum = np.maximum(cum_energy[-1:, :], 1e-4)
            norm_cum = cum_energy / max_cum
            zenith_weight = np.exp(-4.5 * (norm_cum ** 1.2))
            energy_weighted = energy * zenith_weight

            # 3. Normalisasi kolom dengan Global Floor untuk mencegah amplifikasi noise pada kolom berkabut
            p99_e = float(np.percentile(energy_weighted[::2, ::2], 99.5))
            global_floor = max(0.15 * p99_e, 1e-4)
            col_max = np.maximum(np.max(energy_weighted, axis=0, keepdims=True), global_floor)
            energy_norm = energy_weighted / col_max

            cost = 1.0 - energy_norm
            roi_h = y_max - y_min

            dp = np.zeros((roi_h, w), dtype=np.float32)
            parent = np.zeros((roi_h, w), dtype=np.int32)
            dp[:, 0] = cost[:, 0]

            # Batasi rentang loncatan antarkolom dan gandakan penalti kelengkungan
            # agar garis tidak terjerumus menukik ke celah dinding/atap rumah di bawah
            max_jump = min(16, max(4, int(roi_h * 0.025)))
            jump_idx = np.arange(-max_jump, max_jump + 1)
            jump_penalty_kernel = (0.06 * (jump_idx ** 2)).astype(np.float32)

            y_grid = np.arange(roi_h, dtype=np.int32)

            # Vektorisasi kolom menggunakan sliding window NumPy (20x lebih cepat)
            for x in range(1, w):
                prev_col = dp[:, x - 1]
                padded = np.pad(prev_col, max_jump, mode='constant', constant_values=1e7)
                windows = np.lib.stride_tricks.sliding_window_view(padded, 2 * max_jump + 1)
                penalized = windows + jump_penalty_kernel
                min_idx = np.argmin(penalized, axis=1)
                dp[:, x] = cost[:, x] + penalized[y_grid, min_idx]
                parent[:, x] = np.clip(y_grid - max_jump + min_idx, 0, roi_h - 1)

            horizon_roi = np.zeros(w, dtype=np.int32)
            horizon_roi[x_end] = int(np.argmin(dp[:, x_end]))
            for x in range(x_end - 1, x_start - 1, -1):
                horizon_roi[x] = parent[horizon_roi[x + 1], x + 1]
            for x in range(x_end + 1, w):
                horizon_roi[x] = horizon_roi[x_end]
            for x in range(x_start - 1, -1, -1):
                horizon_roi[x] = horizon_roi[x_start]

            # 4. Interpolasi Puncak Parabolik Sub-Piksel (3-Point Parabolic Peak Interpolation)
            # Menghilangkan efek kuantisasi undakan tangga (stair-stepping) pada elevasi sudut astronomi
            subpixel_roi = horizon_roi.astype(np.float64)
            for x in range(x_start, x_end + 1):
                y_pk = horizon_roi[x]
                if 1 <= y_pk < roi_h - 1:
                    e_prev = float(energy[y_pk - 1, x])
                    e_curr = float(energy[y_pk, x])
                    e_next = float(energy[y_pk + 1, x])
                    denom = 2.0 * (2.0 * e_curr - e_prev - e_next)
                    if abs(denom) > 1e-5:
                        delta_pk = (e_next - e_prev) / denom
                        subpixel_roi[x] += np.clip(delta_pk, -0.5, 0.5)

            raw_horizon_y = y_min + subpixel_roi

        elif method == self.METHOD_CANNY:
            # Metode Canny Edge + Pencarian Kontur Teratas
            v = float(np.median(gray))
            lower = int(max(0, (0.66 + threshold_offset / 100.0) * v))
            upper = int(min(255, (1.33 + threshold_offset / 100.0) * v))
            edges = cv2.Canny(gray, lower, upper)

            # Morfologi closing horizontal untuk menghubungkan tepi bukit
            kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 3))
            closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel_close)

            # Temukan tepi pertama dari atas di dalam rentang ROI
            col_y = np.full(w, np.nan, dtype=np.float64)
            for x in range(w):
                col_edges = np.where(closed[y_min:y_max, x] > 0)[0]
                if len(col_edges) > 0:
                    col_y[x] = y_min + col_edges[0]
            valid_mask = ~np.isnan(col_y)
            if np.any(valid_mask):
                valid_x = np.where(valid_mask)[0]
                valid_y = col_y[valid_mask]
                col_y = np.interp(np.arange(w), valid_x, valid_y)
            else:
                col_y = np.full(w, int(h * 0.55), dtype=np.float64)
            raw_horizon_y = col_y

        else:
            # METHOD_OTSU: Adaptive Thresholding
            roi_gray = gray[y_min:y_max, :]
            otsu_val, _ = cv2.threshold(roi_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            target_thresh = int(np.clip(otsu_val + threshold_offset, 10, 245))

            if not invert_mask:
                _, raw_mask = cv2.threshold(gray, target_thresh, 255, cv2.THRESH_BINARY_INV)
            else:
                _, raw_mask = cv2.threshold(gray, target_thresh, 255, cv2.THRESH_BINARY)

            # Morphological cleaning
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 5))
            cleaned_mask = cv2.morphologyEx(raw_mask, cv2.MORPH_CLOSE, kernel)

            col_y = np.full(w, np.nan, dtype=np.float64)
            for x in range(w):
                col = cleaned_mask[y_min:y_max, x]
                ground_idxs = np.where(col > 0)[0]
                if len(ground_idxs) > 0:
                    col_y[x] = y_min + ground_idxs[0]
            valid_mask = ~np.isnan(col_y)
            if np.any(valid_mask):
                valid_x = np.where(valid_mask)[0]
                valid_y = col_y[valid_mask]
                col_y = np.interp(np.arange(w), valid_x, valid_y)
            else:
                col_y = np.full(w, float(y_max), dtype=np.float64)
            raw_horizon_y = col_y

        # Gunakan kernel median kecil (maks size 5) agar puncak objek tidak terpotong
        sw = max(3, smooth_window | 1)
        med_size = min(5, sw)
        if len(raw_horizon_y) > med_size:
            from scipy.ndimage import median_filter, uniform_filter1d
            filtered = median_filter(raw_horizon_y, size=med_size, mode="nearest")
            base_smoothed = uniform_filter1d(filtered, size=3, mode="nearest")
            horizon_y = np.clip(base_smoothed, float(y_min), float(y_max))
        else:
            horizon_y = raw_horizon_y

        # Integrasi halangan vertikal ramping (menara BTS, SUTET, kubah, tiang antena)
        # Menggunakan Filter Slender Prominence dengan Triple Acceptance Gate
        try:
            min_base = int(np.clip(np.min(horizon_y) - 8, y_min, y_max))
            if min_base > y_min + 15:
                sky_zone = gray[y_min:min_base, x_start:x_end+1]
                sky_med = float(np.median(sky_zone))
                # Ambang dijangkarkan ke median langit (menolak variasi rumbai awan)
                sky_thresh = sky_med - 20.0

                obs_mask = (gray < sky_thresh).astype(np.uint8) * 255
                kernel_vert = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 13))
                obs_closed = cv2.morphologyEx(obs_mask, cv2.MORPH_CLOSE, kernel_vert)

                tower_y = np.copy(horizon_y)
                for x in range(x_start, x_end + 1):
                    b_idx = int(horizon_y[x])
                    if b_idx >= h:
                        continue
                    col = obs_closed[:b_idx + 2, x]
                    curr = b_idx
                    while curr > y_min and col[curr] > 0:
                        curr -= 1
                    if curr < b_idx - 5:
                        tower_y[x] = float(curr)

                is_obstacle = (tower_y < horizon_y - 6)
                jumps = np.where(is_obstacle)[0]
                for _, g in groupby(enumerate(jumps), lambda ix: ix[0] - ix[1]):
                    group = list(map(itemgetter(1), g))
                    width = len(group)
                    tip_y = np.min(tower_y[group])
                    base_y = np.median(horizon_y[group])
                    height = base_y - tip_y
                    aspect = height / max(1.0, float(width))

                    y_check = int(round(tip_y + min(4, height * 0.3)))
                    x_l = max(0, group[0] - max(8, width))
                    x_r = min(w - 1, group[-1] + max(8, width))
                    sky_l = float(gray[y_check, x_l])
                    sky_r = float(gray[y_check, x_r])
                    tip_val = float(np.min(gray[y_check, group[0]:group[-1]+1]))
                    contrast = min(sky_l, sky_r) - tip_val

                    # Triple Gate: struktur fisik ramping dengan kontras nyata terhadap langit di kedua sisi
                    if 2 <= width <= 32 and height >= 10 and aspect >= 1.25 and contrast >= 15.0:
                        horizon_y[group] = tower_y[group]
        except Exception:
            pass

        # Buat mask biner tanah/halangan
        int_y = np.clip(np.round(horizon_y).astype(np.int32), 0, h - 1)
        for x in range(w):
            mask[int_y[x]:, x] = 255

        self.last_horizon_y = horizon_y
        return horizon_y, mask

    def compute_horizon_profile(
        self,
        horizon_y: np.ndarray,
        img_w: int,
        img_h: int,
        az_center: float,
        hfov: float,
        vfov: Optional[float] = None,
        tilt_center: float = 0.0,
        elevation_m: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Menghitung profil sudut (Azimut dan Elevasi) lengkap dari array horizon_y.
        """
        x_indices = np.arange(img_w)
        az_raw, el_raw = pixel_to_azimuth_elevation(
            x=x_indices,
            y=horizon_y,
            img_w=img_w,
            img_h=img_h,
            az_center=az_center,
            hfov=hfov,
            vfov=vfov,
            tilt_center=tilt_center,
        )
        azimuths = np.asarray(az_raw, dtype=np.float64)
        elevations = np.asarray(el_raw, dtype=np.float64)

        # Baseline kalibrasi ufuk: tempatkan 0° tepat di garis dasar ufuk mar'i (garis merah)
        min_el = float(np.min(elevations))
        elevations = elevations - min_el

        dip_deg, dip_arcmin = calculate_dip(elevation_m)

        prominent_obstacles = self.detect_prominent_obstacles(
            elevations=elevations,
            azimuths=azimuths,
            horizon_y=horizon_y,
            img_w=img_w,
            img_h=img_h,
        )

        min_idx = int(np.argmin(elevations))
        max_idx = int(np.argmax(elevations))

        stats = {
            "min_elevation": float(np.min(elevations)),
            "min_azimuth": float(azimuths[min_idx]),
            "max_elevation": float(np.max(elevations)),
            "max_azimuth": float(azimuths[max_idx]),
            "mean_elevation": float(np.mean(elevations)),
            "az_range_min": float(azimuths[0]),
            "az_range_max": float(azimuths[-1]),
            "hfov": hfov,
            "vfov": vfov if vfov is not None else float(np.ptp(elevations)),
            "prominent_count": len(prominent_obstacles),
        }

        self.last_azimuths = azimuths
        self.last_elevations = elevations

        return {
            "azimuths": azimuths,
            "elevations": elevations,
            "horizon_y": horizon_y,
            "dip_deg": dip_deg,
            "dip_arcmin": dip_arcmin,
            "prominent_obstacles": prominent_obstacles,
            "stats": stats,
            "img_w": img_w,
            "img_h": img_h,
            "az_center": az_center,
            "hfov": hfov,
            "vfov": vfov,
            "tilt_center": tilt_center,
            "elevation_m": elevation_m,
        }

    def detect_prominent_obstacles(
        self,
        elevations: np.ndarray,
        azimuths: np.ndarray,
        horizon_y: np.ndarray,
        img_w: int,
        img_h: int,
        min_prominence: float = 0.10,
        max_peaks: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Mendeteksi objek-objek rintangan yang menonjol di atas garis ufuk mar'i
        (misal menara pemancar, puncak bukit, gedung, atau pohon tinggi).

        Mengembalikan daftar objek dengan koordinat piksel (x, y) serta
        sudut astronomis:
        - Derajat Horizontal (Azimuth awal & akhir sesuai LEBAR objek)
        - Derajat Vertikal (Elevasi / Altitudo dalam derajat)
        - Nilai prominensi / kenaikan tinggi relatif
        """
        from scipy.signal import find_peaks

        min_dist = max(15, img_w // 28)
        peaks, props = find_peaks(elevations, prominence=min_prominence, distance=min_dist)
        if len(peaks) == 0 and min_prominence > 0.05:
            peaks, props = find_peaks(elevations, prominence=0.05, distance=min_dist)

        if len(peaks) == 0:
            return []

        proms = props.get("prominences", np.zeros(len(peaks)))
        left_bases = props.get("left_bases", peaks)
        right_bases = props.get("right_bases", peaks)
        top_indices = np.argsort(proms)[::-1][:max_peaks]
        top_peaks = sorted(peaks[top_indices])

        n = len(elevations)
        obstacles = []
        for i, px in enumerate(top_peaks):
            pos = np.where(peaks == px)[0]
            pi = int(pos[0]) if len(pos) > 0 else 0
            prom_val = float(proms[pi]) if len(pos) > 0 else 0.0
            py = float(horizon_y[px])
            az = float(azimuths[px])
            alt = float(elevations[px])

            # --- LEBAR OBJEK ---
            # Mulai dari kaki prominensi, lalu dipersempit memakai ambang 12% tinggi
            # prominensi agar lebar mengikuti bentuk objek (bukan seluruh lereng).
            x_start = int(left_bases[pi]) if len(pos) > 0 else int(px)
            x_end = int(right_bases[pi]) if len(pos) > 0 else int(px)
            x_start = max(0, min(n - 1, x_start))
            x_end = max(0, min(n - 1, x_end))

            base_elev = alt - prom_val
            thresh = base_elev + 0.12 * max(prom_val, 0.0)
            if prom_val > 0.0:
                k = int(px)
                while k > x_start and float(elevations[k - 1]) >= thresh:
                    k -= 1
                x_start = k
                k = int(px)
                while k < x_end and float(elevations[k + 1]) >= thresh:
                    k += 1
                x_end = k

            # Cegah rentang antar objek bertumpuk: batasi sampai titik tengah
            # antara puncak ini dengan puncak tetangga terdekat.
            if i > 0:
                mid_left = int(round((top_peaks[i - 1] + px) / 2.0))
                x_start = max(x_start, mid_left)
            if i < len(top_peaks) - 1:
                mid_right = int(round((px + top_peaks[i + 1]) / 2.0))
                x_end = min(x_end, mid_right)

            x_start = max(0, min(n - 1, x_start))
            x_end = max(0, min(n - 1, x_end))
            if x_end <= x_start:
                x_start = max(0, int(px) - 1)
                x_end = min(n - 1, int(px) + 1)

            az_start = float(azimuths[x_start])
            az_end = float(azimuths[x_end])
            # Pastikan urutan menaik (azimut bisa menurun bila arah bidik terbalik)
            if az_start > az_end:
                az_start, az_end = az_end, az_start

            obstacles.append({
                "id": i + 1,
                "x": int(px),
                "y": int(round(py)),
                "x_start": x_start,
                "x_end": x_end,
                "azimuth": round(az, 2),
                "az_start": round(az_start, 2),
                "az_end": round(az_end, 2),
                "az_span": round(abs(az_end - az_start), 2),
                "elevation": round(alt, 2),
                "prominence": round(prom_val, 2),
                "label": f"Objek {i + 1}",
                "text": f"Objek {i + 1}: Az {az_start:.2f}-{az_end:.2f} deg | Alt {alt:+.2f} deg",
                "short_text": f"Az {az_start:.2f}°-{az_end:.2f}°, Alt {alt:+.2f}°",
            })
        return obstacles

    def render_overlay(
        self,
        image_bgr: np.ndarray,
        horizon_y: np.ndarray,
        azimuths: Optional[np.ndarray] = None,
        elevations: Optional[np.ndarray] = None,
        target_az: Optional[float] = None,
        target_x: Optional[int] = None,
        target_y: Optional[int] = None,
        show_true_horizon: bool = True,
        dip_deg: float = 0.0,
        az_center: float = 270.0,
        hfov: float = 15.0,
        vfov: Optional[float] = None,
        tilt_center: float = 0.0,
        prominent_obstacles: Optional[List[Dict[str, Any]]] = None,
        show_prominent_peaks: bool = True,
    ) -> np.ndarray:
        """
        Merender kontur ufuk mar'i dan garis referensi astronomi pada gambar.
        - Garis Cyan/Neon: Kontur Ufuk Mar'i
        - Garis Putih Putus-putus: Ufuk Hakiki (0°)
        - Garis Kuning Tipis: Kerendahan Ufuk Laut (-Dip)
        - Garis Merah Vertikal & Titik Bidik: Posisi Azimut Sasaran Terpilih
        - Salib tengah optik (Center Optical Crosshair)
        """
        h, w = image_bgr.shape[:2]
        canvas = image_bgr.copy()

        # 1. Garis Ufuk Hakiki (0°) dan Ufuk Laut Dip ditiadakan sesuai permintaan
        # 2. Gambar Salib Sumbu Tengah Optik (Optical Center Crosshair)
        cx, cy = int((w - 1) / 2), int((h - 1) / 2)
        cv2.line(canvas, (cx - 15, cy), (cx + 15, cy), (120, 120, 120), 1)
        cv2.line(canvas, (cx, cy - 15), (cx, cy + 15), (120, 120, 120), 1)

        # 3. Gambar Kontur Ufuk Mar'i (Polylines Kuning Terang Ber-outline Hitam)
        # Hitung ketebalan proporsional agar tetap terlihat tajam pada foto resolusi tinggi
        line_thick = max(3, int(round(w / 350.0)))
        outline_thick = line_thick + max(2, int(line_thick * 0.6))

        pts = np.column_stack((
            np.arange(w),
            np.clip(np.round(horizon_y).astype(np.int32), 0, h - 1)
        )).reshape((-1, 1, 2))
        # Garis outline hitam agar kontras di latar langit terang/awan
        cv2.polylines(canvas, [pts], isClosed=False, color=(0, 0, 0), thickness=outline_thick, lineType=cv2.LINE_AA)
        # Garis kontur kuning neon terang
        cv2.polylines(canvas, [pts], isClosed=False, color=(0, 255, 255), thickness=line_thick, lineType=cv2.LINE_AA)

        # 4. Kursor Azimut Sasaran - Resolusi Target Terlebih Dahulu
        if target_x is None and target_az is not None:
            if azimuths is not None and len(azimuths) == w:
                target_x = int(np.argmin(np.abs(azimuths - target_az)))
            else:
                from core.falak_calc import azimuth_elevation_to_pixel
                tx_calc, _ = azimuth_elevation_to_pixel(
                    target_az, 0.0, w, h, az_center, hfov, vfov, tilt_center
                )
                target_x = int(round(tx_calc))

        # 1. Hitung info target terlebih dahulu
        placed_boxes = []
        target_info = None
        if target_x is not None and 0 <= target_x < w:
            raw_ty = horizon_y[target_x] if target_y is None else target_y
            ty = int(round(raw_ty))
            if target_az is not None and elevations is not None:
                alt_val = elevations[target_x]
                txt = f"Az: {target_az:.2f} deg | Alt: {alt_val:+.2f} deg"
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.42
                (tw, th), baseline = cv2.getTextSize(txt, font, font_scale, 1)
                tx_box = min(w - tw - 24, max(10, target_x - tw // 2))
                ty_box = max(th + 16, ty - 26)
                box_w = tw + 18
                box_h = th + baseline + 10
                box_top = ty_box - th - 5
                placed_boxes.append((tx_box, box_top, box_w, box_h))
                target_info = (tx_box, ty_box, box_top, box_w, box_h, txt)

        # 2. Gambar garis meridian merah dan retikel bidik
        if target_x is not None and 0 <= target_x < w:
            raw_ty = horizon_y[target_x] if target_y is None else target_y
            ty = int(round(raw_ty))
            cv2.line(canvas, (target_x, 0), (target_x, h - 1), (0, 0, 255), 2, cv2.LINE_AA)
            cv2.circle(canvas, (target_x, ty), 6, (0, 0, 255), -1, cv2.LINE_AA)
            cv2.circle(canvas, (target_x, ty), 11, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.circle(canvas, (target_x, ty), 15, (0, 0, 255), 1, cv2.LINE_AA)

        # 3. Anotasi Popup Objek Menonjol (Prominent Obstacles / Peaks)
        # Menampilkan penanda dan pop up angka derajat horizontal & vertikal pada objek yang menonjol
        if show_prominent_peaks and elevations is not None and azimuths is not None:
            if prominent_obstacles is None:
                prominent_obstacles = self.detect_prominent_obstacles(
                    elevations=elevations,
                    azimuths=azimuths,
                    horizon_y=horizon_y,
                    img_w=w,
                    img_h=h,
                )

            for i, obs in enumerate(prominent_obstacles):
                px = obs["x"]
                py = obs["y"]
                az_val = obs["azimuth"]
                alt_val = obs["elevation"]
                obj_id = obs.get("id", i + 1)
                obj_label = (obs.get("label") or f"Objek {obj_id}").strip()

                # Rentang azimut sesuai LEBAR objek (mis. 230,00 - 240,00 derajat)
                az_start = obs.get("az_start", az_val)
                az_end = obs.get("az_end", az_val)
                try:
                    az_start = float(az_start)
                    az_end = float(az_end)
                except (TypeError, ValueError):
                    az_start, az_end = az_val, az_val
                has_span = abs(az_end - az_start) > 0.05
                if has_span:
                    az_txt = f"{az_start:.2f}-{az_end:.2f} deg"
                else:
                    az_txt = f"{az_val:.2f} deg"

                # Cek kedekatan dengan target_x agar kotak tidak bertumpuk
                near_target = (target_x is not None) and (abs(px - target_x) < 45)

                txt = f"{obj_label}: Az {az_txt} | Alt {alt_val:+.2f} deg"
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.40
                thick = 1
                (tw, th), baseline = cv2.getTextSize(txt, font, font_scale, thick)
                pad_x, pad_y = 7, 5
                box_w = tw + pad_x * 2
                box_h = th + pad_y * 2 + baseline

                # Variasi ketinggian stem agar popup objek berdekatan tidak tumpang-tindih
                stem_len = 24 + ((i + (1 if near_target else 0)) % 2) * 26
                box_y = py - stem_len - box_h
                if box_y < 12:
                    box_y = min(h - box_h - 10, py + 18)
                cand_bx = int(px - box_w / 2)
                cand_bx = max(8, min(w - box_w - 8, cand_bx))

                # Margin keselamatan 6px terhadap garis meridian merah agar teks tidak tertimpa
                if target_x is not None and abs(px - target_x) > 10:
                    if cand_bx <= target_x <= cand_bx + box_w:
                        if px < target_x:
                            cand_bx = max(8, target_x - box_w - 6)
                        else:
                            cand_bx = min(w - box_w - 8, target_x + 6)
                box_x = cand_bx

                # Garis vertikal penunjuk dari pucuk objek ke kotak popup
                stem_top = box_y + box_h if box_y < py else box_y
                stem_color = (0, 220, 255)  # Kuning-amber terang
                cv2.line(canvas, (px, py), (px, stem_top), stem_color, 1, cv2.LINE_AA)

                # Penanda LEBAR objek: garis horizontal + garis batas kiri/kanan
                xs = obs.get("x_start")
                xe = obs.get("x_end")
                if has_span and isinstance(xs, (int, float)) and isinstance(xe, (int, float)):
                    xs = max(0, min(w - 1, int(xs)))
                    xe = max(0, min(w - 1, int(xe)))
                    if xe > xs:
                        span_color = (255, 176, 0)  # Biru-cyan BGR
                        # garis horizontal di bawah puncak objek
                        span_y = min(h - 6, py + 14)
                        cv2.line(canvas, (xs, span_y), (xe, span_y), span_color, 2, cv2.LINE_AA)
                        # tiang batas kiri & kanan
                        tick = 9
                        cv2.line(canvas, (xs, span_y - tick), (xs, span_y + tick), span_color, 2, cv2.LINE_AA)
                        cv2.line(canvas, (xe, span_y - tick), (xe, span_y + tick), span_color, 2, cv2.LINE_AA)
                        # titik pucuk tetap ditandai
                        cv2.line(canvas, (px, py), (px, span_y), span_color, 1, cv2.LINE_AA)

                # Titik penanda pucuk objek
                cv2.circle(canvas, (px, py), 5, (0, 0, 0), -1, cv2.LINE_AA)
                cv2.circle(canvas, (px, py), 4, stem_color, -1, cv2.LINE_AA)
                cv2.circle(canvas, (px, py), 2, (255, 255, 255), -1, cv2.LINE_AA)

                # Kotak popup latar belakang gelap berbingkai cyan modern
                cv2.rectangle(canvas, (box_x, box_y), (box_x + box_w, box_y + box_h), (15, 23, 42), -1)
                cv2.rectangle(canvas, (box_x, box_y), (box_x + box_w, box_y + box_h), (56, 189, 248), 1, cv2.LINE_AA)
                cv2.putText(
                    canvas, txt, (box_x + pad_x, box_y + pad_y + th),
                    font, font_scale, (255, 255, 255), thick, cv2.LINE_AA
                )

        # 4. Gambar kotak teks kursor target di layer paling atas
        if target_x is not None and 0 <= target_x < w and target_info is not None:
            tx_box, ty_box, box_top, box_w, box_h, txt = target_info
            cv2.rectangle(canvas, (tx_box, box_top), (tx_box + box_w, box_top + box_h), (20, 20, 25), -1)
            cv2.rectangle(canvas, (tx_box, box_top), (tx_box + box_w, box_top + box_h), (0, 50, 255), 1, cv2.LINE_AA)
            cv2.putText(
                canvas, txt, (tx_box + 8, ty_box),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA
            )

        return canvas
