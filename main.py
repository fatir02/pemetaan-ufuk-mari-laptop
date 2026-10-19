"""Entry point utama aplikasi.

Release resmi menjalankan antarmuka web melalui ``app_desktop.py``. Menjalankan
``python main.py`` kini menggunakan jalur yang sama agar source dan EXE tidak
lagi menampilkan dua antarmuka berbeda.

UI PyQt lama tetap tersedia melalui ``python legacy_desktop.py``.
"""

from app_desktop import main


if __name__ == "__main__":
    main()
