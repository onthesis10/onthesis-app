# run.py
# File ini adalah titik masuk (entry point) untuk menjalankan aplikasi Anda.
# Cukup jalankan file ini dari terminal dengan perintah: python run.py

from app import app

if __name__ == '__main__':
    # Menjalankan aplikasi Flask dalam mode debug.
    # Mode debug akan otomatis me-reload server jika ada perubahan kode.
    # Host '0.0.0.0' membuat server dapat diakses dari jaringan lokal Anda.
    # Port 5000 adalah port default yang Anda gunakan di fetch JavaScript.
    
    # FIX: Menambahkan use_reloader=False untuk mencegah server crash saat menyimpan file.
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
