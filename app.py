from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import json
import os
import numpy as np
from datetime import datetime
import torch
import logging

app = Flask(__name__)
CORS(app)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# LOAD ARTIFACTS & MODELS (RAG + LLM SETUP)
# ============================================================

def load_chunks():
    chunks_path = 'artifacts/chunks.json'
    if os.path.exists(chunks_path):
        with open(chunks_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Handle both {"chunks": [...]} and [...]
            if isinstance(data, dict):
                return data.get('chunks', data)
            return data
    return []

def load_artifacts():
    """Load FAISS index, chunks, and embedder"""
    try:
        import faiss
        from sentence_transformers import SentenceTransformer
        
        chunks = load_chunks()
        index = None
        
        index_path = 'artifacts/faiss.index'
        if os.path.exists(index_path):
            index = faiss.read_index(index_path)
        
        # Load embedder model
        embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        
        logger.info(f"✅ RAG artifacts loaded: {len(chunks)} chunks, FAISS index ready")
        return chunks, index, embedder
    except Exception as e:
        logger.error(f"❌ Error loading artifacts: {e}")
        return [], None, None

def load_llm_model():
    """Load LLM model (TinyLlama untuk efisiensi)"""
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        
        MODEL_NAME = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
        
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            device_map="auto",
            torch_dtype=torch.float16
        )
        
        logger.info(f"✅ LLM model loaded: {MODEL_NAME}")
        return tokenizer, model
    except Exception as e:
        logger.error(f"❌ Error loading LLM: {e}")
        return None, None

# Load everything at startup
chunks, faiss_index, embedder = load_artifacts()
tokenizer, llm_model = load_llm_model()

# Flag untuk track model status
MODEL_READY = embedder is not None and faiss_index is not None and llm_model is not None

logger.info(f"🚀 Model status: {'READY' if MODEL_READY else 'FALLBACK MODE'}")

# ============================================================
# RAG + LLM FUNCTIONS
# ============================================================

def retrieve_topk(query, k=5, threshold=0.35):
    """Retrieve top-k relevant chunks using FAISS"""
    if not embedder or not faiss_index:
        return [], []
    
    try:
        q_emb = embedder.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True
        ).astype("float32")
        
        scores, ids = faiss_index.search(q_emb, k)
        return ids[0].tolist(), scores[0].tolist()
    except Exception as e:
        logger.error(f"Error in retrieve_topk: {e}")
        return [], []

def build_rag_context(query, k=5, threshold=0.35, max_chars=1500):
    """Build context from retrieved chunks"""
    ids, scores = retrieve_topk(query, k=k)
    
    context_parts = []
    valid_scores = []
    
    for chunk_id, score in zip(ids, scores):
        if score < threshold:
            break
        
        txt = chunks[chunk_id].strip()
        context_parts.append(f"[Source {len(context_parts)+1}]\n{txt}")
        valid_scores.append(float(score))
    
    if not context_parts:
        return None, [], []
    
    context = "\n\n---\n\n".join(context_parts)
    return context[:max_chars], [int(i) for i in ids[:len(valid_scores)]], valid_scores

