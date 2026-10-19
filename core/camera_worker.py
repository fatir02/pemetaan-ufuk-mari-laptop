"""
camera_worker.py
Modul QThread asinkron untuk live streaming kamera USB (eyepiece) menggunakan OpenCV.
Mencegah UI GUI membeku (freeze) dan mendukung mode simulasi jika kamera fisik tidak tersedia.
"""

import sys
import time
from typing import Optional
import numpy as np
import cv2
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker

from core.sample_generator import generate_synthetic_horizon


def _camera_backends():
    """Urutan backend OpenCV yang sesuai dengan sistem operasi."""
    if sys.platform == "darwin":
        return [cv2.CAP_AVFOUNDATION, cv2.CAP_ANY]
    if sys.platform.startswith("win"):
        return [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
    return [cv2.CAP_V4L2, cv2.CAP_ANY]


def _open_camera(index: int):
    """Coba satu indeks dengan backend native lalu fallback CAP_ANY."""
    for backend in _camera_backends():
        cap = None
        try:
            cap = cv2.VideoCapture(index, backend)
            if cap.isOpened():
                return cap
        except Exception:
            pass
        if cap is not None:
            cap.release()
    return None


def find_best_camera_index(preferred: Optional[int] = None) -> int:
    """
    Mendeteksi dan memprioritaskan kamera eksternal USB (seperti Logitech C270 / Eyepiece)
    sebelum memilih webcam internal laptop (index 0).
    """
    candidates = []
    if preferred is not None and preferred >= 0:
        candidates.append(int(preferred))
    # Kamera eksternal diprioritaskan setelah preferred; indeks 0 tetap menjadi
    # fallback kamera internal laptop.
    candidates.extend(idx for idx in [1, 2, 3, 0] if idx not in candidates)
    for idx in candidates:
        cap = None
        try:
            cap = _open_camera(idx)
            if cap is not None:
                # Beberapa webcam memerlukan beberapa frame untuk warm-up.
                ret = False
                for _ in range(5):
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        break
                cap.release()
                if ret:
                    return idx
        except Exception:
            if cap is not None:
                cap.release()

    return int(preferred) if preferred is not None and preferred >= 0 else -1


class CameraWorker(QThread):
    """
    QThread pekerja untuk membaca frame video dari kamera USB secara kontinu.
    """
    frame_ready = pyqtSignal(np.ndarray)
    fps_updated = pyqtSignal(float)
    status_changed = pyqtSignal(bool, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, camera_index: Optional[int] = None, is_simulation: bool = False, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.is_simulation = is_simulation
        self._running = False
        self._mutex = QMutex()
        self._last_frame = None
        self._fps = 0.0
        self._sim_offset = 0

    def set_camera_index(self, index: int, is_simulation: bool = False):
        """Mengatur indeks kamera baru atau beralih ke mode simulasi."""
        with QMutexLocker(self._mutex):
            self.camera_index = index
            self.is_simulation = is_simulation

    def get_current_frame(self) -> Optional[np.ndarray]:
        """Mengambil frame aktif terakhir secara aman antar-thread."""
        with QMutexLocker(self._mutex):
            if self._last_frame is not None:
                return self._last_frame.copy()
            return None

    def stop(self):
        """Menghentikan streaming kamera."""
        self._running = False
        self.wait(1500)

    def run(self):
        self._running = True

        cap = None
        if not self.is_simulation:
            self.status_changed.emit(True, "Mencari kamera fisik...")
            selected_index = find_best_camera_index(self.camera_index)
            if selected_index >= 0:
                self.camera_index = selected_index
                cap = _open_camera(selected_index)

            if cap is None or not cap.isOpened():
                self.error_occurred.emit(
                    "Kamera fisik tidak dapat dibuka. Periksa izin kamera sistem, "
                    "pastikan kamera tidak digunakan aplikasi lain, lalu coba lagi."
                )
                if cap is not None:
                    cap.release()
                self._running = False
                self.status_changed.emit(False, "Kamera tidak tersedia")
                return
            else:
                # Set resolusi standar HD 1280x720 jika didukung
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                cap.set(cv2.CAP_PROP_FPS, 30)

        self.status_changed.emit(
            True,
            f"Kamera terhubung ({'Simulasi' if self.is_simulation else f'Device #{self.camera_index}'})",
        )

        # Baseline simulasi jika dalam mode simulasi
        base_sim_frame = None
        if self.is_simulation:
            base_sim_frame = generate_synthetic_horizon(1280, 720)

        frame_count = 0
        t_start = time.time()

        while self._running:
            loop_start = time.time()

            if self.is_simulation:
                # Mode simulasi: buat sedikit pergeseran halus awan/angin untuk efek live stream
                self._sim_offset = (self._sim_offset + 1) % 1280
                frame = base_sim_frame.copy()
                # Tambahkan noise sensor halus realistis
                noise = np.random.normal(0, 1.5, frame.shape).astype(np.int16)
                noisy_frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
                # Timestamp di sudut
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                cv2.putText(
                    noisy_frame, f"[SIMULASI FALAK LIVE] {ts}", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2, cv2.LINE_AA
                )
                ret = True
                current_frame = noisy_frame
                time.sleep(0.033)  # ~30 FPS
            else:
                ret, current_frame = cap.read()
                if not ret:
                    self.error_occurred.emit("Kamera terputus atau frame tidak terbaca.")
                    break

            if ret and current_frame is not None:
                with QMutexLocker(self._mutex):
                    self._last_frame = current_frame.copy()

                self.frame_ready.emit(current_frame)
                frame_count += 1

                # Hitung FPS tiap 15 frame
                if frame_count % 15 == 0:
                    dt = time.time() - t_start
                    if dt > 0:
                        self._fps = frame_count / dt
                        self.fps_updated.emit(self._fps)

        if cap is not None:
            cap.release()

        self._running = False
        self.status_changed.emit(False, "Kamera dinonaktifkan")
