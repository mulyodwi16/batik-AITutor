from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import json
import os
import numpy as np
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Load data
def load_chunks():
    chunks_path = 'artifacts/chunks.json'
    if os.path.exists(chunks_path):
        with open(chunks_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def load_embeddings():
    emb_path = 'artifacts/embeddings.npy'
    if os.path.exists(emb_path):
        return np.load(emb_path)
    return None

def load_faiss_index():
    index_path = 'artifacts/faiss.index'
    if os.path.exists(index_path):
        import faiss
        return faiss.read_index(index_path)
    return None

chunks = load_chunks()
embeddings = load_embeddings()
faiss_index = load_faiss_index()

# Sample batik knowledge base
batik_knowledge = {
    'batik': 'Batik adalah teknik pewarnaan kain menggunakan lilin (wax resist dyeing) yang sangat terkenal dari Indonesia.',
    'sejarah': 'Batik telah menjadi bagian dari budaya Indonesia selama berabad-abad, terutama berkembang di Jawa.',
    'motif': 'Motif batik Indonesia sangat beragam, termasuk parang, kawung, ceplok, dan banyak lagi yang masing-masing memiliki makna khusus.',
    'warisan': 'UNESCO mengakui batik Indonesia sebagai Masterpiece of Oral and Intangible Heritage of Humanity sejak tahun 2009.',
    'proses': 'Proses pembuatan batik meliputi persiapan kain, pendesainan, pembatikan (aplikasi lilin), pencelupan, dan pembilasan.',
    'warna': 'Warna-warna tradisional batik biasanya menggunakan bahan alami seperti indigofera (biru) dan soga (coklat).',
    'regional': 'Setiap daerah di Indonesia memiliki ciri khas batik yang unik seperti batik Yogyakarta, Semarang, dan Cirebon.'
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '').lower().strip()
        
        if not user_message:
            return jsonify({'reply': 'Silakan tanyakan sesuatu tentang Batik Indonesia!', 'timestamp': datetime.now().isoformat()})
        
        # Simple keyword matching
        reply = "Maaf, informasi tentang itu belum tersedia. Coba tanya tentang: sejarah, motif, proses, warna, atau warisan budaya Batik Indonesia."
        
        for key, value in batik_knowledge.items():
            if key in user_message:
                reply = value
                break
        
        # Try matching with chunks
        if reply == batik_knowledge['proses']:  # If still default
            for chunk in chunks:
                if isinstance(chunk, dict):
                    content = chunk.get('content', '').lower()
                else:
                    content = str(chunk).lower()
                
                if any(word in user_message for word in ['batik', 'indonesia', 'budaya', 'sejarah']):
                    chunk_text = chunk.get('content', '') if isinstance(chunk, dict) else str(chunk)
                    if len(chunk_text) > 20:
                        reply = chunk_text[:250] + "..."
                    break
        
        return jsonify({
            'reply': reply,
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({'reply': f'Error: {str(e)}', 'timestamp': datetime.now().isoformat()}), 500

@app.route('/api/suggestions', methods=['GET'])
def suggestions():
    return jsonify({
        'suggestions': [
            'Apa itu Batik?',
            'Sejarah Batik Indonesia',
            'Motif-motif Batik',
            'Proses pembuatan Batik',
            'Warisan Batik UNESCO'
        ]
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
