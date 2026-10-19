"""
app_desktop.py
Peluncur Aplikasi Desktop Mandiri (native embedded WebView, tanpa Chrome/Chromium).
Menjalankan backend Flask secara lokal di latar belakang dan membungkus seluruh
antarmuka web ke dalam satu jendela aplikasi desktop profesional.

Pengawasan jendela memakai Windows API (ctypes EnumWindows) — tanpa PowerShell,
tanpa jendela konsol yang bermunculan.
Singleton antar-instance memakai named mutex + lock file.
"""
import os
import sys
import time
import socket
import threading
import subprocess
import webbrowser
import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

_T0 = time.time()
_LOG_PATH = None


def log(msg):
    """Catat tahapan start ke berkas log agar masalah startup bisa didiagnosis."""
    global _LOG_PATH
    line = "[%7.2fs pid=%s] %s" % (time.time() - _T0, os.getpid(), msg)
    try:
        if _LOG_PATH is None:
            base = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()),
                                "PemetaanUfukMari")
            os.makedirs(base, exist_ok=True)
            _LOG_PATH = os.path.join(base, "startup.log")
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


log("=== proses exe mulai ===")


# ---------------- SINGLETON ANTAR-INSTANCE ----------------

_MUTEX_NAME = "PemetaanUfukMariAppSingleton"
_MUTEX_HANDLE = None


def acquire_mutex_nonblocking():
    """Kunci singleton antar-instance (named mutex Windows).

    True  = kita pemilik kunci (tidak ada instance lain yang hidup)
    False = instance lain sedang memegang kunci
    Kunci otomatis lepas saat proses pemiliknya mati.
    """
    global _MUTEX_HANDLE
    import ctypes
    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = k32.CreateMutexW(None, False, _MUTEX_NAME)
        if not handle:
            log("mutex CreateMutexW gagal (handle=None): error=%d" % ctypes.get_last_error())
            return True  # anggap punya kunci agar tetap jalan
        last = ctypes.get_last_error()
        if last == 183:  # ERROR_ALREADY_EXISTS
            log("mutex sudah ada: instance lain hidup -> satukan")
            k32.CloseHandle(handle)
            return False
        _MUTEX_HANDLE = handle
        log("satu-satunya: kunci mutex didapat")
        return True
    except Exception as e:
        log("mutex exception: %r" % (e,))
        return True


# ---------------- PENCARIAN BROWSER & PORT ----------------

