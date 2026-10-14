# Kuis Matematika

Web kuis ala Quizizz (mode mandiri) dengan Flask + SQLite.

## Jalankan di laptop
    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt
    python app.py
Buka http://127.0.0.1:5000

- Halaman admin: /admin (password bawaan: admin123)
- Murid: masukkan kode kuis di halaman utama

## Ganti password dan kunci rahasia
Atur environment variable `ADMIN_PASSWORD` dan `SECRET_KEY`
(di PythonAnywhere lewat file WSGI, lihat panduan).