def generate_rag_answer(query, k=5, max_tokens=250):
    """Generate answer using RAG + LLM"""
    if not MODEL_READY:
        # Fallback jika model tidak ready
        return _fallback_answer(query)
    
    try:
        # Build context dari retrieval
        context, chunk_ids, scores = build_rag_context(query, k=k, threshold=0.35)
        
        # Build prompt
        if context:
            prompt = f"""Kamu adalah AI Tutor batik Indonesia yang membantu dalam pembelajaran.
Jawab pertanyaan berikut dengan jelas dan singkat dalam Bahasa Indonesia.
Gunakan informasi dari dokumen di bawah jika relevan.

INFORMASI DOKUMEN:
{context}

PERTANYAAN: {query}

JAWABAN:"""
        else:
            prompt = f"""Kamu adalah AI Tutor batik Indonesia. Jawab pertanyaan berikut dalam Bahasa Indonesia.

PERTANYAAN: {query}

JAWABAN:"""
        
        # Generate dengan LLM
        inputs = tokenizer(prompt, return_tensors="pt").to(llm_model.device)
        
        with torch.no_grad():
            output = llm_model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=0.7,
                top_p=0.9,
                do_sample=True,
                eos_token_id=tokenizer.eos_token_id,
                pad_token_id=tokenizer.eos_token_id,
            )
        
        # Decode answer
        response = tokenizer.decode(
            output[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True
        ).strip()
        
        return response, chunk_ids, scores
    
    except Exception as e:
        logger.error(f"Error in generate_rag_answer: {e}")
        return _fallback_answer(query), [], []

def _fallback_answer(query):
    """Fallback answer jika LLM tidak ready"""
    query_lower = query.lower()
    
    batik_kb = {
        'batik': 'Batik adalah teknik pewarnaan kain menggunakan lilin (wax resist dyeing) yang sangat terkenal dari Indonesia.',
        'sejarah': 'Batik telah menjadi bagian dari budaya Indonesia selama berabad-abad, terutama berkembang di Jawa.',
        'motif': 'Motif batik Indonesia sangat beragam, termasuk parang, kawung, ceplok, dan banyak lagi.',
        'warisan': 'UNESCO mengakui batik Indonesia sebagai Masterpiece of Oral and Intangible Heritage of Humanity.',
        'proses': 'Proses pembuatan batik meliputi persiapan kain, pendesainan, pembatikan, pencelupan, dan pembilasan.',
        'warna': 'Warna-warna tradisional batik menggunakan bahan alami seperti indigofera (biru) dan soga (coklat).',
    }
    
    for key, answer in batik_kb.items():
        if key in query_lower:
            return answer
    
    return "Maaf, informasi tentang itu belum tersedia. Coba tanya tentang: sejarah, motif, proses, atau warisan batik."

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Main chat endpoint using RAG + LLM"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({
                'reply': 'Silakan tanyakan sesuatu tentang Batik Indonesia!',
                'timestamp': datetime.now().isoformat(),
                'model': 'empty'
            })
        
        # Generate answer dengan RAG + LLM
        answer, chunk_ids, scores = generate_rag_answer(user_message, k=5, max_tokens=300)
        
        # Prepare metadata
        metadata = {
            'retrieved_chunks': chunk_ids,
            'retrieval_scores': scores,
            'model_used': 'RAG+LLM' if MODEL_READY else 'Fallback',
            'has_context': len(chunk_ids) > 0,
            'top_score': scores[0] if scores else 0.0
        }
        
        return jsonify({
            'reply': answer,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata
        })
    
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({
            'reply': f'Terjadi error: {str(e)[:100]}. Coba lagi?',
            'timestamp': datetime.now().isoformat(),
            'error': True
        }), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'model_ready': MODEL_READY,
        'chunks_loaded': len(chunks),
        'faiss_ready': faiss_index is not None,
        'embedder_ready': embedder is not None,
        'llm_ready': llm_model is not None
    })

@app.route('/api/suggestions', methods=['GET'])
def suggestions():
    return jsonify({
        'suggestions': [
            'Apa itu Batik?',
            'Sejarah Batik Indonesia',
            'Motif-motif Batik',
            'Proses pembuatan Batik',
            'Warisan Batik UNESCO',
            'Daerah penghasil batik'
        ]
    })

# Startup logging
@app.before_request
def startup_info():
    pass

if __name__ == '__main__':
    print("\n" + "="*80)
    print("🚀 Batik AI-Tutor Starting Up")
    print("="*80)
    print(f"✅ Chunks loaded: {len(chunks)}")
    print(f"✅ FAISS index: {'Ready' if faiss_index else 'Not found'}")
    print(f"✅ Embedder model: {'Loaded' if embedder else 'Failed'}")
    print(f"✅ LLM model: {'Loaded' if llm_model else 'Failed (using fallback)'}")
    print(f"✅ Model status: {'🟢 FULL RAG+LLM' if MODEL_READY else '🟡 FALLBACK MODE'}")
    print("\n📍 Starting server on http://0.0.0.0:5000")
    print("="*80 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
