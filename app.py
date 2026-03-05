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
        
        # Load embedder model - force CPU (Ollama handles GPU; Python CUDA incompatible with this GPU)
        try:
            embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
            logger.info("✅ Embedder model loaded successfully on cpu")
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

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL    = "gpt-oss:20b"

def load_llm_model():
    """Check Ollama is reachable and the model is available.
    Returns (OLLAMA_MODEL, None) on success, (None, None) on failure."""
    import requests
    try:
        # Check Ollama server is up
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        r.raise_for_status()
        available = [m["name"] for m in r.json().get("models", [])]
        if OLLAMA_MODEL in available:
            logger.info(f"✅ Ollama ready — model '{OLLAMA_MODEL}' found")
        else:
            logger.warning(f"⚠️  Model '{OLLAMA_MODEL}' not in Ollama ({available}). "
                           f"Run: ollama pull {OLLAMA_MODEL}")
        return OLLAMA_MODEL, None   # (model_name, None) — no tokenizer needed
    except Exception as e:
        logger.error(f"❌ Cannot reach Ollama at {OLLAMA_BASE_URL}: {e}")
        return None, None

def build_inventory_summary(chunks_data):
    """Build inventory summary dynamically from chunks"""
    try:
        import re
        
        # Reconstruct full text to avoid cross-chunk section boundary issues
        full_text = '\n'.join(chunks_data)
        
        # Find section boundaries
        jetis_start = full_text.find('# Batik Motifs from Kampung Batik Jetis')
        surabaya_start = full_text.find('# Batik Motifs from Surabaya')
        
        jetis_text = full_text[jetis_start:surabaya_start] if jetis_start != -1 and surabaya_start != -1 else ''
        surabaya_text = full_text[surabaya_start:] if surabaya_start != -1 else ''
        
        # Match "## Name Motif" / "### Name Motif" headings; filter false positives
        jetis_motifs = [m.strip() for m in re.findall(r'#{2,3}\s+([\w\s\-\(\)]+?)\s+Motif(?!\w)', jetis_text)
                        if 'from' not in m and 'Meaning' not in m and 'Visual' not in m]
        surabaya_motifs = [m.strip() for m in re.findall(r'#{2,3}\s+([\w\s\-\(\)]+?)\s+Motif(?!\w)', surabaya_text)
                           if 'from' not in m and 'Meaning' not in m and 'Visual' not in m]
        
        # Deduplicate while preserving order
        jetis_motifs = list(dict.fromkeys(jetis_motifs))
        surabaya_motifs = list(dict.fromkeys(surabaya_motifs))
        
        inventory = {'jetis': jetis_motifs, 'surabaya': surabaya_motifs}
        
        # Build summary string
        total = len(inventory['jetis']) + len(inventory['surabaya'])
        summary = f"""Saat ini saya memiliki pengetahuan tentang {total} motif batik Indonesia:

**Dari Kampung Batik Jetis, Sidoarjo ({len(inventory['jetis'])} motif):**
"""
        for i, motif in enumerate(inventory['jetis'], 1):
            summary += f"{i}. {motif}\n"
        
        summary += f"\n**Dari Surabaya ({len(inventory['surabaya'])} motif):**\n"
        for i, motif in enumerate(inventory['surabaya'], 1):
            summary += f"{i}. {motif}\n"
        
        logger.info(f"✅ Inventory summary built: {total} motifs ({len(inventory['jetis'])} Jetis, {len(inventory['surabaya'])} Surabaya)")
        return summary
    
    except Exception as e:
        logger.error(f"❌ Error building inventory summary: {e}")
        return None

# Load everything at startup
chunks, faiss_index, embedder = load_artifacts()
ollama_model_name, _ = load_llm_model()  # returns (model_name, None) — no tokenizer needed for Ollama

# Reuse 'tokenizer' variable name for MODEL_READY check compatibility
tokenizer = ollama_model_name  # truthy string = Ollama reachable, None = not reachable

# Build inventory summary dynamically from chunks
inventory_summary = build_inventory_summary(chunks) if chunks else None

