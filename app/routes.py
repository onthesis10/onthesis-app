# /app/routes.py

import os
from flask import (render_template, request, redirect, url_for, 
                   flash, session, jsonify, Response)
from dotenv import load_dotenv
import google.generativeai as genai
from firebase_admin import auth
import markdown
import json
import pandas as pd
import numpy as np
from scipy import stats
import statsmodels.api as sm
from io import BytesIO
import matplotlib.pyplot as plt
import base64

# ========================================================================
# 1. Impor 'app' dari __init__.py (Struktur yang Benar)
# ========================================================================
from app import app, db 

# Impor fungsi-fungsi dari utils.py
from app.utils import (
    search_references_crossref,
    generate_outline_with_ai,
    generate_subchapter_with_ai,
    review_and_compile_with_ai,
    export_to_docx,
    export_to_pdf
)

# --- Inisialisasi Gemini API (cukup sekali di sini) ---
load_dotenv()
try:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("Peringatan: GEMINI_API_KEY tidak ditemukan di .env")
    print("Konfigurasi Gemini API akan digunakan dari utils.py")
except Exception as e:
    print(f"Error terkait inisialisasi Gemini API di routes.py: {e}")


# ========================================================================
# --- Routes Utama dan Autentikasi (DIPERBAIKI) ---
# ========================================================================
@app.route('/')
def index():
    """Rute utama, akan mengarahkan ke login atau dashboard."""
    if 'user' in session:
        return redirect(url_for('dashboard'))
    # Mengarahkan ke fungsi login yang menampilkan halaman
    return redirect(url_for('login'))

@app.route('/login', methods=['GET'])
def login():
    """Fungsi ini HANYA untuk menampilkan halaman login."""
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/verify-token', methods=['POST'])
def verify_google_token():
    """
    Endpoint ini menangani verifikasi token dan MENGEMBALIKAN JSON.
    Versi ini lebih robust untuk menangani berbagai format request.
    """
    id_token = None
    
    # Menambahkan log untuk debugging
    print(f"Request Headers: {request.headers}")
    print(f"Request is_json: {request.is_json}")

    # Metode 1: Cek jika request adalah JSON (cara yang benar)
    if request.is_json:
        try:
            data = request.get_json()
            id_token = data.get('id_token')
            print("Mencoba mengambil token dari JSON body.")
        except Exception as e:
            print(f"Gagal mem-parsing JSON: {e}")
            pass
    
    # Metode 2: Jika bukan JSON, cek sebagai form data
    if not id_token:
        id_token = request.form.get('id_token')
        if id_token:
            print("Token ditemukan di form data.")

    # Metode 3: Jika masih tidak ada, coba baca raw data (untuk kasus header salah)
    if not id_token:
        try:
            print("Token tidak ditemukan, mencoba membaca raw data.")
            raw_data = request.get_data(as_text=True)
            print(f"Raw data received: {raw_data}")
            data = json.loads(raw_data)
            id_token = data.get('id_token')
            if id_token:
                print("Token ditemukan setelah parsing raw data.")
        except Exception:
            # Gagal parsing raw data, berarti formatnya aneh atau kosong
            pass

    # Final check: jika token tetap tidak ditemukan
    if not id_token:
        print("FINAL: ID Token tidak ditemukan di semua metode (JSON, Form, Raw).")
        return jsonify({"status": "error", "message": "ID token tidak ditemukan dalam request."}), 400
    
    try:
        # Verifikasi token dengan Firebase Admin SDK
        print("Memverifikasi ID Token dengan Firebase...")
        decoded_token = auth.verify_id_token(id_token)
        # Simpan informasi user di session server
        session['user'] = decoded_token
        session.permanent = True
        print("Verifikasi berhasil. Mengarahkan ke dashboard.")
        # Kirim respons sukses dalam format JSON
        return jsonify({
            "status": "success", 
            "message": "Login berhasil!",
            "redirect_url": url_for('dashboard')
        })
    except Exception as e:
        error_message = f"Verifikasi token gagal: {str(e)}"
        print(error_message) # Log error di server untuk debugging
        # Kirim respons error dalam format JSON
        return jsonify({"status": "error", "message": error_message}), 401

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Anda telah berhasil logout.')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

# ========================================================================
# --- Routes Fitur-Fitur Statis Lainnya (Tetap Utuh) ---
# ========================================================================
@app.route('/projects')
def projects():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('projects.html')

@app.route('/writing_assistant')
def writing_assistant():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('writing_assistant.html')

# ... (Semua rute statis lainnya tetap sama persis) ...
@app.route('/paraphrase_ai')
def paraphrase_ai():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('paraphrase_ai.html')

@app.route('/search_references')
def search_references():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('search_references.html')

@app.route('/citation_management')
def citation_management():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('citation_management.html')

@app.route('/chat_ai')
def chat_ai():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('chat_ai.html')

@app.route('/data_analysis')
def data_analysis():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('data_analysis.html')

