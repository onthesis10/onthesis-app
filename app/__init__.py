# ========================================================================
# File: app/__init__.py (Versi untuk Railway/Serverless)
# Deskripsi: Menginisialisasi aplikasi dan membaca kredensial Firebase
#            dari environment variable, bukan dari file.
# ========================================================================

import os
import json # <-- Impor baru untuk membaca string JSON
from flask import Flask, jsonify, request, redirect, url_for
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from flask_login import LoginManager

# --- Konfigurasi Awal ---
load_dotenv()

# 1. Inisialisasi Aplikasi Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'kunci-rahasia-default-yang-aman')

# 2. Inisialisasi Firebase Admin SDK & Firestore (CARA BARU)
try:
    if not firebase_admin._apps:
        # Ambil kredensial dari environment variable FIREBASE_CREDENTIALS_JSON
        firebase_creds_json_str = os.getenv("FIREBASE_CREDENTIALS_JSON")
        if not firebase_creds_json_str:
            raise ValueError("Environment variable FIREBASE_CREDENTIALS_JSON tidak diatur.")

        # Ubah string JSON menjadi dictionary Python
        cred_dict = json.loads(firebase_creds_json_str)

        # Inisialisasi menggunakan dictionary
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        print("--- Firebase Admin SDK berhasil diinisialisasi dari env var. ---")

    # Buat klien Firestore yang akan diimpor oleh file lain
    db = firestore.client()
    print("--- Klien Firestore berhasil diinisialisasi. ---")

except Exception as e:
    print(f"!!! KRITIS: Gagal menginisialisasi Firebase Admin SDK atau Firestore: {e}")
    db = None # Pastikan db ada meskipun gagal

# 3. Inisialisasi Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ========================================================================
# Menambahkan handler untuk permintaan API yang tidak sah
# ========================================================================
@login_manager.unauthorized_handler
def unauthorized_callback():
    """
    Mengirim balasan JSON saat pengguna yang belum login mencoba mengakses
    rute API yang dilindungi.
    """
    if request.path.startswith('/api/'):
        return jsonify({
            'status': 'error',
            'message': 'Sesi Anda telah berakhir. Silakan muat ulang halaman dan login kembali.'
        }), 401
    return redirect(url_for('login'))


# 4. Impor rute setelah semua inisialisasi selesai
# Ini penting untuk menghindari circular import
from app import routes