# MODEL_READY: embedder + faiss must be loaded; Ollama model name must be set
MODEL_READY = embedder is not None and faiss_index is not None and tokenizer is not None

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
            normalize_embeddings=True,
            device="cpu",
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

def retrieve_by_location(location):
    """Directly return all chunk IDs that belong to a specific location.
    Used when query mentions Surabaya/Jetis — bypasses FAISS threshold."""
    if location == 'surabaya':
        keywords = ['Batik Motifs from Surabaya', 'Kintir Kintiran', 'Gembili Wonokromo',
                    'Kembang Bungur', 'Sparkling', 'Remo Suroboyoan', 'Abhi Boyo']
    elif location == 'jetis':
        keywords = ['Kampung Batik Jetis', 'Liris Motif', 'Alun-Alun Contong',
                    'Burung Merak', 'Sekar Jagad', 'Parang Jabon', 'Love Putihan']
    else:
        return [], []

    ids, scores = [], []
    for i, chunk in enumerate(chunks):
        if any(kw in chunk for kw in keywords):
            ids.append(i)
            scores.append(1.0)  # Perfect score — hand-picked
    logger.info(f"📍 Location-based retrieval '{location}': {len(ids)} chunks → IDs {ids}")
    return ids, scores


def detect_location(query):
    """Return 'surabaya', 'jetis', or None based on query keywords."""
    q = query.lower()
    if any(w in q for w in ['surabaya', 'putat', 'wonokromo', 'kintir', 'gembili',
                             'bungur', 'sparkling', 'remo', 'abhi boyo']):
        return 'surabaya'
    if any(w in q for w in ['jetis', 'sidoarjo', 'liris', 'alun-alun contong',
                             'burung merak', 'sekar jagad', 'parang jabon', 'love putihan']):
        return 'jetis'
    return None


