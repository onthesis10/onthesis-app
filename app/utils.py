import os
import json
import requests
import markdown
import google.generativeai as genai
from crossref.restful import Works
from docx import Document
from docx.shared import Inches
from weasyprint import HTML
from io import BytesIO

# Konfigurasi API Key dari .env
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

def search_references_crossref(keywords, limit=20):
    """
    Mencari referensi akademis menggunakan CrossRef API.
    """
    works = Works()
    query = " ".join(keywords.split(','))
    results = works.query(query).sample(limit)
    
    references = []
    for item in results:
        try:
            authors = ", ".join(author['given'] + " " + author['family'] for author in item.get('author', [])) if item.get('author') else "N/A"
            ref = {
                "id": item.get('DOI', f"ref_{len(references)}"),
                "title": item.get('title', ["No Title"])[0],
                "author": authors,
                "year": item.get('created', {}).get('date-parts', [[None]])[0][0],
                "abstract": item.get('abstract', 'Abstract not available.').replace('<jats:p>', '').replace('</jats:p>', ''),
                "doi": item.get('DOI')
            }
            references.append(ref)
        except Exception:
            continue # Lewati jika ada referensi yang formatnya aneh
    return references

def generate_outline_with_ai(inputs):
    """
    Membuat kerangka (outline) Bab 2 menggunakan Gemini AI.
    """
    prompt = f"""
    Anda adalah seorang asisten ahli penulisan skripsi. Buatkan kerangka (outline) yang terstruktur dan komprehensif untuk Bab 2: Kajian Pustaka, berdasarkan informasi berikut:

    Judul Penelitian: "{inputs['researchTitle']}"
    Kata Kunci: "{inputs['mainKeywords']}"
    Bahasa: {inputs['language']}

    Kerangka harus mencakup sub-bab utama seperti:
    1. Landasan Teori (jelaskan teori-teori utama yang relevan)
    2. Penelitian Terdahulu (review jurnal atau penelitian sebelumnya)
    3. Kerangka Pemikiran (jika relevan)
    4. Hipotesis Penelitian (jika ada)

    Untuk setiap sub-bab, berikan judul dan deskripsi singkat tentang apa yang harus dibahas di dalamnya.

    Format output Anda HARUS dalam bentuk JSON array seperti ini, dan tidak boleh ada teks lain di luar format JSON:
    [
        {{"title": "2.1 Judul Sub-bab", "description": "Deskripsi singkat isi sub-bab ini."}},
        {{"title": "2.2 Judul Sub-bab", "description": "Deskripsi singkat isi sub-bab ini."}}
    ]
    """
    
    response = model.generate_content(prompt)
    try:
        # Menghapus ```json dan ``` dari respons AI
        cleaned_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        outline = json.loads(cleaned_text)
        return outline
    except (json.JSONDecodeError, AttributeError) as e:
        print(f"Error decoding AI response for outline: {e}")
        print(f"Raw AI response: {response.text}")
        # Fallback jika JSON gagal di-parse
        return [{"title": "Error: Gagal Membuat Outline", "description": "AI tidak memberikan format yang benar. Coba lagi."}]


def generate_subchapter_with_ai(research_inputs, subchapter, references):
    """
    Menulis konten untuk satu sub-bab menggunakan Gemini AI, berdasarkan referensi.
    """
    # Ambil abstrak dari referensi untuk dijadikan konteks
    reference_abstracts = "\n\n".join([f"Judul: {ref['title']}\nPenulis: {ref['author']} ({ref['year']})\nAbstrak: {ref['abstract']}" for ref in references])

    prompt = f"""
    Anda adalah seorang penulis akademis yang sangat teliti. Tugas Anda adalah menulis konten untuk sub-bab berikut dalam sebuah skripsi.

    Informasi Penelitian:
    - Judul Skripsi: "{research_inputs['researchTitle']}"
    - Bahasa Penulisan: {research_inputs['language']}

    Sub-bab yang harus ditulis:
    - Judul Sub-bab: "{subchapter['title']}"
    - Deskripsi: "{subchapter['description']}"

    Gunakan ringkasan referensi berikut sebagai dasar utama tulisan Anda. Anda HARUS mengintegrasikan informasi dari abstrak ini ke dalam tulisan Anda dan melakukan sitasi dengan format (Nama Belakang Penulis, Tahun). Jangan mengarang informasi. Lakukan parafrase dengan baik untuk menghindari plagiarisme.

    Ringkasan Referensi:
    ---
    {reference_abstracts}
    ---

    Instruksi Penulisan:
    1. Tulis konten yang detail, koheren, dan mendalam untuk sub-bab ini.
    2. Panjang tulisan sekitar 500-700 kata.
    3. Gunakan gaya bahasa formal akademik.
    4. Setiap klaim atau informasi yang diambil dari referensi HARUS disertai sitasi. Contoh: (Smith, 2021).
    5. Output harus dalam format Markdown.

    Mulai tulisan Anda sekarang.
    """
    
    response = model.generate_content(prompt)
    html_content = markdown.markdown(response.text)
    return html_content

