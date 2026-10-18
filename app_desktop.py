"""
app_desktop.py
Peluncur Aplikasi Desktop Mandiri (Native Window via Microsoft Edge WebView2).
Menjalankan backend Flask secara lokal di latar belakang dan membungkus seluruh
antarmuka web yang kaya fitur ke dalam satu jendela aplikasi desktop profesional.
"""

import os
import sys
import time
import socket
import threading
import subprocess
import webbrowser

# Pastikan path modul lokal dikenali
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from web_app import app
from core.paths import get_resource_path, get_app_dir


def find_app_browser():
    """Cari browser modern (Edge / Chrome) untuk mode standalone window tanpa address bar."""
    candidates = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def is_port_in_use(port=5000):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for_server(port=5000, timeout=10.0):
    start = time.time()
    while time.time() - start < timeout:
        if is_port_in_use(port):
            return True
        time.sleep(0.2)
    return False


def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True, use_reloader=False)


def main():
    # Jika server belum aktif di port 5000, jalankan di background thread
    if not is_port_in_use(5000):
        t = threading.Thread(target=run_flask, daemon=True)
        t.start()
        wait_for_server(5000)

    # Buka antarmuka website persis seperti semula di browser bawaan
    webbrowser.open("http://127.0.0.1:5000")

    # Jaga proses tetap hidup melayani server
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