@app.route('/user-profile')
def user_profile():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('user-profile.html')

@app.route('/upgrade')
def upgrade():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('upgrade.html')

# ========================================================================
# --- Routes Fitur Generator (Lama & Lengkap) ---
# ========================================================================
@app.route('/generator_latar_belakang', methods=['GET', 'POST'])
def generator_latar_belakang():
    if 'user' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        pass
    return render_template('generator_latar_belakang.html')

@app.route('/generator_rumusan_masalah', methods=['GET', 'POST'])
def generator_rumusan_masalah():
    if 'user' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        pass
    return render_template('generator_rumusan_masalah.html')

# ========================================================================
# --- Routes Analisis Data (Lengkap & Utuh) ---
# ========================================================================
@app.route('/descriptive_statistics', methods=['GET', 'POST'])
def descriptive_statistics():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            try:
                df = pd.read_csv(file) if file.filename.endswith('.csv') else pd.read_excel(file)
                description = df.describe().to_html(classes='table table-striped w-full')
                return render_template('descriptive_statistics.html', tables=[description], titles=df.columns.values)
            except Exception as e:
                flash(f'Error processing file: {e}')
                return redirect(request.url)
    return render_template('descriptive_statistics.html')

@app.route('/normality_test', methods=['GET', 'POST'])
def normality_test():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            try:
                df = pd.read_csv(file) if file.filename.endswith('.csv') else pd.read_excel(file)
                results = {}
                for column in df.select_dtypes(include=np.number).columns:
                    stat, p = stats.shapiro(df[column].dropna())
                    results[column] = {'stat': stat, 'p': p, 'is_normal': p > 0.05}
                return render_template('normality_test.html', results=results)
            except Exception as e:
                flash(f'Error processing file: {e}')
                return redirect(request.url)
    return render_template('normality_test.html')

@app.route('/homogeneity_test', methods=['GET', 'POST'])
def homogeneity_test():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        group_column = request.form.get('group_column')
        value_column = request.form.get('value_column')
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and group_column and value_column:
            try:
                df = pd.read_csv(file) if file.filename.endswith('.csv') else pd.read_excel(file)
                groups = [df[value_column][df[group_column] == g] for g in df[group_column].unique()]
                stat, p = stats.levene(*groups)
                result = {'stat': stat, 'p': p, 'is_homogeneous': p > 0.05}
                return render_template('homogeneity_test.html', result=result)
            except Exception as e:
                flash(f'Error processing file: {e}')
                return redirect(request.url)
    return render_template('homogeneity_test.html')


# ========================================================================
# --- FITUR GENERATOR KAJIAN TEORI YANG BARU (Tetap Utuh) ---
# ========================================================================
@app.route('/generator_kajian_teori')
def new_generator_kajian_teori():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('generator_kajian_teori.html')

# ... (Semua endpoint API untuk generator kajian teori tetap sama) ...
@app.route('/generator_kajian_teori/generate_outline', methods=['POST'])
def generate_outline_route():
    if 'user' not in session: return jsonify({"error": "Sesi tidak valid"}), 401
    try:
        data = request.get_json()
        generated_outline = generate_outline_with_ai(data)
        found_references = search_references_crossref(data['mainKeywords'])
        return jsonify({"outline": generated_outline, "references": found_references})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/generator_kajian_teori/generate_subchapter', methods=['POST'])
def generate_subchapter_route():
    if 'user' not in session: return jsonify({"error": "Sesi tidak valid"}), 401
    try:
        data = request.get_json()
        html_content = generate_subchapter_with_ai(data['research_inputs'], data['subchapter'], data.get('references', []))
        return jsonify({"content": html_content})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/generator_kajian_teori/compile_and_review', methods=['POST'])
def compile_and_review_route():
    if 'user' not in session: return jsonify({"error": "Sesi tidak valid"}), 401
    try:
        data = request.get_json()
        final_content, final_references = review_and_compile_with_ai(data['research_inputs'], data['chapters'], data['references'])
        return jsonify({"final_content": final_content, "final_references": final_references})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/generator_kajian_teori/export', methods=['POST'])
def export_document_route():
    if 'user' not in session: return jsonify({"error": "Sesi tidak valid"}), 401
    try:
        file_format = request.args.get('format', 'docx')
        content_html = request.form.get('content', '')
        references_html = request.form.get('references', '')
        if file_format == 'docx':
            file_bytes = export_to_docx(content_html, references_html)
            return Response(file_bytes, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document', headers={'Content-Disposition': 'attachment;filename=kajian_teori.docx'})
        elif file_format == 'pdf':
            file_bytes = export_to_pdf(content_html, references_html)
            return Response(file_bytes, mimetype='application/pdf', headers={'Content-Disposition': 'attachment;filename=kajian_teori.pdf'})
        return jsonify({"error": "Format tidak didukung."}), 400
    except Exception as e: return jsonify({"error": str(e)}), 500
