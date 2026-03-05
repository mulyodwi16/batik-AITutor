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

import requests as _req  # module-level import for Ollama calls

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
    """Extract motif list from chunks — used only in /api/health for diagnostics."""
    try:
        import re
        full_text = '\n'.join(chunks_data)
        jetis_start   = full_text.find('# Batik Motifs from Kampung Batik Jetis')
        surabaya_start = full_text.find('# Batik Motifs from Surabaya')
        jetis_text    = full_text[jetis_start:surabaya_start] if jetis_start != -1 and surabaya_start != -1 else ''
        surabaya_text = full_text[surabaya_start:] if surabaya_start != -1 else ''
        def _parse(text):
            ms = [m.strip() for m in re.findall(r'#{2,3}\s+([\w\s\-\(\)]+?)\s+Motif(?!\w)', text)
                  if 'from' not in m and 'Meaning' not in m and 'Visual' not in m]
            return list(dict.fromkeys(ms))
        inv = {'jetis': _parse(jetis_text), 'surabaya': _parse(surabaya_text)}
        total = len(inv['jetis']) + len(inv['surabaya'])
        logger.info(f"✅ Inventory: {total} motifs ({len(inv['jetis'])} Jetis, {len(inv['surabaya'])} Surabaya)")
        return inv
    except Exception as e:
        logger.error(f"❌ build_inventory_summary: {e}")
        return {}

# ─────────────────────────────────────────────────────────────────────────────
# Startup — load all artifacts once
# ─────────────────────────────────────────────────────────────────────────────
chunks, faiss_index, embedder = load_artifacts()
ollama_model_name, _ = load_llm_model()
tokenizer    = ollama_model_name          # kept for MODEL_READY compat
inventory_data = build_inventory_summary(chunks) if chunks else {}
MODEL_READY  = embedder is not None and faiss_index is not None and tokenizer is not None
logger.info(f"🚀 Model status: {'READY' if MODEL_READY else 'FALLBACK MODE'}")

# ── Chunk metadata: tag each chunk with its location (built once at startup) ─
# This enables metadata pre-filtering — a standard RAG pattern.
# We inspect chunk text for section headers rather than hardcoding motif names.
def _build_chunk_locations(chunks_data):
    """Tag each chunk with its location by tracking section headers in order.
    Chunks are sequential slices of the source document, so we track the
    'current section' as we scan — far more reliable than keyword matching."""
    locations = []
    current = None
    for chunk in chunks_data:
        # Section header lines define which location all subsequent chunks belong to
        if '# Batik Motifs from Kampung Batik Jetis' in chunk:
            current = 'jetis'
        elif '# Batik Motifs from Surabaya' in chunk:
            current = 'surabaya'
        locations.append(current)
    return locations

chunk_locations = _build_chunk_locations(chunks) if chunks else []
logger.info(f"📍 Chunk locations tagged: {chunk_locations.count('jetis')} jetis, "
            f"{chunk_locations.count('surabaya')} surabaya, "
            f"{chunk_locations.count(None)} general")

# ============================================================
# RAG + LLM FUNCTIONS  (pure pipeline — no keyword rules)
# ============================================================

# System prompt used for every query — the LLM handles all reasoning
_SYSTEM_PROMPT = """You are an expert AI tutor on Indonesian batik (Batik AI-Tutor).
Answer the user's question using ONLY the context provided.

Rules:
1. COUNT carefully — if asked how many motifs exist (overall or per location), count the distinct motif headings in the context and state the exact number.
2. FILTER by location — if the question mentions a specific place (e.g. Surabaya, Jetis, Sidoarjo), include only motifs/information from that place.
3. LIST completely — if asked to list or enumerate, include every relevant item from the context without skipping any.
4. DO NOT invent information that is not in the context.
5. If the context does not contain the answer, say: "I don't have information about that in my knowledge base."
6. Answer in the same language the user used (Indonesian or English)."""


# ── Named-entity location detection (proper nouns only — NOT intent routing) ─
def _detect_location(query: str):
    """Return 'surabaya', 'jetis', or None.
    Only checks proper nouns (city/village names) — not topic or intent."""
    q = query.lower()
    if any(w in q for w in ['surabaya', 'putat jaya', 'wonokromo']):
        return 'surabaya'
    if any(w in q for w in ['jetis', 'sidoarjo', 'kampung batik jetis']):
        return 'jetis'
    return None


def retrieve_topk(query, k=25):
    """Embed query → FAISS top-k → optional metadata location filter.
    When a city/village is named in the query, only chunks tagged to that
    location (plus general chunks) are kept — this is standard metadata
    pre-filtering, not keyword-based intent routing."""
    if not embedder or not faiss_index:
        return [], []
    try:
        q_emb = embedder.encode(
            [query], convert_to_numpy=True, normalize_embeddings=True, device="cpu"
        ).astype("float32")
        scores, ids = faiss_index.search(q_emb, min(k, faiss_index.ntotal))
        id_list    = ids[0].tolist()
        score_list = scores[0].tolist()

        # Metadata pre-filter: if query names a location, drop chunks from
        # the OTHER location to keep context focused.
        loc = _detect_location(query)
        if loc and chunk_locations:
            opposite = 'jetis' if loc == 'surabaya' else 'surabaya'
            filtered_ids, filtered_scores = [], []
            for cid, sc in zip(id_list, score_list):
                if cid < len(chunk_locations) and chunk_locations[cid] != opposite:
                    filtered_ids.append(cid)
                    filtered_scores.append(sc)
            id_list, score_list = filtered_ids, filtered_scores
            logger.info(f"📍 Location filter '{loc}': {len(id_list)} chunks remain")

        logger.info(f"🔍 Retrieved {len(id_list)} chunks for: {query!r}")
        return id_list, score_list
    except Exception as e:
        logger.error(f"retrieve_topk error: {e}")
        return [], []