def review_and_compile_with_ai(research_inputs, chapters, references):
    """
    Melakukan review akhir, menambahkan transisi, dan memformat daftar pustaka.
    """
    full_content_md = ""
    for chapter in chapters:
        # Konversi HTML kembali ke Markdown sederhana untuk di-review AI
        # Ini adalah penyederhanaan; library yang lebih canggih mungkin diperlukan untuk konversi sempurna
        md_content = str(chapter['content']).replace('<h3>', '### ').replace('</h3>', '').replace('<p>', '').replace('</p>', '\n')
        full_content_md += f"## {chapter['title']}\n{md_content}\n\n"

    # 1. AI Review
    review_prompt = f"""
    Anda adalah seorang editor ahli. Berikut adalah draf lengkap dari Bab 2 sebuah skripsi.
    Tugas Anda:
    1. Baca keseluruhan teks untuk memahami alurnya.
    2. Periksa koherensi dan kesinambungan antar sub-bab.
    3. Tambahkan beberapa kalimat transisi yang mulus di awal atau akhir sub-bab jika diperlukan untuk membuat alurnya lebih baik.
    4. Jangan mengubah konten secara drastis, hanya perbaiki alur dan tambahkan transisi.
    5. Kembalikan teks lengkap yang sudah diperbaiki dalam format Markdown.

    Draf Teks:
    ---
    {full_content_md}
    ---
    """
    reviewed_response = model.generate_content(review_prompt)
    final_content_html = markdown.markdown(reviewed_response.text)

    # 2. Format Daftar Pustaka (APA Style sederhana)
    bibliography_html = "<h3>Daftar Pustaka</h3>"
    for ref in references:
        if ref['author'] and ref['year'] and ref['title']:
            bibliography_html += f"""
            <p style="padding-left: 20px; text-indent: -20px;">
                {ref['author']}. ({ref['year']}). <em>{ref['title']}</em>. 
                {f'doi:{ref["doi"]}' if ref.get("doi") else ''}
            </p>
            """
            
    return final_content_html, bibliography_html

def export_to_docx(html_content, references_html):
    """
    Mengekspor konten HTML ke file DOCX.
    """
    document = Document()
    document.add_heading('Bab 2: Kajian Pustaka', level=1)
    
    # Ini adalah cara sederhana, library seperti html2docx mungkin lebih baik
    # Untuk sekarang, kita akan tambahkan teks mentah
    # Implementasi yang lebih baik akan mem-parsing HTML
    document.add_paragraph(html_content) # Ini tidak akan merender HTML
    document.add_page_break()
    document.add_paragraph(references_html)

    file_stream = BytesIO()
    document.save(file_stream)
    file_stream.seek(0)
    return file_stream.getvalue()

def export_to_pdf(html_content, references_html):
    """
    Mengekspor konten HTML ke file PDF menggunakan WeasyPrint.
    """
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Kajian Teori</title></head>
    <body>
        <h1>Bab 2: Kajian Pustaka</h1>
        {html_content}
        <hr>
        {references_html}
    </body>
    </html>
    """
    file_stream = BytesIO()
    HTML(string=full_html).write_pdf(file_stream)
    file_stream.seek(0)
    return file_stream.getvalue()
