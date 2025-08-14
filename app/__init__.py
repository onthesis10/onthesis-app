# /app/__init__.py

import os
import json
from flask import Flask, jsonify, request, redirect, url_for
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore, auth
from flask_login import LoginManager, UserMixin

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

class User(UserMixin):
    """Kelas User sederhana untuk integrasi dengan Flask-Login."""
    def __init__(self, uid):
        self.id = uid # Flask-Login membutuhkan atribut 'id'

@login_manager.user_loader
def load_user(user_id):
    """
    Fungsi ini dipanggil oleh Flask-Login pada setiap request untuk memuat
    objek user dari user ID (yaitu UID Firebase) yang disimpan di session.
    """
    try:
        auth.get_user(user_id)
        return User(uid=user_id)
    except Exception as e:
        print(f"Gagal memuat user dengan ID {user_id}: {e}")
        return None

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
# 4. PENAMBAHAN: Context Processor untuk Firebase Config
# ========================================================================
@app.context_processor
def inject_firebase_config():
    """
    Mengirim konfigurasi Firebase Frontend ke semua template secara otomatis.
    Ini akan menyelesaikan error 'Undefined is not JSON serializable'.
    """
    config_str = os.getenv('FIREBASE_FRONTEND_CONFIG_JSON')
    if config_str:
        try:
            firebase_config = json.loads(config_str)
            return dict(firebase_config=firebase_config)
        except json.JSONDecodeError:
            print("Peringatan: FIREBASE_FRONTEND_CONFIG_JSON tidak valid.")
            return dict(firebase_config={})
    print("Peringatan: FIREBASE_FRONTEND_CONFIG_JSON tidak ditemukan di environment.")
    return dict(firebase_config={})


# ========================================================================
# 5. Impor Rute (WAJIB DI BAGIAN PALING BAWAH)
# ========================================================================
from app import routes
