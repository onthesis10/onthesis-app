# ========================================================================
# File: app/routes.py
# Deskripsi: Versi lengkap dan final dengan semua fitur dan perbaikan bug.
# ========================================================================

# --- Impor Library ---
import os
import json
import re
import requests
import google.generativeai as genai
import time
import midtransclient
from datetime import date
from werkzeug.utils import secure_filename
import uuid

# --- Impor untuk Analisis Statistik ---
from scipy import stats
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns

# --- Impor dari __init__.py ---
from app import app, db, login_manager

# Impor untuk framework Flask dan ekstensi
from flask import render_template, jsonify, request, redirect, url_for, flash
from flask_cors import CORS
from flask_login import (
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from firebase_admin import auth, firestore

# Impor untuk analisis dokumen
import PyPDF2
import docx

# --- Konfigurasi Tambahan ---
try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
except Exception as e:
    print(f"Peringatan: Gagal mengkonfigurasi Gemini API. Error: {e}")

try:
    server_key = os.getenv('MIDTRANS_SERVER_KEY')
    client_key = os.getenv('MIDTRANS_CLIENT_KEY')
    midtrans_snap = midtransclient.Snap(
        is_production=False,
        server_key=server_key,
        client_key=client_key
    )
except Exception as e:
    print(f"Peringatan: Gagal mengkonfigurasi Midtrans. Error: {e}")
    midtrans_snap = None

# Konfigurasi untuk output statistik deskriptif
OUTPUT_DIR = os.path.join(app.static_folder, 'outputs')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Konfigurasi gaya plot Matplotlib/Seaborn
sns.set_style('whitegrid')
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans']
plt.rcParams['axes.titleweight'] = 'bold'
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['figure.figsize'] = (8,5)


# =========================================================================
# FUNGSI HELPER
# =========================================================================
def read_pdf(file_stream):
    """Membaca teks dari file PDF."""
    reader = PyPDF2.PdfReader(file_stream)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

def read_docx(file_stream):
    """Membaca teks dari file DOCX."""
    doc = docx.Document(file_stream)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text

def descriptive_stats(series: pd.Series):
    s = series.dropna().astype(float)
    n = int(s.count())
    if n == 0: return { 'n': 0 }
    
    mean = float(s.mean())
    median = float(s.median())
    mode_list = s.mode().tolist()
    var = float(s.var(ddof=1)) if n > 1 else 0
    sd = float(s.std(ddof=1)) if n > 1 else 0
    minimum = float(s.min())
    maximum = float(s.max())
    rng = maximum - minimum
    q1 = float(s.quantile(0.25))
    q3 = float(s.quantile(0.75))
    iqr = q3 - q1
    skew = float(s.skew()) if n > 2 else 0
    kurt = float(s.kurtosis()) if n > 3 else 0

    shapiro_w, shapiro_p = (None, None)
    if 3 <= n <= 5000:
        try:
            shapiro_w, shapiro_p = stats.shapiro(s)
        except Exception:
            pass

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    outliers = s[(s < lower) | (s > upper)].tolist()

    return {
        'n': n, 'mean': mean, 'median': median, 'mode': mode_list, 'variance': var,
        'std': sd, 'min': minimum, 'max': maximum, 'range': rng, 'q1': q1,
        'q3': q3, 'iqr': iqr, 'skewness': skew, 'kurtosis': kurt,
        'shapiro_w': shapiro_w, 'shapiro_p': shapiro_p, 'outliers': outliers
    }

def save_figure(fig, prefix='plot'):
    fname = f"{prefix}_{uuid.uuid4().hex[:8]}.png"
    path = os.path.join(OUTPUT_DIR, fname)
    fig.savefig(path, bbox_inches='tight', dpi=150)
    plt.close(fig)
    return url_for('static', filename=f'outputs/{fname}')


# =========================================================================
# MODEL PENGGUNA & LOADER
# =========================================================================
class User(UserMixin):
    def __init__(self, id, displayName, password_hash=None, email=None, is_pro=False, picture=None):
        self.id = id
        self.displayName = displayName
        self.username = displayName
        self.email = email
        self.is_pro = is_pro
        self.picture = picture
        self.password_hash = password_hash

    def check_password(self, password):
        if self.password_hash is None: return False
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    if not db: return None
    try:
        user_doc = db.collection('users').document(user_id).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            return User(id=user_id, displayName=user_data.get('displayName'), email=user_data.get('email'), password_hash=user_data.get('password_hash'), is_pro=user_data.get('isPro', False), picture=user_data.get('picture'))
        return None
    except Exception as e:
        print(f"Error saat memuat pengguna dari Firestore: {e}")
        return None

# =========================================================================
# FUNGSI HELPER UNTUK PEMBATASAN FITUR
# =========================================================================
def check_and_update_usage(user_id, feature_name):
    FEATURE_LIMITS = {
        'paraphrase': 5, 'chat': 10, 'search': 5, 'citation': 15
    }
    limit = FEATURE_LIMITS.get(feature_name)
    if limit is None: return True, "OK"
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()
    if not user_doc.exists: return False, "Pengguna tidak ditemukan."
    today_str = date.today().isoformat()
    usage_data = user_doc.to_dict().get('usage_limits', {})
    last_reset = usage_data.get('last_reset_date')
    if last_reset != today_str:
        citation_total = usage_data.get('citation_count', 0)
        usage_data = {
            'paraphrase_count': 0, 'chat_count': 0, 'search_count': 0,
            'writing_assistant_count': 0, 'data_analysis_count': 0, 'export_doc_count': 0,
            'last_reset_date': today_str, 'citation_count': citation_total
        }
        user_ref.set({'usage_limits': usage_data}, merge=True)
    count_key = f"{feature_name}_count"
    current_count = usage_data.get(count_key, 0)
    if current_count >= limit:
        if feature_name == 'citation':
             return False, f"Anda telah mencapai batas total {limit} referensi untuk akun gratis."
        return False, f"Anda telah mencapai batas penggunaan harian ({limit}x) untuk fitur ini. Silakan upgrade ke PRO."
    user_ref.update({f'usage_limits.{count_key}': firestore.Increment(1)})
    return True, "OK"

def check_and_update_pro_trial(user_id, feature_name):
    PRO_TRIAL_LIMITS = {'writing_assistant': 3, 'data_analysis': 3, 'export_doc': 1}
    limit = PRO_TRIAL_LIMITS.get(feature_name)
    if limit is None: return True, "OK"
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()
    if not user_doc.exists: return False, "Pengguna tidak ditemukan."
    usage_data = user_doc.to_dict().get('usage_limits', {})
    count_key = f"{feature_name}_count"
    current_count = usage_data.get(count_key, 0)
    if current_count >= limit:
        return False, f"Anda telah menggunakan semua percobaan gratis ({limit}x) untuk fitur PRO ini. Silakan upgrade."
    user_ref.update({f'usage_limits.{count_key}': firestore.Increment(1)})
    return True, "OK"

# =========================================================================
# RUTE-RUTE HALAMAN
# =========================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username_input = request.form.get('username')
        password = request.form.get('password')
        users_ref = db.collection('users').where('displayName', '==', username_input).limit(1).stream()
        user_doc = next(users_ref, None)
        if user_doc:
            user = load_user(user_doc.id)
            if user and user.check_password(password):
                login_user(user)
                return redirect(request.args.get('next') or url_for('dashboard'))
        flash('Username atau password salah.', 'danger')
    firebase_config = { "apiKey": os.getenv("FIREBASE_API_KEY"), "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"), "projectId": os.getenv("FIREBASE_PROJECT_ID"), "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"), "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"), "appId": os.getenv("FIREBASE_APP_ID"), "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID") }
    firebase_config_filtered = {k: v for k, v in firebase_config.items() if v is not None}
    return render_template('login.html', firebase_config=firebase_config_filtered)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah berhasil logout.', 'success')
    return redirect(url_for('login'))

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard(): return render_template('dashboard.html')

