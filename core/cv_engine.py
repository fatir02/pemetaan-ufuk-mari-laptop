"""
cv_engine.py
Engine Computer Vision untuk segmentasi dan ekstraksi profil kontur ufuk mar'i.
Mengidentifikasi batas pertemuan langit (sky) dan daratan/halangan (ground/terrain)
per kolom horizontal, mengonversi ke profil elevasi sudut astronomi.
"""

from typing import Tuple, Dict, Any, Optional, List
import numpy as np
import cv2

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
        # Kandidat struktur ramping (menara/antena/tiang) dari tahap detail.
        # Disimpan terpisah agar detect_prominent_obstacles tidak hanya bergantung
        # pada scipy.find_peaks yang tidak dapat mengenali puncak di endpoint.
        self.last_detail_obstacles: List[Dict[str, Any]] = []
        self.last_active_bounds = (0, 0)
        self.last_image_bgr: Optional[np.ndarray] = None

    @staticmethod
    def _group_true_runs(flags: np.ndarray, max_gap: int = 1) -> List[Tuple[int, int]]:
        """Kelompokkan indeks True, sambil menjembatani gap horizontal kecil."""
        idx = np.flatnonzero(flags)
        if len(idx) == 0:
            return []
        groups: List[Tuple[int, int]] = []
        start = prev = int(idx[0])
        for value in idx[1:]:
            value = int(value)
            if value - prev > max_gap + 1:
                groups.append((start, prev))
                start = value
            prev = value
        groups.append((start, prev))
        return groups

    def _detect_slender_obstacles(
        self,
        image_bgr: np.ndarray,
        base_horizon: np.ndarray,
        x_start: int,
        x_end: int,
        y_min: int,
    ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """Deteksi struktur ramping di atas baseline tanpa mengganggu DP utama.

        Jalur ini sengaja memakai citra detail yang lebih sedikit dihaluskan.
        Kandidat harus berawal dekat baseline, tetapi boleh memiliki gap vertikal
        pendek agar menara kisi, antena, dan citra JPEG tetap dapat dikenali.
        """
        h, w = image_bgr.shape[:2]
        base = np.asarray(base_horizon, dtype=np.float64)
        final_horizon = base.copy()
        if h < 30 or w < 30 or x_end < x_start:
            return final_horizon, []

        gray_raw = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        detail = cv2.GaussianBlur(gray_raw, (3, 3), 0.55)

        # Latar langit lokal dihitung secara horizontal. Objek vertikal sempit
        # menjadi lebih gelap daripada estimasi ini, sedangkan awan/bukit lebar
        # cenderung ikut masuk ke background dan memperoleh respons kecil.
        bg_width = max(31, int(round(w * 0.045)) | 1)
        bg_width = min(bg_width, 151 if w >= 151 else (w - 1) | 1)
        sky_background = cv2.GaussianBlur(detail, (bg_width, 1), 0)
        dark_response = sky_background.astype(np.float32) - detail.astype(np.float32)

        roi_height = max(24, int(round(h * 0.18)))
        min_height = max(5, int(round(h * 0.006)))
        max_width = max(24, int(round(w * 0.04)))
        attach_tolerance = max(3, int(round(h * 0.005)))
        max_vertical_gap = max(4, int(round(h * 0.009)))

        # Ambang rendah diperlukan untuk struktur 1-3 px, tetapi tetap ditopang
        # validasi kontinuitas, aspect ratio, kontras samping, dan attachment.
        response_mask = (dark_response >= 6.0).astype(np.uint8) * 255
        close_h = max_vertical_gap * 2 + 1
        response_closed = cv2.morphologyEx(
            response_mask,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_RECT, (1, close_h)),
        )

        tops = base.copy()
        heights = np.zeros(w, dtype=np.float64)
        continuities = np.zeros(w, dtype=np.float64)
        attachments = np.zeros(w, dtype=np.float64)

        for x in range(x_start, x_end + 1):
            bottom = min(h - 1, int(round(base[x])) + attach_tolerance)
            top_limit = max(y_min, int(round(base[x])) - roi_height)
            if bottom <= top_limit:
                continue

            col_closed = response_closed[top_limit:bottom + 1, x] > 0
            col_raw = response_mask[top_limit:bottom + 1, x] > 0
            base_pos = int(round(base[x])) - top_limit
            search_lo = max(0, base_pos - attach_tolerance)
            search_hi = min(len(col_closed), base_pos + attach_tolerance + 1)
            anchors = np.flatnonzero(col_closed[search_lo:search_hi])
            if len(anchors) == 0:
                continue

            anchor = search_lo + int(anchors[-1])
            cursor = anchor
            gap = 0
            highest = anchor
            while cursor >= 0:
                if col_closed[cursor]:
                    highest = cursor
                    gap = 0
                else:
                    gap += 1
                    if gap > max_vertical_gap:
                        break
                cursor -= 1

            top_y = top_limit + highest
            height_px = float(base[x] - top_y)
            if height_px < min_height:
                continue

            seg_end = min(len(col_raw), base_pos + 1)
            segment = col_raw[highest:seg_end]
            continuity = float(np.mean(segment)) if len(segment) else 0.0
            tops[x] = float(top_y)
            heights[x] = height_px
            continuities[x] = continuity
            attachments[x] = 1.0

        active_columns = heights >= min_height
        candidates: List[Dict[str, Any]] = []
        for group_start, group_end in self._group_true_runs(active_columns, max_gap=2):
            width = group_end - group_start + 1
            if width > max_width:
                continue

            cols = np.arange(group_start, group_end + 1)
            valid_cols = cols[heights[cols] >= min_height]
            if len(valid_cols) == 0:
                continue
            tip_x = int(valid_cols[np.argmin(tops[valid_cols])])
            tip_y = float(tops[tip_x])
            base_y = float(np.median(base[valid_cols]))
            height_px = max(0.0, base_y - tip_y)
            aspect = height_px / max(1.0, float(width))
            continuity = float(np.mean(continuities[valid_cols]))

            # Kontras median di kedua sisi. Di endpoint active image, satu sisi
            # saja cukup sehingga menara yang terpotong frame tidak dibuang.
            y0 = max(y_min, int(round(tip_y)))
            y1 = min(h, int(round(tip_y + max(4.0, height_px * 0.55))))
            object_patch = detail[y0:y1, group_start:group_end + 1]
            object_level = float(np.median(object_patch)) if object_patch.size else 255.0
            side_span = max(5, min(20, width * 2 + 3))
            side_levels = []
            if group_start > x_start:
                left = detail[y0:y1, max(x_start, group_start - side_span):group_start]
                if left.size:
                    side_levels.append(float(np.median(left)))
            if group_end < x_end:
                right = detail[y0:y1, group_end + 1:min(x_end + 1, group_end + 1 + side_span)]
                if right.size:
                    side_levels.append(float(np.median(right)))
            contrast = max(0.0, (min(side_levels) - object_level) if side_levels else 0.0)

            # Skor lunak: kandidat tidak langsung gugur hanya karena satu ciri
            # (mis. kontras saat berkabut) sedikit di bawah nilai ideal.
            height_score = min(1.0, height_px / max(12.0, h * 0.025))
            aspect_score = min(1.0, aspect / 2.0)
            contrast_score = min(1.0, contrast / 18.0)
            continuity_score = min(1.0, continuity / 0.60)
            edge_bonus = 0.08 if group_start <= x_start + 1 or group_end >= x_end - 1 else 0.0
            confidence = min(1.0,
                0.24 * height_score
                + 0.20 * aspect_score
                + 0.24 * contrast_score
                + 0.24 * continuity_score
                + 0.08 * float(np.mean(attachments[valid_cols]))
                + edge_bonus
            )

            # Struktur sangat tipis mendapat toleransi; blob lebar wajib punya
            # kontras/aspect lebih kuat untuk menekan awan dan bayangan bukit.
            accepted = confidence >= 0.48 and continuity >= 0.28 and aspect >= 0.75
            if not accepted:
                continue

            # Isi gap horizontal pendek memakai interpolasi top dari kolom valid.
            group_cols = np.arange(group_start, group_end + 1)
            interp_top = np.interp(group_cols, valid_cols, tops[valid_cols])
            final_horizon[group_cols] = np.minimum(final_horizon[group_cols], interp_top)
            candidates.append({
                "x": tip_x,
                "y": int(round(tip_y)),
                "x_start": int(group_start),
                "x_end": int(group_end),
                "height_px": round(height_px, 2),
                "width_px": int(width),
                "continuity": round(continuity, 3),
                "contrast": round(contrast, 2),
                "confidence": round(confidence, 3),
                "is_endpoint": bool(group_start <= x_start + 1 or group_end >= x_end - 1),
                "source": "detail_vertical",
            })

        return final_horizon, candidates

    def _estimate_bottom_connected_prior(
        self,
        gray: np.ndarray,
        y_min: int,
        y_max: int,
        x_start: int,
        x_end: int,
    ) -> Tuple[np.ndarray, float]:
        """Estimasi batas permukaan yang benar-benar terhubung ke bawah citra.

        Awan ekstrem dapat mempunyai gradien lebih kuat daripada ufuk. Karena
        awan umumnya tidak terhubung ke daratan di bawah foto, prior ini memakai
        komponen gelap bottom-connected. Horizontal opening sementara membuang
        pohon/menara ramping agar awan yang bersentuhan secara visual dengannya
        tidak ikut dianggap daratan. Struktur tersebut ditambahkan kembali oleh
        detector detail setelah baseline utama ditemukan.

        Returns:
            (prior_y_per_column, confidence_0_to_1)
        """
        h, w = gray.shape[:2]
        active_w = max(1, x_end - x_start + 1)
        work = cv2.GaussianBlur(gray, (5, 5), 1.0)

        # Otsu dihitung pada 65% bagian bawah: cukup mencakup bukit/laut/tanah,
        # tetapi tidak didominasi kubah langit biru bagian atas.
        lower_top = max(y_min, int(round(h * 0.35)))
        lower = work[lower_top:y_max, x_start:x_end + 1]
        if lower.size == 0:
            return np.full(w, h * 0.65, dtype=np.float64), 0.0
        otsu, _ = cv2.threshold(lower, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        dark = (work <= float(otsu)).astype(np.uint8) * 255

        # Hilangkan konektor sempit vertikal (pohon/menara) sebelum flood dari
        # bawah. Massa daratan horizontal tetap dipertahankan.
        open_w = max(7, int(round(active_w * 0.018)) | 1)
        opened = cv2.morphologyEx(
            dark,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_RECT, (open_w, 3)),
        )
        opened = cv2.morphologyEx(
            opened,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_RECT, (max(5, open_w // 2) | 1, 5)),
        )
        opened[:, :x_start] = 0
        opened[:, x_end + 1:] = 0

        count, labels, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)
        connected = np.zeros_like(opened)
        seed_top = max(0, h - max(4, int(round(h * 0.025))))
        seed_labels = set(int(v) for v in np.unique(labels[seed_top:h, x_start:x_end + 1]) if int(v) != 0)
        # Jika dasar foto sangat terang, izinkan komponen besar yang mencapai
        # dekat dasar sebagai fallback, tetapi bukan cloud blob menggantung.
        if not seed_labels:
            for label in range(1, count):
                x, y, ww, hh, area = stats[label]
                if y + hh >= h - max(8, int(h * 0.05)) and area >= active_w * 3:
                    seed_labels.add(label)
        for label in seed_labels:
            connected[labels == label] = 255

        top_y = np.full(w, np.nan, dtype=np.float64)
        for x in range(x_start, x_end + 1):
            ys = np.flatnonzero(connected[y_min:y_max, x] > 0)
            if len(ys):
                top_y[x] = float(y_min + ys[0])

        valid = np.isfinite(top_y[x_start:x_end + 1])
        coverage = float(np.mean(valid)) if len(valid) else 0.0
        if coverage < 0.12:
            return np.full(w, h * 0.68, dtype=np.float64), 0.0

        valid_x = np.flatnonzero(np.isfinite(top_y))
        prior = np.interp(np.arange(w), valid_x, top_y[valid_x])
        from scipy.ndimage import median_filter, uniform_filter1d
        smooth_size = max(9, int(round(active_w * 0.025)) | 1)
        prior = median_filter(prior, size=smooth_size, mode="nearest")
        prior = uniform_filter1d(prior, size=max(3, smooth_size // 3), mode="nearest")

        # Confidence juga memperhitungkan apakah massa bawah cukup luas.
        area_ratio = float(np.count_nonzero(connected)) / float(max(1, active_w * h))
        confidence = np.clip(0.65 * coverage + 0.35 * min(1.0, area_ratio / 0.12), 0.0, 1.0)
        return prior.astype(np.float64), float(confidence)

    def _classify_skyline_obstacle(
        self,
        x_start: int,
        x_end: int,
        tip_x: int,
        tip_y: float,
        horizon_y: np.ndarray,
        detail_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Klasifikasi konservatif hanya untuk objek yang menyentuh skyline.

        Ini bukan object detector seluruh foto. Label diturunkan dari geometri
        profil dan ciri visual ROI lokal, sehingga nama tetap dapat dikoreksi
        pengguna ketika kondisi lapangan ambigu.
        """
        image = self.last_image_bgr
        if image is None or image.size == 0:
            return {"class": "skyline_obstacle", "label": "Halangan Ufuk", "confidence": 0.35}

        h, w = image.shape[:2]
        xs = max(0, min(w - 1, int(x_start)))
        xe = max(xs, min(w - 1, int(x_end)))
        px = max(xs, min(xe, int(tip_x)))
        py = max(0, min(h - 1, int(round(tip_y))))
        width = max(1, xe - xs + 1)

        detail_height = float((detail_meta or {}).get("height_px", 0.0))
        if detail_height > 0:
            base_y = min(h - 1, int(round(py + detail_height)))
        else:
            shoulder = max(4, min(40, width // 2 + 3))
            samples = np.concatenate((
                horizon_y[max(0, xs - shoulder):xs],
                horizon_y[xe + 1:min(w, xe + shoulder + 1)],
            ))
            base_y = int(round(np.median(samples))) if len(samples) else int(round(np.max(horizon_y[xs:xe + 1])))
            base_y = max(py + 1, min(h - 1, base_y))
        height = max(1, base_y - py)
        aspect = height / float(width)

        # ROI diperluas agar kanopi di sekitar batang dan bidang atap di sekitar
        # peak turut dinilai, tetapi tidak sampai mengklasifikasikan seluruh foto.
        pad_x = max(6, min(int(w * 0.025), width * 2))
        rx0, rx1 = max(0, xs - pad_x), min(w, xe + pad_x + 1)
        ry0, ry1 = max(0, py - max(2, height // 10)), min(h, base_y + max(3, height // 8))
        roi = image[ry0:ry1, rx0:rx1]
        if roi.size == 0:
            return {"class": "skyline_obstacle", "label": "Halangan Ufuk", "confidence": 0.35}

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        # Vegetasi hijau serta vegetasi gelap/desaturasi sedang.
        green = cv2.inRange(hsv, np.array([25, 28, 20]), np.array([100, 255, 230]))
        green_ratio = float(np.mean(green > 0))
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        lap_var = float(cv2.Laplacian(gray_roi, cv2.CV_32F).var())
        edges = cv2.Canny(gray_roi, 50, 140)
        edge_density = float(np.mean(edges > 0))

        # Ukur dukungan massa gelap pada bagian tengah-bawah objek. Sebuah sisi
        # gedung dapat terlihat ramping pada kontur, tetapi di bawahnya terdapat
        # bidang bangunan yang lebar. Menara sejati tetap memiliki footprint
        # sempit/berongga. Fitur ini mencegah setiap vertical detail dilabel menara.
        upper_band_end = max(1, min(roi.shape[0], max(2, int(roi.shape[0] * 0.22))))
        sky_level = float(np.median(gray_roi[:upper_band_end, :]))
        lower_start = max(0, min(roi.shape[0] - 1, int(roi.shape[0] * 0.38)))
        lower_gray = gray_roi[lower_start:, :]
        dark_support = lower_gray < (sky_level - 9.0)
        if dark_support.size:
            supported_columns = np.mean(dark_support, axis=0) >= 0.32
            support_ratio = float(np.mean(supported_columns))
            solidity = float(np.mean(dark_support))
        else:
            support_ratio = 0.0
            solidity = 0.0

        sobel_x = np.abs(cv2.Sobel(gray_roi, cv2.CV_32F, 1, 0, ksize=3))
        sobel_y = np.abs(cv2.Sobel(gray_roi, cv2.CV_32F, 0, 1, ksize=3))
        horizontal_structure = float(np.mean(sobel_y)) / max(1.0, float(np.mean(sobel_x) + np.mean(sobel_y)))

        # Garis arsitektural harus berupa segmen lurus yang nyata di dalam massa
        # objek. Rasio Sobel saja tidak cukup karena batas bukit-langit juga
        # menghasilkan respons horizontal yang kuat.
        lower_edges = edges[lower_start:, :]
        min_line_length = max(6, int(roi.shape[1] * 0.22))
        lines = cv2.HoughLinesP(
            lower_edges,
            1,
            np.pi / 180.0,
            threshold=max(6, min_line_length // 2),
            minLineLength=min_line_length,
            maxLineGap=max(2, int(roi.shape[1] * 0.05)),
        )
        horizontal_lengths = []
        vertical_lengths = []
        if lines is not None:
            for line in np.asarray(lines).reshape(-1, 4):
                x1, y1, x2, y2 = (int(v) for v in line)
                dx, dy = abs(x2 - x1), abs(y2 - y1)
                length = float(np.hypot(dx, dy))
                if dx >= min_line_length and dy <= max(2, int(dx * 0.16)):
                    horizontal_lengths.append(length)
                elif dy >= max(6, int(roi.shape[0] * 0.18)) and dx <= max(2, int(dy * 0.16)):
                    vertical_lengths.append(length)
        horizontal_line_count = len(horizontal_lengths)
        horizontal_line_coverage = min(1.0, sum(horizontal_lengths) / max(1.0, roi.shape[1] * 2.0))
        vertical_line_coverage = min(1.0, sum(vertical_lengths) / max(1.0, roi.shape[0] * 2.0))

        # Ketidakteraturan kontur: vegetasi cenderung bergerigi; terrain halus.
        segment = np.asarray(horizon_y[xs:xe + 1], dtype=np.float64)
        if len(segment) >= 3:
            roughness = float(np.median(np.abs(np.diff(segment, n=2))))
        else:
            roughness = 0.0

        source = str((detail_meta or {}).get("source", "profile_peak"))
        continuity = float((detail_meta or {}).get("continuity", 0.0) or 0.0)
        contrast = float((detail_meta or {}).get("contrast", 0.0) or 0.0)
        detail_confidence = float((detail_meta or {}).get("confidence", 0.0) or 0.0)

        # Menara pada skyline perkotaan sering berdiri di balik gedung/pohon.
        # Karena itu massa lebar di bawah batang tidak boleh membatalkan evidence
        # geometri dari detector detail jika batangnya jelas tinggi dan ramping.
        strong_slender_detail = (
            source == "detail_vertical"
            and aspect >= 2.4
            and continuity >= 0.28
            and detail_confidence >= 0.48
        )
        support_penalty = 1.0 if strong_slender_detail else (
            1.0 - 0.65 * min(1.0, support_ratio / 0.58)
        )

        scores = {
            "tower_antenna": 0.0,
            "vegetation": 0.0,
            "building_roof": 0.0,
            "terrain": 0.0,
        }

        scores["vegetation"] = min(1.0,
            0.62 * min(1.0, green_ratio / 0.24)
            + 0.20 * min(1.0, lap_var / 700.0)
            + 0.18 * min(1.0, roughness / 2.0)
        )
        scores["tower_antenna"] = min(1.0,
            0.38 * min(1.0, aspect / 3.5)
            + 0.22 * min(1.0, continuity / 0.65)
            + 0.18 * min(1.0, contrast / 18.0)
            + 0.14 * min(1.0, edge_density / 0.18)
            + (0.08 if source == "detail_vertical" else 0.0)
        ) * (1.0 - min(0.75, green_ratio * 1.8)) * support_penalty

        # Bangunan/atap umumnya cukup lebar, bertepi jelas, dan tidak hijau.
        broadness = min(1.0, width / max(12.0, w * 0.035))
        low_aspect = 1.0 - min(1.0, aspect / 2.5)
        scores["building_roof"] = min(1.0,
            0.12 * broadness
            + 0.12 * min(1.0, edge_density / 0.16)
            + 0.08 * low_aspect
            + 0.12 * min(1.0, support_ratio / 0.55)
            + 0.10 * min(1.0, solidity / 0.48)
            + 0.24 * horizontal_line_coverage
            + 0.14 * vertical_line_coverage
            + (0.08 if horizontal_line_count >= 2 else 0.0)
        )

        # Terrain adalah fallback untuk puncak lebar, halus, dan bukan kandidat
        # struktur vertikal hasil detector detail.
        smoothness = 1.0 - min(1.0, roughness / 1.8)
        scores["terrain"] = min(1.0,
            0.46 * broadness
            + 0.34 * smoothness
            + 0.20 * (1.0 - min(1.0, edge_density / 0.22))
        ) * (0.55 if source == "detail_vertical" else 1.0)

        class_key = max(scores, key=scores.get)
        confidence = float(scores[class_key])
        labels = {
            "tower_antenna": "Menara/Antena",
            "vegetation": "Vegetasi/Pohon",
            "building_roof": "Bangunan/Atap",
            "terrain": "Bukit/Terrain",
        }
        # Bidang solid lebar dengan garis horizontal kuat merupakan evidence
        # bangunan yang lebih spesifik daripada fallback terrain. Ini menangani
        # atap segitiga yang profil luarnya tampak seperti bukit kecil.
        architectural_evidence = min(1.0,
            0.20 * min(1.0, support_ratio / 0.55)
            + 0.16 * min(1.0, solidity / 0.55)
            + 0.32 * horizontal_line_coverage
            + 0.20 * vertical_line_coverage
            + (0.12 if horizontal_line_count >= 2 else 0.0)
        ) * (1.0 - min(0.8, green_ratio * 2.0))
        has_architectural_lines = (
            horizontal_line_count >= 2
            or (horizontal_line_coverage >= 0.32 and vertical_line_coverage >= 0.12)
        )
        if (
            has_architectural_lines
            and architectural_evidence >= 0.60
            and class_key not in ("vegetation", "tower_antenna")
        ):
            class_key = "building_roof"
            confidence = max(float(scores["building_roof"]), float(architectural_evidence))

        # Bila seluruh evidence lemah, jangan membuat klaim spesifik.
        # Klaim menara dibuat lebih ketat. Vertical edge pada gedung tidak cukup:
        # harus benar-benar ramping, footprint tidak solid/lebar, dan skornya
        # mengungguli bangunan dengan margin yang layak.
        tower_rejected = (
            aspect < 2.0
            or (
                not strong_slender_detail
                and (
                    support_ratio > 0.58
                    or solidity > 0.52
                    or scores["tower_antenna"] < scores["building_roof"] + 0.08
                )
            )
        )
        if class_key == "tower_antenna" and tower_rejected:
            # Jangan otomatis mengubah kandidat menara yang gagal menjadi
            # bangunan. Pilih ulang dari evidence yang benar-benar tersedia.
            alternatives = {
                "vegetation": scores["vegetation"],
                "terrain": scores["terrain"],
            }
            if has_architectural_lines:
                alternatives["building_roof"] = max(scores["building_roof"], architectural_evidence)
            class_key = max(alternatives, key=alternatives.get)
            confidence = float(alternatives[class_key])

        if confidence < 0.44 or class_key == "skyline_obstacle":
            class_key = "skyline_obstacle"
            confidence = max(0.30, confidence)
            label = "Halangan Ufuk"
        else:
            label = labels[class_key]
        return {
            "class": class_key,
            "label": label,
            "confidence": round(confidence, 3),
            "features": {
                "aspect_ratio": round(aspect, 3),
                "green_ratio": round(green_ratio, 3),
                "edge_density": round(edge_density, 3),
                "texture": round(lap_var, 2),
                "roughness": round(roughness, 3),
                "support_ratio": round(support_ratio, 3),
                "solidity": round(solidity, 3),
                "horizontal_structure": round(horizontal_structure, 3),
                "horizontal_line_count": horizontal_line_count,
                "horizontal_line_coverage": round(horizontal_line_coverage, 3),
                "vertical_line_coverage": round(vertical_line_coverage, 3),
                "strong_slender_detail": strong_slender_detail,
            },
        }

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
        self.last_image_bgr = image_bgr.copy()

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
        self.last_active_bounds = (x_start, x_end)

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

            # Prior permukaan bawah menggantikan "edge pertama dari atas" yang
            # mudah terkunci ke awan ekstrem. Awan boleh memiliki energi tinggi,
            # tetapi mendapat penalti bila jauh di atas massa bottom-connected.
            lower_prior, prior_confidence = self._estimate_bottom_connected_prior(
                gray=gray,
                y_min=y_min,
                y_max=y_max,
                x_start=x_start,
                x_end=x_end,
            )

            # 3. Normalisasi kolom dengan Global Floor untuk mencegah amplifikasi noise pada kolom berkabut
            p99_e = float(np.percentile(energy[::2, ::2], 99.5))
            global_floor = max(0.15 * p99_e, 1e-4)
            col_max = np.maximum(np.max(energy, axis=0, keepdims=True), global_floor)
            energy_norm = energy / col_max

            roi_h = y_max - y_min
            roi_rows = np.arange(y_min, y_max, dtype=np.float64)[:, None]
            prior_roi = lower_prior[None, :]
            # Ufuk laut dapat sedikit berada di atas daratan foreground. Zona
            # toleransi 4.5% tinggi tidak dipenalti; awan yang jauh lebih tinggi
            # menerima penalti progresif. Turun jauh di bawah massa dasar juga
            # dipenalti agar jalur tidak memilih tekstur rumput/jalan.
            free_above = max(8.0, h * 0.045)
            free_below = max(4.0, h * 0.018)
            too_high = np.maximum(0.0, prior_roi - roi_rows - free_above)
            too_low = np.maximum(0.0, roi_rows - prior_roi - free_below)
            position_penalty = too_high / max(12.0, h * 0.12) + too_low / max(10.0, h * 0.08)
            prior_weight = 0.35 + 1.25 * prior_confidence
            cost = 1.0 - energy_norm + prior_weight * position_penalty.astype(np.float32)

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

        # Jalur detail kedua: DP tetap menjaga bukit mulus, sedangkan struktur
        # sempit dideteksi dari citra tajam dan digabung secara tervalidasi.
        try:
            horizon_y, self.last_detail_obstacles = self._detect_slender_obstacles(
                image_bgr=image_bgr,
                base_horizon=horizon_y,
                x_start=x_start,
                x_end=x_end,
                y_min=y_min,
            )
        except Exception:
            self.last_detail_obstacles = []

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
        # Referensi yang disengaja oleh instrumen: titik terendah profil pada
        # foto dijadikan baseline relatif 0°. Nilai objek menyatakan tinggi
        # sudut di atas baseline ufuk tersebut, bukan elevasi absolut geodetik.
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
            "baseline_raw_elevation": min_el,
            "elevation_reference": "minimum_horizon_profile",
            "elevation_reference_label": "Titik terendah profil ufuk = 0°",
        }

    def detect_prominent_obstacles(
        self,
        elevations: np.ndarray,
        azimuths: np.ndarray,
        horizon_y: np.ndarray,
        img_w: int,
        img_h: int,
        min_prominence: float = 0.05,
        max_peaks: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Mendeteksi objek-objek rintangan yang menonjol di atas garis ufuk mar'i
        (misal menara pemancar, puncak bukit, gedung, atau pohon tinggi).

        Jumlah objek terdeteksi murni dinamis (0, 1, 2, dst) sesuai dengan
        banyaknya objek yang benar-benar menonjol dalam citra, tidak dipaksakan
        harus ada 5 objek.

        Mengembalikan daftar objek dengan koordinat piksel (x, y) serta
        sudut astronomis:
        - Derajat Horizontal (Azimuth awal & akhir sesuai LEBAR objek)
        - Derajat Vertikal (Elevasi / Altitudo dalam derajat)
        - Nilai prominensi / kenaikan tinggi relatif
        """
        from scipy.signal import find_peaks

        # Jarak lama img_w//28 (~45 px pada 1280 px) membuang menara yang
        # berdekatan. Kandidat detail tetap akan dideduplikasi berdasarkan
        # rentang objek, bukan dibuang hanya berdasarkan jarak puncak.
        min_dist = max(5, img_w // 100)
        peaks, props = find_peaks(elevations, prominence=min_prominence, distance=min_dist)

        proms = props.get("prominences", np.zeros(len(peaks)))
        left_bases = props.get("left_bases", peaks)
        right_bases = props.get("right_bases", peaks)

        # Jika max_peaks ditentukan secara eksplisit, batasi; jika None, deteksi semua objek riil
        if max_peaks is not None and max_peaks > 0 and len(peaks) > max_peaks:
            top_indices = np.argsort(proms)[::-1][:max_peaks]
            top_peaks = sorted(peaks[top_indices])
        else:
            top_peaks = sorted(peaks)

        # Tambahkan kandidat dari detector citra, termasuk endpoint yang tidak
        # mungkin ditemukan oleh scipy.find_peaks. Kandidat yang overlap dengan
        # peak profil akan memakai metadata detail tanpa membuat label ganda.
        detail_candidates = list(self.last_detail_obstacles or [])
        combined_peaks = list(top_peaks)
        for detail_obs in detail_candidates:
            dx = int(detail_obs.get("x", -1))
            ds = int(detail_obs.get("x_start", dx))
            de = int(detail_obs.get("x_end", dx))
            if dx < 0 or dx >= len(elevations):
                continue
            overlapping = [int(px) for px in combined_peaks if ds - 2 <= int(px) <= de + 2]
            # Satu struktur dapat menghasilkan beberapa puncak kecil pada kisi.
            # Pertahankan hanya puncak tertinggi agar label objek tidak ganda.
            if overlapping:
                best = max(overlapping, key=lambda px: float(elevations[px]))
                combined_peaks = [px for px in combined_peaks if px not in overlapping or px == best]
            else:
                combined_peaks.append(dx)
        combined_peaks = sorted(set(combined_peaks))

        n = len(elevations)
        obstacles = []
        for i, px in enumerate(combined_peaks):
            pos = np.where(peaks == px)[0]
            pi = int(pos[0]) if len(pos) > 0 else -1
            matching_detail = next((
                item for item in detail_candidates
                if int(item.get("x_start", item.get("x", -1))) - 2 <= px
                <= int(item.get("x_end", item.get("x", -1))) + 2
            ), None)
            if pi >= 0:
                prom_val = float(proms[pi])
            elif matching_detail is not None:
                ds = max(0, int(matching_detail.get("x_start", px)) - 3)
                de = min(n - 1, int(matching_detail.get("x_end", px)) + 3)
                neighbors = np.concatenate((elevations[ds:px], elevations[px + 1:de + 1]))
                local_base = float(np.median(neighbors)) if len(neighbors) else 0.0
                prom_val = max(0.0, float(elevations[px]) - local_base)
            else:
                prom_val = 0.0
            py = float(horizon_y[px])
            az = float(azimuths[px])
            alt = float(elevations[px])

            # --- LEBAR OBJEK ---
            # Mulai dari kaki prominensi, lalu dipersempit memakai ambang 12% tinggi
            # prominensi agar lebar mengikuti bentuk objek (bukan seluruh lereng).
            if matching_detail is not None:
                x_start = int(matching_detail.get("x_start", px))
                x_end = int(matching_detail.get("x_end", px))
            else:
                x_start = int(left_bases[pi]) if pi >= 0 else int(px)
                x_end = int(right_bases[pi]) if pi >= 0 else int(px)
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
                mid_left = int(round((combined_peaks[i - 1] + px) / 2.0))
                x_start = max(x_start, mid_left)
            if i < len(combined_peaks) - 1:
                mid_right = int(round((px + combined_peaks[i + 1]) / 2.0))
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

            classification = self._classify_skyline_obstacle(
                x_start=x_start,
                x_end=x_end,
                tip_x=int(px),
                tip_y=py,
                horizon_y=horizon_y,
                detail_meta=matching_detail,
            )
            auto_label = classification["label"]
            class_confidence = float(classification["confidence"])

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
                "confidence": float(matching_detail.get("confidence", 0.0)) if matching_detail else None,
                "continuity": float(matching_detail.get("continuity", 0.0)) if matching_detail else None,
                "contrast": float(matching_detail.get("contrast", 0.0)) if matching_detail else None,
                "is_endpoint": bool(matching_detail.get("is_endpoint", False)) if matching_detail else False,
                "source": matching_detail.get("source", "profile_peak") if matching_detail else "profile_peak",
                "object_class": classification["class"],
                "classification_confidence": class_confidence,
                "classification_features": classification["features"],
                "auto_label": auto_label,
                "label": auto_label,
                "text": f"{auto_label}: Az {az_start:.2f}-{az_end:.2f} deg | Alt {alt:+.2f} deg",
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
        show_target_meridian: bool = True,
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

        # 2. Gambar garis meridian merah dan retikel bidik (hanya jika diaktifkan)
        if show_target_meridian and target_x is not None and 0 <= target_x < w:
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
        if show_target_meridian and target_x is not None and 0 <= target_x < w and target_info is not None:
            tx_box, ty_box, box_top, box_w, box_h, txt = target_info
            cv2.rectangle(canvas, (tx_box, box_top), (tx_box + box_w, box_top + box_h), (20, 20, 25), -1)
            cv2.rectangle(canvas, (tx_box, box_top), (tx_box + box_w, box_top + box_h), (0, 50, 255), 1, cv2.LINE_AA)
            cv2.putText(
                canvas, txt, (tx_box + 8, ty_box),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA
            )

        return canvas
