# ========================================================================
# File: app/__init__.py (Versi Final yang Direfactor)
# Deskripsi: Menjadi pusat inisialisasi untuk aplikasi Flask,
#            Firebase Admin, Firestore, dan Flask-Login.
# ========================================================================

import os
# PERUBAHAN: Menambahkan redirect dan url_for ke impor
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

# 2. Inisialisasi Firebase Admin SDK & Firestore
try:
    if not firebase_admin._apps:
        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        if not cred_path:
            raise ValueError("FIREBASE_CREDENTIALS_PATH tidak diatur di file .env")
        
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("--- Firebase Admin SDK berhasil diinisialisasi. ---")
    
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
