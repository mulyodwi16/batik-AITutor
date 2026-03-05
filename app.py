from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import json
import os
import numpy as np
from datetime import datetime
import torch
import logging

# ============================================================
# DISABLE CUDA TO AVOID GPU COMPATIBILITY ISSUES
# ============================================================
os.environ['CUDA_VISIBLE_DEVICES'] = ''
torch.cuda.is_available = lambda: False

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
        try:
            with open(chunks_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Handle both {"chunks": [...]} and [...]
                if isinstance(data, dict):
                    chunks = data.get('chunks', data)
                else:
                    chunks = data
                
                if isinstance(chunks, list) and len(chunks) > 0:
                    logger.info(f"✅ Chunks loaded from {chunks_path}: {len(chunks)} chunks")
                    return chunks
                else:
                    logger.warning(f"⚠️  chunks.json exists but is empty or invalid")
                    return []
        except Exception as e:
            logger.error(f"❌ Error parsing chunks.json: {e}")
            return []
    else:
        logger.warning(f"⚠️  {chunks_path} not found. RAG will be disabled. Run AI_Tutor.ipynb to generate artifacts.")
        return []

def load_artifacts():
    """Load FAISS index, chunks, and embedder"""
    try:
        import faiss
        from sentence_transformers import SentenceTransformer
        
        chunks = load_chunks()
        index = None
        embedder = None
        
        # Load FAISS index
        index_path = 'artifacts/faiss.index'
        if os.path.exists(index_path):
            try:
                index = faiss.read_index(index_path)
                logger.info(f"✅ FAISS index loaded: {index.ntotal} vectors")
            except Exception as e:
                logger.error(f"❌ Error loading FAISS index: {e}")
        else:
            logger.warning(f"⚠️  FAISS index not found at {index_path}")
        
        # Load embedder model
        try:
            embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            logger.info("✅ Embedder model loaded successfully")
        except Exception as e:
            logger.error(f"❌ Error loading embedder: {e}")
            logger.warning("⚠️  Will use LLM-only mode without semantic search")
        
        if chunks and index and embedder:
            logger.info(f"✅ RAG artifacts fully loaded: {len(chunks)} chunks")
        else:
            logger.warning(f"⚠️  Partial artifact loading - chunks:{len(chunks)}, faiss:{index is not None}, embedder:{embedder is not None}")
        
        return chunks, index, embedder
    
    except Exception as e:
        logger.error(f"❌ Error in load_artifacts: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return [], None, None

def load_llm_model():
    """Load LLM model (TinyLlama untuk efisiensi)"""
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        
        MODEL_NAME = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
        
        # Force CPU mode (CUDA disabled at top of file)
        device = "cpu"
        dtype = torch.float32
        
        logger.info(f"Loading LLM on {device} with dtype={dtype}")
        
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            device_map={"": device},
            torch_dtype=dtype
        )
        model = model.to(device)
        
        logger.info(f"✅ LLM model loaded: {MODEL_NAME} on {device}")
        return tokenizer, model
    except Exception as e:
        logger.error(f"❌ Error loading LLM: {e}")
        import traceback
        logger.error(traceback.format_exc())
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

def retrieve_topk(query, k=5, threshold=0.25):
    """Retrieve top-k relevant chunks using FAISS"""
    if not embedder or not faiss_index:
        logger.warning(f"Embedder or FAISS index not available. Cannot retrieve for query: {query}")
        return [], []
    
    try:
        q_emb = embedder.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True
        ).astype("float32")
        
        scores, ids = faiss_index.search(q_emb, k)
        result_ids = ids[0].tolist()
        result_scores = scores[0].tolist()
        
        logger.info(f"🔍 Retrieved top-{k} for '{query}': IDs={result_ids}, Scores={[f'{s:.3f}' for s in result_scores]}")
        return result_ids, result_scores
    except Exception as e:
        logger.error(f"Error in retrieve_topk: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return [], []

def build_rag_context(query, k=5, threshold=0.25, max_chars=1500):
    """Build context from retrieved chunks"""
    ids, scores = retrieve_topk(query, k=k, threshold=threshold)
    
    context_parts = []
    valid_scores = []
    valid_ids = []
    
    if not ids:
        logger.warning(f"No chunks retrieved for query: {query}")
        return None, [], []
    
    for chunk_id, score in zip(ids, scores):
        if score < threshold:
            logger.debug(f"Score {score:.3f} below threshold {threshold}, stopping retrieval")
            break
        
        txt = chunks[chunk_id].strip()
        context_parts.append(f"[Source {len(context_parts)+1}]\n{txt}")
        valid_scores.append(float(score))
        valid_ids.append(int(chunk_id))
    
    if not context_parts:
        logger.warning(f"No chunks passed threshold for query: {query}. Returning first chunk anyway.")
        # Fallback: use first chunk even if below threshold
        txt = chunks[ids[0]].strip()
        context_parts.append(f"[Source 1]\n{txt}")
        valid_scores.append(float(scores[0]))
        valid_ids.append(int(ids[0]))
    
    context = "\n\n---\n\n".join(context_parts)
    logger.info(f"Context built with {len(context_parts)} chunks, total {len(context)} chars")
    return context[:max_chars], valid_ids, valid_scores

def generate_rag_answer(query, k=10, max_tokens=200):
    """Generate answer using RAG + LLM with synthesis (not raw chunks)"""
    if not MODEL_READY:
        logger.warning(f"Model not ready, using fallback for query: {query}")
        return _fallback_answer(query), [], []
    
    try:
        # Detect if this is a counting/enumeration question
        is_counting_question = any(word in query.lower() for word in ['berapa', 'berapa banyak', 'sebutkan', 'apa saja', 'ada berapa', 'jumlah', 'jenis'])
        
        # For counting questions, use enough chunks but not too many to avoid confusion
        effective_k = 12 if is_counting_question else k
        
        # Build context dari retrieval
        context, chunk_ids, scores = build_rag_context(query, k=effective_k, threshold=0.25)
        
        # Build prompt dengan handling khusus untuk berbagai tipe pertanyaan
        if context:
            # For counting/enumeration questions, be more explicit
            if is_counting_question:
                prompt = f"""Anda adalah ahli batik Indonesia.

Tugas: Jawab pertanyaan dengan MENYEBUTKAN SEMUA item/jenis/motif yang ditemukan di dokumen.
Format jawaban:
- Gunakan kalimat Anda SENDIRI (jangan copy-paste)
- Jika diminta sebutkan: tuliskan daftar atau penjelasan setiap item
- JANGAN membaur atau ulangi informasi yang sama

Dokumen:
{context}

Pertanyaan: {query}

Jawaban (dengan menyebutkan semua yang relevan, jelas dan padat):"""
            else:
                prompt = f"""Anda adalah AI Tutor Batik Indonesia. Jawab dengan 1-3 kalimat menggunakan informasi dari dokumen.

Dokumen:
{context}

Pertanyaan: {query}

Jawaban:"""
        else:
            prompt = f"""Anda adalah AI Tutor Batik Indonesia. Jawab pertanyaan berikut dengan singkat dalam Bahasa Indonesia.

Pertanyaan: {query}

Jawaban:"""
        
        # Generate dengan LLM
        logger.info(f"Generating answer (counting={is_counting_question}, k={effective_k}) with context ({len(chunk_ids)} chunks)")
        inputs = tokenizer(prompt, return_tensors="pt").to(llm_model.device)
        
        with torch.no_grad():
            output = llm_model.generate(
                **inputs,
                max_new_tokens=250 if is_counting_question else 180,  # Slightly more for enumeration
                temperature=0.2,  # Even lower - more focused
                top_p=0.5,        # More deterministic
                do_sample=True,
                eos_token_id=tokenizer.eos_token_id,
                pad_token_id=tokenizer.eos_token_id,
            )
        
        # Decode answer
        response = tokenizer.decode(
            output[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True
        ).strip()
        
        # Clean up response - AGGRESSIVE cleaning for counting questions
        response = _clean_response(response, is_counting=is_counting_question)
        
        # Validate answer is not just raw chunk (sanity check)
        if not response or len(response) < 10:
            logger.warning(f"Answer too short or empty, using fallback")
            return _fallback_answer(query), chunk_ids, scores
        
        # Clean up to prevent memory leak
        del inputs, output
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        
        logger.info(f"✓ Generated synthesized answer ({len(response)} chars) with {len(chunk_ids)} sources")
        return response, chunk_ids, scores
    
    except Exception as e:
        logger.error(f"Error in generate_rag_answer: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return _fallback_answer(query), [], []

def _clean_response(text, is_counting=False):
    """Clean up LLM response - remove artifacts, instructions, repetition"""
    import re
    
    # Remove common instruction text that might slip through
    text = re.sub(r'Tugas:|Format jawaban:|Dokumen:|Pertanyaan:|Jawaban.*?:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'PENTING:|INFORMASI DARI DOKUMEN:|PERTANYAAN:|JAWABAN', '', text, flags=re.IGNORECASE)
    text = re.sub(r'jangan.*?copy-paste', '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove [Source X] tags
    text = re.sub(r'\[Source \d+\]', '', text)
    text = re.sub(r'\[source \d+\]', '', text)
    
    # Remove markdown
    text = re.sub(r'\*\*', '', text)
    text = re.sub(r'###+', '', text)
    text = re.sub(r'__+', '', text)
    
    # Remove bullet points at start of lines
    text = re.sub(r'^\s*[-•*]\s+', '', text, flags=re.MULTILINE)
    
    # For counting questions - remove repetitive lines aggressively
    if is_counting:
        lines = text.split('\n')
        seen_lines = set()
        unique_lines = []
        for line in lines:
            line = line.strip()
            # Normalize for dedup
            norm_line = re.sub(r'\s+', ' ', line).lower()
            if line and norm_line not in seen_lines and len(line) > 5:
                # Skip very instruction-like lines
                if not any(kw in line.lower() for kw in ['pertanyaan', 'jawaban', 'dokumen', 'tugas', 'format']):
                    seen_lines.add(norm_line)
                    unique_lines.append(line)
        text = '\n'.join(unique_lines)
    
    # Clean whitespace and normalize
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove any remaining double words/fragments
    words = text.split()
    # Remove obvious duplicates (same word appearing 3+ times in a row)
    cleaned_words = []
    prev_word = None
    repeat_count = 0
    for word in words:
        if word.lower() == prev_word.lower() if prev_word else False:
            repeat_count += 1
            if repeat_count < 2:  # Allow one repeat
                cleaned_words.append(word)
        else:
            cleaned_words.append(word)
            prev_word = word
            repeat_count = 0
    
    text = ' '.join(cleaned_words)
    
    # Ensure proper punctuation
    text = text.strip()
    if text and not text.endswith('.'):
        text += '.'
    
    # Capitalize first letter
    if text:
        text = text[0].upper() + text[1:]
    
    return text

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
        
        # Generate answer dengan RAG + LLM (uses default k=10, with auto-detection for counting questions)
        answer, chunk_ids, scores = generate_rag_answer(user_message)
        
        # Prepare metadata
        metadata = {
            'retrieved_chunks': chunk_ids,
            'retrieval_scores': scores,
            'model_used': 'RAG+LLM' if MODEL_READY else 'Fallback',
            'has_context': len(chunk_ids) > 0,
            'top_score': scores[0] if scores else 0.0,
            'answer_length': len(answer)
        }
        
        # Clean up memory
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        
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

@app.route('/api/debug/retrieve', methods=['GET'])
def debug_retrieve():
    """Debug endpoint to test FAISS retrieval without LLM generation"""
    query = request.args.get('q', 'batik').strip()
    k = min(int(request.args.get('k', 5)), 10)
    threshold = float(request.args.get('threshold', 0.25))
    
    if not embedder or not faiss_index:
        return jsonify({'error': 'FAISS or embedder not loaded'}), 500
    
    try:
        context, chunk_ids, scores = build_rag_context(query, k=k, threshold=threshold)
        
        retrieved_chunks = []
        for idx, score in zip(chunk_ids, scores):
            retrieved_chunks.append({
                'id': int(idx),
                'score': float(score),
                'text': chunks[idx][:200] + '...' if len(chunks[idx]) > 200 else chunks[idx]
            })
        
        return jsonify({
            'query': query,
            'threshold': threshold,
            'num_retrieved': len(chunk_ids),
            'chunks': retrieved_chunks,
            'context_char_length': len(context) if context else 0
        })
    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}")
        return jsonify({'error': str(e)}), 500

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