@app.route('/projects')
@login_required
def projects(): return render_template('projects.html')

@app.route('/search-references')
@login_required
def search_references(): return render_template('search_references.html')

@app.route('/citation-management')
@login_required
def citation_management(): return render_template('citation_management.html')

@app.route('/paraphrase-ai')
@login_required
def paraphrase_ai(): return render_template('paraphrase_ai.html')

@app.route('/chat-ai')
@login_required
def chat_ai(): return render_template('chat_ai.html')

@app.route('/writing-assistant')
@login_required
def writing_assistant(): return render_template('writing_assistant.html')

@app.route('/data-analysis')
@login_required
def data_analysis(): return render_template('data_analysis.html')

@app.route('/normality-test')
@login_required
def normality_test(): return render_template('normality_test.html')

@app.route('/homogeneity_test')
@login_required
def homogeneity_test(): return render_template('homogeneity_test.html')

@app.route('/descriptive_statistics')
@login_required
def descriptive_statistics():
    return render_template('descriptive_statistics.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def user_profile():
    if request.method == 'POST':
        try:
            new_name = request.form.get('name')
            if not new_name or len(new_name) < 3:
                flash('Nama tampilan harus memiliki setidaknya 3 karakter.', 'danger')
                return redirect(url_for('user_profile'))
            user_id = current_user.id
            db.collection('users').document(user_id).update({'displayName': new_name})
            auth.update_user(user_id, display_name=new_name)
            flash('Profil berhasil diperbarui!', 'success')
        except Exception as e:
            flash(f'Terjadi kesalahan saat memperbarui profil: {e}', 'danger')
        return redirect(url_for('user_profile'))
    client_key = os.getenv('MIDTRANS_CLIENT_KEY')
    return render_template('user-profile.html', midtrans_client_key=client_key)

# =========================================================================
# RUTE API
# =========================================================================

@app.route('/api/check-pro-trial-usage', methods=['POST'])
@login_required
def check_pro_trial_usage():
    if current_user.is_pro:
        return jsonify({'allowed': True})
    
    try:
        data = request.get_json()
        feature_name = data.get('feature')
        if not feature_name:
            return jsonify({'error': 'Nama fitur diperlukan.'}), 400
        
        is_allowed, message = check_and_update_pro_trial(current_user.id, feature_name)
        
        if not is_allowed:
            return jsonify({'allowed': False, 'message': message}), 429
        
        return jsonify({'allowed': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/writing-assistant', methods=['POST'])
@login_required
def api_writing_assistant():
    if not current_user.is_pro:
        is_allowed, message = check_and_update_pro_trial(current_user.id, 'writing_assistant')
        if not is_allowed: return jsonify({'error': message}), 429
    try:
        data = request.get_json()
        task = data.get('task')
        context = data.get('context')
        if not task or not context: return jsonify({'error': 'Task dan context diperlukan.'}), 400
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = ""
        if task == 'generate_outline':
            prompt = f"Buatkan kerangka skripsi yang terstruktur dan logis berdasarkan judul berikut: \"{context}\""
        elif task == 'generate_abstract':
            prompt = f"Buatkan draf abstrak yang ringkas dan padat (sekitar 200-250 kata) berdasarkan isi skripsi berikut:\n\n{context}"
        else:
            return jsonify({'error': 'Task tidak valid.'}), 400
        response = model.generate_content(prompt)
        return jsonify({'generated_text': response.text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/interpret-analysis', methods=['POST'])
@login_required
def interpret_analysis():
    if not current_user.is_pro:
        is_allowed, message = check_and_update_pro_trial(current_user.id, 'data_analysis')
        if not is_allowed: return jsonify({'error': message}), 429
    try:
        stats_text = request.get_json().get('stats')
        if not stats_text: return jsonify({'error': 'Data statistik tidak boleh kosong.'}), 400
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Anda adalah seorang analis data. Berdasarkan data statistik berikut:\n---\n{stats_text}\n---\nBerikan interpretasi singkat yang mudah dipahami dalam format markdown."
        response = model.generate_content(prompt)
        return jsonify({'interpretation': response.text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search-references', methods=['POST'])
@login_required
def api_search_references():
    is_allowed, message = check_and_update_usage(current_user.id, 'search')
    if not is_allowed: return jsonify({'error': message}), 429
    data = request.get_json()
    source = data.get('source')
    query = data.get('query')
    year = data.get('year')
    try:
        if source == 'core':
            core_api_key = os.getenv('CORE_API_KEY')
            if not core_api_key: return jsonify({'error': 'Kunci API CORE tidak dikonfigurasi.'}), 500
            api_url = 'https://api.core.ac.uk/v3/search/works'
            q = f"(title:({query}) OR authors:({query}))"
            if year: q += f" AND yearPublished:{year}"
            params = {'q': q, 'limit': 20}
            headers = {'Authorization': f'Bearer {core_api_key}'}
            response = requests.get(api_url, params=params, headers=headers, timeout=20)
            response.raise_for_status()
            return jsonify(response.json())
        elif source == 'crossref':
            base_url = 'https://api.crossref.org/works'
            params = {'query.bibliographic': query, 'rows': 20}
            if year: params['filter'] = f'from-pub-date:{year}-01-01,until-pub-date:{year}-12-31'
            headers = {'User-Agent': 'OnThesisApp/1.0 (mailto:contact@onthesis.app)'}
            response = requests.get(base_url, params=params, headers=headers, timeout=20)
            response.raise_for_status()
            api_data = response.json()
            results = api_data.get('message', {}).get('items', [])
            return jsonify({'results': results})
        else:
            return jsonify({'error': 'Sumber tidak valid.'}), 400
    except Exception as e:
        return jsonify({'error': f'Terjadi kesalahan saat mencari referensi: {e}'}), 500

@app.route('/paraphrase', methods=['POST'])
@login_required
def paraphrase_text():
    is_allowed, message = check_and_update_usage(current_user.id, 'paraphrase')
    if not is_allowed: return jsonify({'error': message}), 429
    try:
        text = request.get_json().get('text')
        if not text: return jsonify({'error': 'Teks tidak boleh kosong.'}), 400
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Parafrasekan teks ini ke gaya akademis untuk skripsi, pertahankan maknanya:\n\n{text}"
        response = model.generate_content(prompt)
        return jsonify({'paraphrased_text': response.text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
@login_required
def chat_with_ai():
    is_allowed, message = check_and_update_usage(current_user.id, 'chat')
    if not is_allowed: return jsonify({'error': message}), 429
    try:
        message = request.get_json().get('message')
        if not message: return jsonify({'error': 'Pesan tidak boleh kosong.'}), 400
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Anda adalah asisten AI bernama OnThesis. Jawab pertanyaan mahasiswa ini seputar skripsi dengan ramah dan membantu: {message}"
        response = model.generate_content(prompt)
        return jsonify({'reply': response.text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze-document', methods=['POST'])
@login_required
def analyze_document():
    if 'document' not in request.files:
        return jsonify({'error': 'Tidak ada file yang diunggah.'}), 400
    file = request.files['document']
    if file.filename == '':
        return jsonify({'error': 'Nama file kosong.'}), 400
    try:
        filename = secure_filename(file.filename).lower()
        content = ""
        if filename.endswith('.pdf'):
            content = read_pdf(file.stream)
        elif filename.endswith('.docx'):
            content = read_docx(file.stream)
        else:
            return jsonify({'error': 'Format file tidak didukung. Harap unggah PDF atau DOCX.'}), 400
        if not content.strip():
            return jsonify({'error': 'Tidak ada teks yang dapat diekstrak dari file ini.'}), 400
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Dari teks dokumen akademis berikut, identifikasi informasi sitasi untuk dokumen itu sendiri.
        Ekstrak penulis utama, judul utama, tahun publikasi, dan nama jurnal atau konferensi tempat dokumen itu diterbitkan.
        Berikan hasilnya sebagai array JSON yang hanya berisi SATU objek dengan kunci: "title", "author", "year", dan "journal".

        Teks Dokumen (ambil dari bagian awal untuk efisiensi):
        ---
        {content[:8000]} 
        ---
        """
        response = model.generate_content(prompt)
        clean_json_string = re.sub(r'```json\s*|\s*```', '', response.text.strip(), flags=re.DOTALL)
        if not clean_json_string.strip().startswith('['):
            clean_json_string = f"[{clean_json_string}]"
        references = json.loads(clean_json_string)
        return jsonify({'references': references})
    except json.JSONDecodeError:
        return jsonify({'error': 'AI tidak dapat memformat informasi sitasi dengan benar. Coba lagi.'}), 500
    except Exception as e:
        print(f"Error saat menganalisis dokumen: {e}")
        return jsonify({'error': f'Terjadi kesalahan internal: {str(e)}'}), 500

@app.route('/api/normality', methods=['POST'])
@login_required
def api_normality():
    try:
        data = request.get_json()
        values = data.get('values')
        if not values or not isinstance(values, list):
            return jsonify({'error': 'Data angka diperlukan dalam array'}), 400
        
        s = pd.Series(values, dtype=float).dropna()
        
        if len(s) < 3:
            return jsonify({'error': 'Minimal 3 data untuk uji normalitas'}), 400
        
        n = len(s)
        mean = s.mean()
        sd = s.std(ddof=1)

        shapiro_stat, shapiro_p = stats.shapiro(s)
        ks_stat, ks_p = stats.kstest((s - mean) / sd, 'norm')

        shapiro_p_rounded = round(shapiro_p, 3)
        ks_p_rounded = round(ks_p, 3)

        if shapiro_p > 0.05:
            conclusion = "berdistribusi normal"
        else:
            conclusion = "tidak berdistribusi normal"
        
        summary = f"Hasil uji Shapiro-Wilk menunjukkan nilai signifikansi p = {shapiro_p_rounded}. Karena nilai p > 0.05, dapat disimpulkan bahwa data {conclusion}."

        df_table = pd.DataFrame({
            "test": ["Shapiro-Wilk", "Kolmogorov-Smirnov"],
            "statistic": [shapiro_stat, ks_stat],
            "df": [n, n],
            "p": [shapiro_p_rounded, ks_p_rounded]
        })
        table_json = df_table.to_dict(orient='records')

        return jsonify({
            "summary": summary, 
            "mean": round(mean, 3), 
            "std_dev": round(sd, 3), 
            "n": n, 
            "table": table_json
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/levene', methods=['POST'])
@login_required
def api_levene():
    try:
        data = request.get_json()
        groups = data.get('groups')
        if not groups or not isinstance(groups, list) or len(groups) < 2:
            return jsonify({'error': 'Minimal 2 grup data diperlukan'}), 400

        cleaned_groups = [np.array(g, dtype=float)[~np.isnan(g)] for g in groups]
        group_sizes = [len(g) for g in cleaned_groups]
        if any(size < 2 for size in group_sizes):
            return jsonify({'error': 'Setiap grup minimal punya 2 data'}), 400

        stat, p_value = stats.levene(*cleaned_groups)
        
        p_string = f"{p_value:.3f}"
        comparison = "> 0.05" if p_value > 0.05 else "<= 0.05"
        conclusion = "homogen" if p_value > 0.05 else "tidak homogen"
        summary = f"Hasil Levene’s Test menunjukkan nilai Sig. = {p_string} ({comparison}), sehingga dapat disimpulkan varians data antar kelompok adalah {conclusion}."

        df_table = pd.DataFrame({
            "test": ["Levene’s Test"],
            "statistic": [stat],
            "df1": [len(cleaned_groups) - 1],
            "df2": [sum(group_sizes) - len(cleaned_groups)],
            "p": [p_value]
        })
        df_table['statistic'] = df_table['statistic'].round(4)
        df_table['p'] = df_table['p'].round(4)
        table_json = df_table.to_dict(orient='records')

        return jsonify({
            "summary": summary,
            "n_per_group": group_sizes,
            "table": table_json
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/bartlett', methods=['POST'])
@login_required
def api_bartlett():
    try:
        data = request.get_json()
        groups = data.get('groups')
        if not groups or not isinstance(groups, list) or len(groups) < 2:
            return jsonify({'error': 'Minimal 2 grup data diperlukan'}), 400

        cleaned_groups = [np.array(g, dtype=float)[~np.isnan(g)] for g in groups]
        group_sizes = [len(g) for g in cleaned_groups]
        if any(size < 2 for size in group_sizes):
            return jsonify({'error': 'Setiap grup minimal punya 2 data'}), 400

        stat, p_value = stats.bartlett(*cleaned_groups)

        p_string = f"{p_value:.3f}"
        comparison = "> 0.05" if p_value > 0.05 else "<= 0.05"
        conclusion = "homogen" if p_value > 0.05 else "tidak homogen"
        summary = f"Hasil Bartlett's Test menunjukkan nilai Sig. = {p_string} ({comparison}), sehingga dapat disimpulkan varians data antar kelompok adalah {conclusion}."

        df_table = pd.DataFrame({
            "test": ["Bartlett’s Test"],
            "statistic": [stat],
            "df1": [len(cleaned_groups) - 1],
            "df2": [None],
            "p": [p_value]
        })
        df_table['statistic'] = df_table['statistic'].round(4)
        df_table['p'] = df_table['p'].round(4)
        table_json = df_table.to_dict(orient='records')

        return jsonify({
            "summary": summary,
            "n_per_group": group_sizes,
            "table": table_json
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
@app.route('/api/descriptive_analysis', methods=['POST'])
@login_required
def descriptive_analysis():
    if not current_user.is_pro:
        is_allowed, message = check_and_update_pro_trial(current_user.id, 'data_analysis')
        if not is_allowed:
            return jsonify({'error': message}), 429
    try:
        uploaded = request.files.get('file')
        raw_text = request.form.get('raw_csv')
        df = None

        if uploaded and uploaded.filename != '':
            if uploaded.filename.lower().endswith('.csv'):
                df = pd.read_csv(uploaded)
            else:
                return jsonify({'error': 'Format file tidak valid. Harap unggah file CSV.'}), 400
        elif raw_text and raw_text.strip() != '':
            from io import StringIO
            df = pd.read_csv(StringIO(raw_text))
        else:
            return jsonify({'error': 'Tidak ada data yang diberikan.'}), 400

        numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
        if not numeric_cols:
            return jsonify({'error': 'Tidak ditemukan kolom numerik pada data.'}), 400

        results = {}
        plots = {}

        for col in numeric_cols:
            stats_d = descriptive_stats(df[col])
            results[col] = stats_d
            s = df[col].dropna().astype(float)

            # Histogram
            fig1, ax1 = plt.subplots()
            sns.histplot(s, bins='auto', kde=True, ax=ax1, edgecolor='black')
            ax1.set_title(f'Histogram - {col}')
            plots[f'{col}_histogram'] = save_figure(fig1, prefix=f'hist_{col}')

            # Boxplot
            fig2, ax2 = plt.subplots(figsize=(8, 2))
            sns.boxplot(x=s, ax=ax2)
            ax2.set_title(f'Boxplot - {col}')
            plots[f'{col}_boxplot'] = save_figure(fig2, prefix=f'box_{col}')

        return jsonify({
            'results': results,
            'plots': plots,
            'columns': numeric_cols
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/get-usage-status')
@login_required
def get_usage_status():
    if current_user.is_pro:
        return jsonify({'status': 'pro', 'message': 'Akses Penuh Tanpa Batas'})
    LIMITS = {'paraphrase': 5, 'chat': 10, 'search': 5, 'citation': 15, 'writing_assistant': 3, 'data_analysis': 3, 'export_doc': 1}
    user_ref = db.collection('users').document(current_user.id)
    user_doc = user_ref.get()
    if not user_doc.exists: return jsonify({'error': 'User not found'}), 404
    usage_data = user_doc.to_dict().get('usage_limits', {})
    today_str = date.today().isoformat()
    if usage_data.get('last_reset_date') != today_str:
        usage_data['paraphrase_count'] = 0
        usage_data['chat_count'] = 0
        usage_data['search_count'] = 0
    return jsonify({
        'status': 'free',
        'paraphrase_remaining': LIMITS['paraphrase'] - usage_data.get('paraphrase_count', 0),
        'chat_remaining': LIMITS['chat'] - usage_data.get('chat_count', 0),
        'search_remaining': LIMITS['search'] - usage_data.get('search_count', 0),
        'citation_remaining': LIMITS['citation'] - usage_data.get('citation_count', 0),
        'writing_assistant_remaining': LIMITS['writing_assistant'] - usage_data.get('writing_assistant_count', 0),
        'data_analysis_remaining': LIMITS['data_analysis'] - usage_data.get('data_analysis_count', 0),
        'export_doc_remaining': LIMITS['export_doc'] - usage_data.get('export_doc_count', 0),
        'limits': LIMITS
    })

@app.route('/api/submit-feedback', methods=['POST'])
@login_required
def submit_feedback():
    try:
        data = request.get_json()
        message = data.get('message')
        category = data.get('category')
        page_url = data.get('pageUrl')
        if not message or not category:
            return jsonify({'status': 'error', 'message': 'Pesan dan kategori tidak boleh kosong.'}), 400
        feedback_doc = {
            'userId': current_user.id, 'userEmail': current_user.email,
            'message': message, 'category': category, 'pageUrl': page_url,
            'timestamp': firestore.SERVER_TIMESTAMP, 'status': 'new'
        }
        db.collection('feedback').add(feedback_doc)
        return jsonify({'status': 'success', 'message': 'Terima kasih atas masukan Anda!'})
    except Exception as e:
        print(f"Error saat menyimpan feedback: {e}")
        return jsonify({'status': 'error', 'message': 'Terjadi kesalahan di server.'}), 500

@app.route('/api/verify-google-token', methods=['POST'])
def verify_google_token():
    try:
        token = request.json['token']
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
        user_ref = db.collection('users').document(uid)
        user_doc = user_ref.get()
        if user_doc.exists:
            user = load_user(uid)
        else:
            user_data = {
                'displayName': decoded_token.get('name', decoded_token.get('email')),
                'email': decoded_token.get('email'),
                'picture': decoded_token.get('picture'),
                'isPro': False, 'password_hash': None
            }
            user_ref.set(user_data)
            user = load_user(uid)
        login_user(user)
        return jsonify({'status': 'success', 'redirect_url': url_for('dashboard')})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Verifikasi token gagal: {e}'}), 401

@app.route('/api/create-transaction', methods=['POST'])
@login_required
def create_transaction():
    try:
        if not midtrans_snap:
            return jsonify({'status': 'error', 'message': 'Layanan pembayaran tidak terkonfigurasi.'}), 503
        order_id = f"ONTESIS-PRO-{current_user.id}-{int(time.time())}"
        transaction_details = {"order_id": order_id, "gross_amount": 50000}
        customer_details = {"first_name": current_user.displayName, "email": current_user.email}
        transaction = midtrans_snap.create_transaction({
            "transaction_details": transaction_details,
            "customer_details": customer_details
        })
        return jsonify({'status': 'success', 'token': transaction['token']})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Gagal membuat transaksi: {e}'}), 500

@app.route('/api/payment-notification', methods=['POST'])
def payment_notification():
    try:
        notification_json = request.get_json()
        order_id = notification_json['order_id']
        transaction_status = notification_json['transaction_status']
        fraud_status = notification_json.get('fraud_status')
        if transaction_status == 'settlement' and fraud_status == 'accept':
            parts = order_id.split('-')
            if len(parts) >= 3 and parts[0] == 'ONTESIS' and parts[1] == 'PRO':
                user_id = parts[2]
                db.collection('users').document(user_id).update({'isPro': True})
                print(f"Sukses: Pengguna {user_id} telah di-upgrade ke PRO.")
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        print(f"Error saat menangani notifikasi pembayaran: {e}")
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500