def generate_rag_answer(query):
    """Pure RAG pipeline: embed → retrieve → LLM → answer.
    No keyword-based routing; the LLM (gpt-oss:20b) handles all reasoning."""
    if not MODEL_READY:
        logger.warning("Model not ready — using fallback")
        return _fallback_answer(query), [], []

    try:
        # ── 1. Retrieve top-25 chunks sorted by relevance ─────────────────────
        ids, scores = retrieve_topk(query)
        if not ids:
            logger.warning("No chunks retrieved — using fallback")
            return _fallback_answer(query), [], []

        # ── 2. Build context — cap to keep within Ollama's reliable generation
        #       window. Top-ranked (most relevant) chunks are included first.
        #       8 000 chars ≈ 2 000 tokens, well within num_ctx=8192 budget.
        MAX_CONTEXT_CHARS = 8_000
        parts = []
        total_chars = 0
        for i, cid in enumerate(ids):
            chunk_text = chunks[cid].strip()
            entry = f"[Source {i+1}]\n{chunk_text}"
            if total_chars + len(entry) > MAX_CONTEXT_CHARS:
                break
            parts.append(entry)
            total_chars += len(entry)

        context = "\n\n---\n\n".join(parts)
        logger.info(f"Context: {len(parts)}/{len(ids)} chunks, {len(context)} chars")

        # ── 3. Call Ollama ────────────────────────────────────────────────────
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": f"Context:\n{context}\n\nQuestion: {query}"},
            ],
            "stream": False,
            "options": {
                "temperature":    0.1,
                "top_p":          0.9,
                "repeat_penalty": 1.2,
                "num_predict":    512,
                "num_ctx":        8192,
            },
        }

        import time
        response = ""
        for attempt in range(2):
            r = _req.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=180)
            r.raise_for_status()
            raw = r.json()["message"]["content"].strip()
            logger.info(f"Ollama attempt {attempt+1} ({len(raw)} chars): {raw[:150]!r}")
            response = _clean_response(raw)
            if response and len(response) >= 10:
                break
            time.sleep(1)

        if not response or len(response) < 10:
            logger.warning("Empty Ollama response — fallback")
            return _fallback_answer(query), ids, scores

        logger.info(f"✓ Answer ready ({len(response)} chars, {len(parts)} sources)")
        return response, ids[:len(parts)], scores[:len(parts)]

    except Exception as e:
        logger.error(f"generate_rag_answer error: {e}")
        import traceback; logger.error(traceback.format_exc())
        return _fallback_answer(query), [], []


def _clean_response(text):
    """Minimal post-processing — Ollama does not leak prompts."""
    import re
    if not text:
        return text
    text = re.sub(r'<\|[^|>]+\|>', '', text)       # special tokens
    text = re.sub(r'\[Source \d+\]', '', text)       # citation tags
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # bold → plain
    text = re.sub(r'__([^_]+)__',     r'\1', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ',    text)
    text = text.strip()
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
    jetis_count    = len(inventory_data.get('jetis', []))
    surabaya_count = len(inventory_data.get('surabaya', []))
    return jsonify({
        'status': 'ok',
        'model_ready': MODEL_READY,
        'chunks_loaded': len(chunks),
        'faiss_ready': faiss_index is not None,
        'embedder_ready': embedder is not None,
        'llm_ready': ollama_model_name is not None,
        'ollama_model': ollama_model_name,
        'inventory': {
            'total': jetis_count + surabaya_count,
            'jetis': jetis_count,
            'surabaya': surabaya_count,
        },
    })

@app.route('/api/debug/retrieve', methods=['GET'])
def debug_retrieve():
    """Debug endpoint — test FAISS retrieval without LLM generation"""
    query = request.args.get('q', 'batik').strip()
    k     = min(int(request.args.get('k', 10)), 25)

    if not embedder or not faiss_index:
        return jsonify({'error': 'FAISS or embedder not loaded'}), 500

    try:
        ids, scores = retrieve_topk(query, k=k)
        retrieved = [
            {
                'id':    int(cid),
                'score': round(float(sc), 4),
                'text':  chunks[cid][:200] + ('...' if len(chunks[cid]) > 200 else ''),
            }
            for cid, sc in zip(ids, scores)
        ]
        return jsonify({'query': query, 'num_retrieved': len(ids), 'chunks': retrieved})
    except Exception as e:
        logger.error(f"debug_retrieve error: {e}")
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
    
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