def build_rag_context(query, k=5, threshold=0.25, max_chars=4000):
    """Build context from retrieved chunks.
    Uses location-based retrieval when query targets a specific city/village."""
    query_lower = query.lower()
    location = detect_location(query)

    # If query is about listing/knowing batik from a specific location, grab ALL location chunks
    is_location_list = location and any(w in query_lower for w in [
        'batik', 'motif', 'tell', 'list', 'show', 'what', 'which',
        'sebutkan', 'apa saja', 'ceritakan', 'tentang', 'know', 'about'
    ])

    if is_location_list:
        ids, scores = retrieve_by_location(location)
    else:
        ids, scores = retrieve_topk(query, k=k, threshold=threshold)

    context_parts = []
    valid_scores = []
    valid_ids = []

    if not ids:
        logger.warning(f"No chunks retrieved for query: {query}")
        return None, [], []

    for chunk_id, score in zip(ids, scores):
        if not is_location_list and score < threshold:
            logger.debug(f"Score {score:.3f} below threshold {threshold}, stopping retrieval")
            break

        txt = chunks[chunk_id].strip()
        context_parts.append(f"[Source {len(context_parts)+1}]\n{txt}")
        valid_scores.append(float(score))
        valid_ids.append(int(chunk_id))

    if not context_parts:
        logger.warning(f"No chunks passed threshold for query: {query}. Returning first chunk anyway.")
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
    
    # Special handling: detect inventory/total count questions (Indonesian & English)
    query_lower = query.lower()
    is_inventory_question = (
        # Indonesian
        ('berapa' in query_lower or 'jumlah' in query_lower or 'total' in query_lower) and
        'batik' in query_lower and
        any(w in query_lower for w in ['motif', 'jenis', 'macam', 'kamu', 'tahu', 'ketahui', 'ada', 'semua'])
    ) or (
        # English
        ('how many' in query_lower or 'how much' in query_lower or 'total' in query_lower) and
        'batik' in query_lower and
        any(w in query_lower for w in ['motif', 'type', 'kind', 'know', 'you'])
    )
    if is_inventory_question:
        if inventory_summary:
            logger.info("Answered inventory question with dynamic summary")
            return inventory_summary, [], []
        else:
            logger.warning("Inventory summary not available, using fallback")
            return _fallback_answer(query), [], []
    
    try:
        # Detect if this is a counting/enumeration question (Indonesian & English)
        is_counting_question = any(word in query.lower() for word in [
            'berapa', 'sebutkan', 'apa saja', 'jumlah', 'jenis', 'macam',  # Indonesian
            'how many', 'list', 'what are', 'enumerate', 'types of', 'kinds of'  # English
        ])
        
        # For counting questions, use enough chunks but not too many to avoid confusion
        effective_k = 12 if is_counting_question else k
        
        # Build context dari retrieval
        logger.info(f"[Step 1] Building context for: {query!r}")
        context, chunk_ids, scores = build_rag_context(
            query, k=effective_k, threshold=0.25,
            max_chars=10000 if (is_counting_question or detect_location(query)) else 4000
        )
        logger.info(f"[Step 2] Context ready: {len(chunk_ids)} chunks, {len(context) if context else 0} chars")
        
        # Build messages using standard chat format
        system_msg = "You are an expert on Indonesian batik. Answer questions clearly and concisely based only on the provided context. Do not invent information."
        
        if context:
            if is_counting_question:
                user_msg = f"""Context about Indonesian batik:
{context}

Question: {query}

List all relevant motifs or items found in the context above. Be complete and concise."""
            else:
                user_msg = f"""Context about Indonesian batik:
{context}

Question: {query}

Answer in 2-3 sentences using only information from the context above."""
        else:
            user_msg = f"""Question about Indonesian batik: {query}

Answer briefly based on your knowledge of batik."""
        
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg},
        ]
        
        # Call Ollama API (with 1 retry on empty response)
        import requests, time
        logger.info(f"[Step 3] Calling Ollama '{OLLAMA_MODEL}' (counting={is_counting_question}, k={effective_k}, chunks={len(chunk_ids)})")
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "top_p": 0.5,
                "repeat_penalty": 1.4,
                "num_predict": 300 if is_counting_question else 200,
                "num_ctx": 8192,  # Explicit context window size
            }
        }
        
        response = ""
        for attempt in range(2):  # try up to 2 times
            r = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=180)
            r.raise_for_status()
            raw = r.json()["message"]["content"].strip()
            logger.info(f"[Step 4] Ollama raw (attempt {attempt+1}, {len(raw)} chars): {raw[:150]!r}")
            response = _clean_response(raw, is_counting=is_counting_question)
            logger.info(f"[Step 5] After clean ({len(response)} chars): {response[:150]!r}")
            if response and len(response) >= 10:
                break
            logger.warning(f"Attempt {attempt+1}: response too short ({len(response)} chars), retrying...")
            time.sleep(1)
        
        if not response or len(response) < 10:
            logger.warning("Answer too short or empty, using fallback")
            return _fallback_answer(query), chunk_ids, scores
        
        logger.info(f"✓ Ollama answer ({len(response)} chars) with {len(chunk_ids)} sources")
        return response, chunk_ids, scores
    
    except Exception as e:
        logger.error(f"Error in generate_rag_answer: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return _fallback_answer(query), [], []

def _clean_response(text, is_counting=False):
    """Clean up LLM response - remove artifacts only, keep valid content.
    Ollama (unlike TinyLlama) does NOT leak prompt instructions, so cleaning
    should be minimal to avoid destroying legitimate answer content."""
    import re
    
    if not text:
        return text
    
    # Only remove model-specific special tokens (safety net)
    text = re.sub(r'<\|[^|>]+\|>', '', text)  # <|eot_id|>, etc.
    
    # Remove [Source X] citation tags
    text = re.sub(r'\[Source \d+\]', '', text)
    
    # Convert markdown bold to plain text
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    
    # Collapse excess whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = text.strip()
    
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
        'llm_ready': ollama_model_name is not None,
        'ollama_model': ollama_model_name
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
    print(f"✅ Ollama model: {ollama_model_name if ollama_model_name else 'Not reachable (using fallback)'}")
    print(f"✅ Model status: {'🟢 FULL RAG+LLM' if MODEL_READY else '🟡 FALLBACK MODE'}")
    print("\n📍 Starting server on http://0.0.0.0:5000")
    print("="*80 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
