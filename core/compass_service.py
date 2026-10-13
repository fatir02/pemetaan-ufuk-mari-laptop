"""
compass_service.py
Service pembaca serial sensor kompas (BNO055 / QMC5883L) asinkron dan thread-safe.
Mendukung auto-detect port COM dan auto-reconnect tanpa memblokir GUI/Web server.
"""

import time
import json
import threading
from typing import Dict, Any, Optional

try:
    import serial
    import serial.tools.list_ports as list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    serial = None
    list_ports = None
    SERIAL_AVAILABLE = False


class CompassService:
    def __init__(self, default_port: str = "COM7", baudrate: int = 115200):
        self.default_port = default_port
        self.baudrate = baudrate
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = {
            "azimuth": 270.0,
            "tilt": 0.0,
            "cal_mag": 0,
            "cal_gyro": 0,
            "connected": False,
            "port": default_port,
            "status": "Inisialisasi...",
            "last_update": 0,
        }

    def start(self):
        if self._running or not SERIAL_AVAILABLE:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def get_data(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def _find_target_port(self) -> Optional[str]:
        if not list_ports:
            return self.default_port
        ports = list(list_ports.comports())
        for p in ports:
            if p.device.upper() == self.default_port.upper():
                return p.device
        for p in ports:
            desc = (p.description or "").lower()
            if "ch340" in desc or "cp210" in desc or "usb-serial" in desc or "uart" in desc:
                return p.device
        return ports[0].device if ports else None

    def _worker_loop(self):
        while self._running:
            if not SERIAL_AVAILABLE or serial is None:
                with self._lock:
                    self._data["connected"] = False
                    self._data["status"] = "Pyserial belum terpasang"
                time.sleep(2.0)
                continue

            target_port = self._find_target_port()
            if not target_port:
                with self._lock:
                    self._data["connected"] = False
                    self._data["status"] = "Tidak ada port COM terdeteksi"
                time.sleep(1.5)
                continue

            ser = None
            try:
                ser = serial.Serial(target_port, self.baudrate, timeout=1.0)
                ser.reset_input_buffer()
                with self._lock:
                    self._data["connected"] = True
                    self._data["port"] = target_port
                    self._data["status"] = f"Terhubung ke {target_port}"

                while self._running:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
                    if line.startswith("{") and line.endswith("}"):
                        try:
                            parsed = json.loads(line)
                            with self._lock:
                                if "azimuth" in parsed:
                                    self._data["azimuth"] = float(parsed["azimuth"])
                                if "tilt" in parsed:
                                    self._data["tilt"] = float(parsed["tilt"])
                                if "cal_mag" in parsed:
                                    self._data["cal_mag"] = int(parsed.get("cal_mag", 0))
                                if "cal_gyro" in parsed:
                                    self._data["cal_gyro"] = int(parsed.get("cal_gyro", 0))
                                self._data["connected"] = True
                                self._data["status"] = "Data aktif"
                                self._data["last_update"] = time.time()
                        except (ValueError, TypeError):
                            pass
            except serial.SerialException as err:
                err_str = str(err)
                msg = f"Port {target_port} sibuk/terkunci (tutup Serial Monitor Arduino)" if "PermissionError" in err_str or "Access is denied" in err_str else f"Gagal buka {target_port}"
                with self._lock:
                    self._data["connected"] = False
                    self._data["status"] = msg
                time.sleep(1.5)
            except Exception as e:
                with self._lock:
                    self._data["connected"] = False
                    self._data["status"] = f"Error: {e}"
                time.sleep(1.5)
            finally:
                if ser and ser.is_open:
                    try:
                        ser.close()
                    except Exception:
                        pass


# Global singleton instance
compass_service = CompassService()
