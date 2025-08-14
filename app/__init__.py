# /app/__init__.py

import os
import json
from flask import Flask, jsonify, request, redirect, url_for
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from flask_login import LoginManager

# Memuat environment variables dari file .env
load_dotenv()

# ========================================================================
# 1. Inisialisasi Aplikasi Flask (HANYA DI SINI)
# ========================================================================
app = Flask(__name__)
# Kunci rahasia dipindahkan ke sini agar terpusat
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'kunci-rahasia-default-yang-aman')


# ========================================================================
# 2. Inisialisasi Firebase Admin SDK & Firestore
# ========================================================================
db = None # Definisikan db di luar try-except
try:
    if not firebase_admin._apps:
        # Mengambil kredensial dari environment variable (cara yang benar untuk server)
        firebase_creds_json_str = os.getenv("FIREBASE_CREDENTIALS_JSON")
        if not firebase_creds_json_str:
            raise ValueError("Environment variable FIREBASE_CREDENTIALS_JSON tidak diatur.")

        # Mengubah string JSON menjadi dictionary Python
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


# ========================================================================
# 3. Inisialisasi Flask-Login
# ========================================================================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Halaman login jika user belum terautentikasi

@login_manager.unauthorized_handler
def unauthorized_callback():
    """
    Mengirim balasan JSON saat pengguna yang belum login mencoba mengakses
    rute API yang dilindungi.
    """
    if request.path.startswith('/api/') or request.path.startswith('/generator_kajian_teori/'):
        return jsonify({
            'status': 'error',
            'message': 'Sesi Anda telah berakhir. Silakan muat ulang halaman dan login kembali.'
        }), 401
    return redirect(url_for('login'))


# ========================================================================
# 4. Impor Rute (WAJIB DI BAGIAN PALING BAWAH)
# Ini penting untuk menghindari circular import
# ========================================================================
from app import routes
