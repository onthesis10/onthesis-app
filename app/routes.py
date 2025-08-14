import os
from flask import (Flask, render_template, request, redirect, url_for, 
                   flash, session, jsonify, Response)
from dotenv import load_dotenv
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, auth, firestore
import markdown
import json
import pandas as pd
import numpy as np
from scipy import stats
import statsmodels.api as sm
from io import BytesIO
import matplotlib.pyplot as plt
import base64

# Impor fungsi-fungsi dari utils.py
from app.utils import (
    search_references_crossref,
    generate_outline_with_ai,
    generate_subchapter_with_ai,
    review_and_compile_with_ai,
    export_to_docx,
    export_to_pdf
)

# --- Inisialisasi Aplikasi Flask dan Firebase ---
load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default_secret_key")

# Inisialisasi Firebase
try:
    cred_path = 'ServiceAccountKey.json'
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase berhasil diinisialisasi.")
    else:
        print("Peringatan: File ServiceAccountKey.json tidak ditemukan.")
        db = None
except Exception as e:
    print(f"Error initializing Firebase: {e}")
    db = None

# Inisialisasi Gemini API
try:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if gemini_api_key:
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-pro')
        print("Gemini API berhasil diinisialisasi.")
    else:
        print("Peringatan: GEMINI_API_KEY tidak ditemukan di .env")
        model = None
except Exception as e:
    print(f"Error initializing Gemini API: {e}")
    model = None


# --- Routes Utama dan Autentikasi ---
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        id_token = request.form.get('id_token')
        try:
            decoded_token = auth.verify_id_token(id_token)
            session['user'] = decoded_token
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f"Login Gagal: {e}")
            return redirect(url_for('login'))
    return render_template('login.html')

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

# --- Routes Fitur-Fitur Statis Lainnya ---
@app.route('/projects')
def projects():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('projects.html')

@app.route('/writing_assistant')
def writing_assistant():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('writing_assistant.html')

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

# --- Routes Fitur Generator (Lama & Lengkap) ---
@app.route('/generator_latar_belakang', methods=['GET', 'POST'])
def generator_latar_belakang():
    if 'user' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        # ... Logika lengkap untuk POST request ...
        pass
    return render_template('generator_latar_belakang.html')

@app.route('/generator_rumusan_masalah', methods=['GET', 'POST'])
def generator_rumusan_masalah():
    if 'user' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        # ... Logika lengkap untuk POST request ...
        pass
    return render_template('generator_rumusan_masalah.html')

# --- Routes Analisis Data (Lama & Lengkap) ---
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


# --- FITUR GENERATOR KAJIAN TEORI YANG BARU ---

@app.route('/generator_kajian_teori')
def new_generator_kajian_teori():
    """Menampilkan halaman utama Generator Kajian Teori yang baru."""
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('generator_kajian_teori.html')

@app.route('/generator_kajian_teori/generate_outline', methods=['POST'])
def generate_outline_route():
    """API Endpoint untuk membuat kerangka (outline) dan mencari referensi."""
    if 'user' not in session:
        return jsonify({"error": "Sesi tidak valid, silakan login kembali."}), 401
    
    try:
        data = request.get_json()
        if not data or 'mainKeywords' not in data:
            return jsonify({"error": "Kata kunci utama diperlukan."}), 400

        generated_outline = generate_outline_with_ai(data)
        found_references = search_references_crossref(data['mainKeywords'])

        return jsonify({
            "outline": generated_outline,
            "references": found_references
        })

    except Exception as e:
        print(f"Error in generate_outline_route: {e}")
        return jsonify({"error": f"Terjadi kesalahan: {str(e)}"}), 500

@app.route('/generator_kajian_teori/generate_subchapter', methods=['POST'])
def generate_subchapter_route():
    """API Endpoint untuk membuat konten per sub-bab."""
    if 'user' not in session:
        return jsonify({"error": "Sesi tidak valid, silakan login kembali."}), 401

    try:
        data = request.get_json()
        if not data or 'subchapter' not in data:
            return jsonify({"error": "Data sub-bab tidak ditemukan."}), 400

        html_content = generate_subchapter_with_ai(
            data['research_inputs'], 
            data['subchapter'], 
            data.get('references', [])
        )
        
        return jsonify({"content": html_content})

    except Exception as e:
        print(f"Error in generate_subchapter_route: {e}")
        return jsonify({"error": f"Terjadi kesalahan: {str(e)}"}), 500

@app.route('/generator_kajian_teori/compile_and_review', methods=['POST'])
def compile_and_review_route():
    """API Endpoint untuk menggabungkan, mereview, dan membuat daftar pustaka."""
    if 'user' not in session:
        return jsonify({"error": "Sesi tidak valid, silakan login kembali."}), 401

    try:
        data = request.get_json()
        if not data or 'chapters' not in data or 'references' not in data:
            return jsonify({"error": "Data tidak lengkap untuk proses review."}), 400

        final_content, final_references = review_and_compile_with_ai(
            data['research_inputs'],
            data['chapters'],
            data['references']
        )
        
        return jsonify({
            "final_content": final_content,
            "final_references": final_references
        })

    except Exception as e:
        print(f"Error in compile_and_review_route: {e}")
        return jsonify({"error": f"Terjadi kesalahan: {str(e)}"}), 500

@app.route('/generator_kajian_teori/export', methods=['POST'])
def export_document_route():
    """API Endpoint untuk mengekspor dokumen final."""
    if 'user' not in session:
        return jsonify({"error": "Sesi tidak valid, silakan login kembali."}), 401

    try:
        file_format = request.args.get('format', 'docx')
        content_html = request.form.get('content', '')
        references_html = request.form.get('references', '')
        
        if file_format == 'docx':
            file_bytes = export_to_docx(content_html, references_html)
            return Response(
                file_bytes, 
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                headers={'Content-Disposition': 'attachment;filename=kajian_teori.docx'}
            )
        elif file_format == 'pdf':
            file_bytes = export_to_pdf(content_html, references_html)
            return Response(
                file_bytes,
                mimetype='application/pdf',
                headers={'Content-Disposition': 'attachment;filename=kajian_teori.pdf'}
            )
        
        return jsonify({"error": "Format tidak didukung."}), 400

    except Exception as e:
        print(f"Error in export_document_route: {e}")
        return jsonify({"error": f"Terjadi kesalahan: {str(e)}"}), 500