def find_app_browser():
    """Cari browser modern (Edge / Chrome) untuk mode standalone window tanpa address bar."""
    if sys.platform == "darwin":
        candidates = [
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    elif sys.platform.startswith("win"):
        candidates = [
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
    else:
        candidates = [
            "/usr/bin/microsoft-edge", "/usr/bin/microsoft-edge-stable",
            "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium",
        ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def find_free_port(start_port=5000, max_attempts=200):
    """Cari port TCP lokal yang benar-benar bebas dan BISA DIPAKAI.

    Dua cek digabung karena masing-masing punya kelemahan di Windows:
    1. connect_ex: listener 0.0.0.0:port oleh proses lain terdeteksi,
       tetapi port yang cuma di-bind tanpa listen lolos.
    2. bind: pada Windows, bind 127.0.0.1:port masih bisa SUKSES meski
       proses lain sudah listen di 0.0.0.0:port, sehingga bentrok lolos.
    Port dianggap aman hanya jika TIDAK bisa di-connect DAN bisa di-bind.
    """
    for p in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) == 0:
                continue  # port dipakai proses lain
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
            except OSError:
                continue
        return p
    return start_port


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _page_is_our_app(head):
    return "Ufuk Mar" in head


def server_healthy_on(port):
    """Cek satu port: apakah server aplikasi ini masih menjawab."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1.5) as r:
            head = r.read(2048).decode("utf-8", "replace")
            return r.status == 200 and _page_is_our_app(head)
    except Exception:
        return False


def find_healthy_app_port(start_port=5000, end_port=5200):
    """Cari server APLIKASI INI yang masih hidup di port mana pun."""
    import urllib.request
    for p in range(start_port, end_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.35)
            if s.connect_ex(("127.0.0.1", p)) != 0:
                continue
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{p}/", timeout=1.2) as r:
                head = r.read(2048).decode("utf-8", "replace")
                if r.status == 200 and _page_is_our_app(head):
                    return p
        except Exception:
            continue
    return None


def wait_for_server(port, timeout=120.0):
    """Tunggu sampai server Flask BENAR-BENAR menjawab HTTP 200 berisi aplikasi."""
    import urllib.request
    import urllib.error

    url = f"http://127.0.0.1:{port}/"
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                head = resp.read(2048).decode("utf-8", "replace")
                if resp.status == 200 and _page_is_our_app(head):
                    return True
        except (urllib.error.URLError, OSError, ValueError):
            pass
        time.sleep(0.15)
    return False


# ---------------- PENGAWASAN JENDELA (Windows API, tanpa PowerShell) ----------------

def _find_app_hwnds():
    """Kumpulkan handle (hwnd) seluruh jendela aplikasi yang terbuka.

    Memakai Windows API langsung (ctypes) — tanpa menjalankan proses apa pun.
    """
    if not sys.platform.startswith("win"):
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hwnds = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n > 0:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                t = buf.value
                if ("Pemetaan Ufuk Mar'i" in t) or ("Pemetaan Profil Ufuk" in t):
                    hwnds.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return hwnds


def app_window_exists(profile_root=None):
    """Cek apakah jendela aplikasi (Edge app mode) masih terbuka."""
    return len(_find_app_hwnds()) > 0


def focus_app_window():
    """Bawa jendela aplikasi yang sudah terbuka ke depan. True bila ada."""
    import ctypes
    user32 = ctypes.windll.user32
    hwnds = _find_app_hwnds()
    if not hwnds:
        return False
    hwnd = hwnds[0]
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.keybd_event(0x12, 0, 0, 0)   # ALT ditekan
    user32.keybd_event(0x12, 0, 2, 0)   # ALT dilepas
    user32.SetForegroundWindow(hwnd)
    return True


def close_stale_app_windows():
    """Tutup jendela-jendela aplikasi lama yang servernya sudah mati (zombie)."""
    if not sys.platform.startswith("win"):
        return
    import ctypes
    user32 = ctypes.windll.user32
    WM_CLOSE = 0x0010
    for hwnd in _find_app_hwnds():
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        log("jendela lama (zombie) ditutup: hwnd %s" % hwnd)


# ---------------- SERVER FLASK ----------------

def run_flask(port):
    import logging
    # 'app' diimpor DI DALAM fungsi agar selalu tersedia apa pun urutan
    # eksekusi main(); menghindari NameError bila modul dimuat ulang.
    from web_app import app as flask_app
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    log("server Flask akan mendengarkan di port %s" % port)
    try:
        flask_app.run(host="127.0.0.1", port=port, debug=False, threaded=True, use_reloader=False)
    except SystemExit as e:
        log("Flask SystemExit: %r" % (e,))
        raise
    except BaseException as e:
        import traceback
        log("FLASK GAGAL JALAN: %r" % (e,))
        log("traceback: %s" % traceback.format_exc()[-1500:])


def show_starting_window(state):
    """Jendela tunggu: kotak dialog native Windows, auto-close, non-blokir.

    Tkinter TIDAK dipakai lagi: kombinasi Tkinter di thread utama + Flask di
    thread latar terbukti memicu crash 'Tcl_AsyncDelete: async handler deleted
    by the wrong thread' (tcl86t.dll) yang membunuh seluruh proses aplikasi.
    Kotak dialog native (MessageBoxTimeoutW) bebas dari masalah itu dan
    menutup sendiri otomatis.
    """
    if not sys.platform.startswith("win"):
        return
    import ctypes
    import threading

    MB_SETFOREGROUND = 0x00010000
    MB_TOPMOST = 0x00040000
    MB_ICONINFORMATION = 0x00000040
    MB_OK = 0x00000000

    def worker():
        try:
            # Dialog tampil di thread daemon; menutup sendiri setelah 15 detik
            # atau lebih cepat bila user klik OK. Tidak memblokir thread utama.
            ctypes.windll.user32.MessageBoxTimeoutW(
                0,
                "Menyiapkan mesin analisis...\n\nKlik OK, atau jendela tertutup otomatis.",
                "Pemetaan Ufuk Mar'i",
                MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND | MB_TOPMOST,
                0,
                15000,  # auto-close 15 detik
            )
            log("splash: dialog tunggu selesai")
        except Exception as e:
            log("splash dialog gagal (tidak fatal): %r" % (e,))

    threading.Thread(target=worker, daemon=True).start()


# ---------------- IZIN KAMERA (tanpa flag terlarang) ----------------

def _grant_camera_permission(profile_root, port):
    """Catat izin kamera otomatis untuk Origin aplikasi di profil Edge."""
    import json

    try:
        pref_path = os.path.join(profile_root, "Default", "Preferences")
        os.makedirs(os.path.dirname(pref_path), exist_ok=True)

        prefs = {}
        if os.path.exists(pref_path):
            try:
                with open(pref_path, encoding="utf-8") as f:
                    prefs = json.load(f)
            except (ValueError, OSError):
                prefs = {}

        origin = f"http://127.0.0.1:{port}"
        prof = prefs.setdefault("profile", {})
        cset = prof.setdefault("content_settings", {})
        exceptions = cset.setdefault("exceptions", {})
        media_camera = exceptions.setdefault("media_stream_camera", {})
        media_mic = exceptions.setdefault("media_stream_mic", {})
        setting = {"setting": 1, "origin": origin, "embedded": None}
        media_camera[origin] = dict(setting)
        media_mic[origin] = dict(setting)

        with open(pref_path, "w", encoding="utf-8") as f:
            json.dump(prefs, f)
        log("izin kamera ditetapkan untuk %s" % origin)
    except Exception as e:
        log("izin kamera gagal ditulis (tidak fatal): %r" % (e,))


def _open_window_to(port):
    """Fallback lama: buka browser eksternal bila diminta secara eksplisit."""
    browser = find_app_browser()
    url = f"http://127.0.0.1:{port}"
    profile_root = os.path.join(
        os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".pemetaan-ufuk-mari"),
        "PemetaanUfukMari",
        "browser_profile",
    )
    os.makedirs(profile_root, exist_ok=True)
    _grant_camera_permission(profile_root, port)
    if browser:
        subprocess.Popen([
            browser,
            f"--app={url}",
            f"--user-data-dir={profile_root}",
            "--window-size=1360,860",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-translate",
            "--autoplay-policy=no-user-gesture-required",
        ])
        log("jendela dibuka ke server sehat %s" % url)
    else:
        webbrowser.open(url)
        log("browser default dibuka ke %s" % url)


def open_embedded_window(port):
    """Buka UI pada WebView native dan blokir sampai jendela ditutup.

    pywebview memakai WKWebView/WebKit di macOS (termasuk Hackintosh) dan
    WebView2 di Windows, sehingga Chrome/Chromium tidak dijalankan sebagai UI.
    """
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError(
            "Komponen native webview belum terpasang. Jalankan: "
            "python -m pip install -r requirements.txt"
        ) from exc

    if sys.platform == "darwin":
        _configure_macos_camera_webview()

    url = f"http://127.0.0.1:{port}"
    storage_path = os.path.join(
        os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".pemetaan-ufuk-mari"),
        "native_webview",
    )
    os.makedirs(storage_path, exist_ok=True)
    log("membuka native webview ke %s" % url)
    webview.create_window(
        "Pemetaan Ufuk Mar'i",
        url=url,
        width=1360,
        height=860,
        min_size=(960, 640),
        resizable=True,
        background_color="#0b0f17",
        text_select=True,
        zoomable=False,
    )
    # Pemilihan engine otomatis: Cocoa/WKWebView pada macOS dan WebView2 pada
    # Windows. start() sengaja berjalan di main thread sesuai syarat pywebview.
    webview.start(
        debug=False,
        private_mode=False,
        storage_path=storage_path,
        icon=os.path.join(BASE_DIR, "assets", "icon.png"),
    )
    log("native webview ditutup")


def _invoke_objc_block(block_obj, value):
    """Panggil block Objective-C ``void (^)(NSInteger)`` dari PyObjC.

    Block yang diterima dari WKUIDelegate tidak membawa metadata signature,
    sehingga ``block(value)`` gagal dengan "cannot call block without a
    signature". Pemanggilan langsung lewat ABI block layout diperlukan:
    ``isa, flags, reserved, invoke, descriptor`` — fungsi invoke ada di offset
    ketiga (indeks 2 dari array pointer).
    """
    import ctypes

    import objc

    ptr = objc.pyobjc_id(block_obj)
    if not ptr:
        raise RuntimeError("block Objective-C tidak memiliki pointer")
    words = (ctypes.c_void_p * 4).from_address(ptr)
    invoke = words[2]
    if not invoke:
        raise RuntimeError("block Objective-C tidak memiliki fungsi invoke")
    ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_long)(invoke)(
        ctypes.c_void_p(ptr), ctypes.c_long(int(value))
    )


def _configure_macos_camera_webview():
    """Izinkan getUserMedia pada WKWebView yang dibungkus pywebview.

    pywebview 6.x belum memasang callback permission media pada Cocoa. Tanpa
    callback ini WKWebView dapat menolak kamera lokal sebelum dialog izin macOS
    muncul. Origin aplikasi hanya server loopback yang dibuat launcher ini.
    """
    try:
        import AppKit
        import Foundation
        import WebKit
        import objc
        from webview.platforms import cocoa

        bundle = AppKit.NSBundle.mainBundle()
        info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        info["NSCameraUsageDescription"] = (
            "Kamera digunakan untuk mengambil foto profil ufuk secara langsung."
        )

        selector_name = (
            "webView_requestMediaCapturePermissionForOrigin_"
            "initiatedByFrame_type_decisionHandler_"
        )
        delegate = cocoa.BrowserView.BrowserDelegate
        if not hasattr(delegate, selector_name):
            # Signature: void (self, _cmd, WKWebView*, WKSecurityOrigin*,
            # WKFrameInfo*, NSInteger type, block decisionHandler).
            # 'type' adalah NSInteger (q) dan decisionHandler adalah block (@?).
            def grant_camera(self, webview_obj, origin, frame, capture_type, handler):
                # Handler wajib dipanggil tepat sekali. Bila ada error saat
                # membaca origin, tetap berikan keputusan agar getUserMedia
                # tidak menggantung.
                decision = WebKit.WKPermissionDecisionDeny
                try:
                    host = ""
                    try:
                        host = str(origin.host() or "").lower()
                    except Exception:
                        host = ""
                    allowed = host in {"127.0.0.1", "localhost"}
                    decision = (
                        WebKit.WKPermissionDecisionGrant
                        if allowed
                        else WebKit.WKPermissionDecisionDeny
                    )
                    log(
                        "permintaan izin media webview host=%r type=%s -> %s"
                        % (host, capture_type, decision)
                    )
                except Exception as exc:
                    log("gagal mengevaluasi izin media webview: %r" % (exc,))
                finally:
                    try:
                        _invoke_objc_block(handler, decision)
                    except Exception as exc:
                        log("gagal memanggil decisionHandler media: %r" % (exc,))

            grant_camera = objc.selector(
                grant_camera,
                selector=(
                    b"webView:requestMediaCapturePermissionForOrigin:"
                    b"initiatedByFrame:type:decisionHandler:"
                ),
                signature=b"v@:@@@q@?<v@q>",
            )
            setattr(delegate, selector_name, grant_camera)

        log("izin kamera WKWebView dikonfigurasi untuk origin loopback")
    except Exception as exc:
        # Jangan menggagalkan seluruh aplikasi; UI akan memberikan pesan izin
        # getUserMedia jika versi WebKit tidak mendukung callback tersebut.
        log("konfigurasi izin kamera WKWebView gagal: %r" % (exc,))


def launch_application_window(port):
    """Jalankan native WebView; browser fallback harus diizinkan eksplisit."""
    try:
        open_embedded_window(port)
        return True
    except Exception as exc:
        log("native webview gagal: %r" % (exc,))
        if os.environ.get("PEMETAAN_ALLOW_BROWSER_FALLBACK") == "1":
            _open_window_to(port)
            return True

        message = (
            "Jendela native WebView gagal dibuka.\n\n"
            f"{exc}\n\n"
            "Pasang ulang dependensi dengan:\n"
            "python -m pip install -r requirements.txt"
        )
        if sys.platform.startswith("win"):
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, message, "Pemetaan Ufuk Mar'i", 0x10)
            except Exception:
                print(message, file=sys.stderr)
        else:
            print(message, file=sys.stderr)
        return False


def converge_to_existing(port):
    """Satukan ke instance yang sudah jalan: fokuskan jendelanya."""
    for _ in range(10):
        if not server_healthy_on(port):
            log("server port %s sudah tidak sehat" % port)
            close_stale_app_windows()
            return False
        if focus_app_window():
            log("jendela aplikasi yang ada difokuskan (port %s)" % port)
            return True
        time.sleep(1.0)
    return launch_application_window(port)


# ---------------- PROGRAM UTAMA ----------------

def main():
    # ---- KUNCI SINGLETON: dicek PALING AWAL, sebelum proses lain jalan ----
    if not acquire_mutex_nonblocking():
        log("instance lain sedang berjalan -> satukan ke instance itu")
        existing = find_healthy_app_port(5000, 5200)
        if existing is not None and converge_to_existing(existing):
            return
        close_stale_app_windows()
        log("lanjut start instance baru")

    # Tutup sisa jendela zombie dari sesi yang mati tak wajar
    close_stale_app_windows()

    from web_app import app
    log("modul web_app selesai diimpor")

    port = find_free_port(5000)
    state = {"ready": False, "failed": False}

    # Server Flask berjalan di thread latar
    threading.Thread(target=run_flask, args=(port,), daemon=True).start()

    def wait_worker():
        log("menunggu server siap...")
        ok = wait_for_server(port, timeout=120.0)
        log("server siap=%s" % ok)
        if ok:
            state["ready"] = True
        else:
            state["failed"] = True

    threading.Thread(target=wait_worker, daemon=True).start()

    # Dialog tunggu native (non-blokir) + tunggu langsung sampai server siap
    show_starting_window(state)

    # Tunggu di thread utama sampai server siap (wait_worker mengubah state)
    deadline = time.time() + 125.0
    while not state.get("ready") and not state.get("failed") and time.time() < deadline:
        time.sleep(0.2)

    if not state.get("ready"):
        log("GAGAL: server tidak pernah siap")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                "Mesin analisis gagal dijalankan.\n\n"
                "Tutup aplikasi lain yang mungkin memakai port yang sama, "
                "lalu jalankan kembali aplikasi ini.",
                "Pemetaan Ufuk Mar'i",
                0x00000010 | 0x00010000 | 0x00040000,  # ERROR | SETFOREGROUND | TOPMOST
            )
        except Exception:
            pass
        return

    time.sleep(0.6)

    try:
        launch_application_window(port)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        log("launcher selesai")


if __name__ == "__main__":
    main()
