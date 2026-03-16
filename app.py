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
    """Load chunks AND metadata from chunks.json (v2.0 format)"""
    chunks_path = 'artifacts/chunks.json'
    if os.path.exists(chunks_path):
        try:
            with open(chunks_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # v2.0 format: {"metadata": {...}, "chunks": [...], "chunk_metadata": [...]}
                if isinstance(data, dict) and 'chunks' in data:
                    chunks = data.get('chunks', [])
                    chunk_metadata = data.get('chunk_metadata', [])
                    metadata_v = data.get('metadata', {})
                    
                    if isinstance(chunks, list) and len(chunks) > 0:
                        logger.info(f"✅ Chunks loaded: {len(chunks)} chunks (v{metadata_v.get('version', '1.0')})")
                        if chunk_metadata:
                            logger.info(f"✅ Metadata loaded: {len(chunk_metadata)} entries")
                        return chunks, chunk_metadata
                    else:
                        logger.warning(f"⚠️  chunks.json exists but is empty")
                        return [], []
                # Fallback for old format
                elif isinstance(data, list):
                    logger.info(f"✅ Loaded legacy format: {len(data)} chunks")
                    return data, []
                else:
                    logger.warning(f"⚠️  Invalid chunks.json format")
                    return [], []
        except Exception as e:
            logger.error(f"❌ Error parsing chunks.json: {e}")
            return [], []
    else:
        logger.warning(f"⚠️  {chunks_path} not found. RAG will be disabled. Run setup-artifacts-new.py to generate artifacts.")
        return [], []

def load_artifacts():
    """Load FAISS index, chunks, metadata, and embedder"""
    try:
        import faiss
        from sentence_transformers import SentenceTransformer
        
        chunks, chunk_metadata = load_chunks()
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
        
        return chunks, index, embedder, chunk_metadata
    
    except Exception as e:
        logger.error(f"❌ Error in load_artifacts: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return [], None, None, []

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL    = "qwen2.5:14b"

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

def build_inventory_summary(metadata_list):
    """Extract motif list from chunk_metadata — used only in /api/health for diagnostics."""
    try:
        inv = {'jetis': set(), 'surabaya': set(), 'knowledge': set()}
        
        for meta in metadata_list:
            if not isinstance(meta, dict):
                continue
            
            location = meta.get('location', '').lower()
            title = meta.get('file_title', '')
            subcategory = meta.get('subcategory', '')
            
            # Classify by location
            if 'sidoarjo' in location or 'jetis' in location:
                if subcategory == 'motif':
                    inv['jetis'].add(title)
            elif 'surabaya' in location:
                if subcategory == 'motif':
                    inv['surabaya'].add(title)
            elif subcategory == 'culture' or subcategory == 'village':
                inv['knowledge'].add(title)
        
        # Convert sets to sorted lists
        inv_list = {
            'jetis': sorted(inv['jetis']),
            'surabaya': sorted(inv['surabaya']),
            'knowledge': sorted(inv['knowledge'])
        }
        total = sum(len(v) for v in inv_list.values())
        logger.info(f"✅ Inventory: {total} items ({len(inv_list['jetis'])} Jetis, {len(inv_list['surabaya'])} Surabaya, {len(inv_list['knowledge'])} knowledge)")
        return inv_list
    except Exception as e:
        logger.error(f"❌ build_inventory_summary: {e}")
        return {'jetis': [], 'surabaya': [], 'knowledge': []}

# ─────────────────────────────────────────────────────────────────────────────
# Startup — load all artifacts once
# ─────────────────────────────────────────────────────────────────────────────
chunks, faiss_index, embedder, chunk_metadata = load_artifacts()
ollama_model_name, _ = load_llm_model()
tokenizer    = ollama_model_name          # kept for MODEL_READY compat
inventory_data = build_inventory_summary(chunk_metadata) if chunk_metadata else {}
MODEL_READY  = embedder is not None and faiss_index is not None and tokenizer is not None
logger.info(f"🚀 Model status: {'READY' if MODEL_READY else 'FALLBACK MODE'}")

# ── Build chunk location map from metadata (for filtering) ──────────────────
# Maps chunk ID → location (more reliable than text parsing)
def _build_chunk_locations_from_metadata(metadata_list):
    """Build location map from structured metadata."""
    locations = {}
    for i, meta in enumerate(metadata_list):
        location = meta.get('location', '')
        if 'sidoarjo' in location.lower() or 'jetis' in location.lower():
            locations[i] = 'jetis'
        elif 'surabaya' in location.lower():
            locations[i] = 'surabaya'
        else:
            locations[i] = 'general'
    return locations

chunk_location_map = _build_chunk_locations_from_metadata(chunk_metadata) if chunk_metadata else {}
logger.info(f"📍 Chunk locations loaded from metadata: {len([l for l in chunk_location_map.values() if l == 'jetis'])} jetis, "
            f"{len([l for l in chunk_location_map.values() if l == 'surabaya'])} surabaya")

# ============================================================
# RAG + LLM FUNCTIONS  (pure pipeline — no keyword rules)
# ============================================================

# System prompt used for every query — the LLM handles all reasoning
_SYSTEM_PROMPT = """You are an expert AI tutor on Indonesian batik (Batik AI-Tutor).
Answer the user's question using ONLY the context provided.

=== CRITICAL RULES ===

1. MOTIF EXTRACTION (Most Important):
   - Parse headings like "# XXX Motif" or "[Source N]\n# YYY Motif" in context
   - Extract ALL UNIQUE motif names — check entire context carefully
   - Count DISTINCT motif titles (use set logic, not chunk count)
   - List ALL motif names when asked "how many" or "what motifs"
   - CRITICAL: Make sure you find and list EVERY single motif heading, don't miss any
   - Example: If context has "Alun-Alun Contong Motif", "Parang Jabon Motif", "Sekar Jagad Motif"
     CORRECT: "Ada 3 motif: 1) Alun-Alun Contong, 2) Parang Jabon, 3) Sekar Jagad"
     WRONG: "Batik Jetis memiliki motif-motif tradisional" (too generic)
   - Always verify: Count = number of "# XXX Motif" headers in context

2. COUNT carefully — if asked for count:
   - For "Berapa motif dari Jetis?": Extract unique motif names from context and state exact number
   - For comparisons: Compare specific attributes, not generic descriptions
   - Always provide NUMBER first, then explanation

3. LIST completely — if asked to list or enumerate:
   - Include EVERY relevant item from context without skipping
   - For motifs: List all motif names with brief descriptions if available
   - Format as numbered list for clarity

4. LOCATION HANDLING:
   - If question asks about ONE location: use ONLY that location's motifs/information
   - If question compares MULTIPLE locations: clearly label and separate information by location
   - Example for comparative: "Jetis memiliki: [list]; Surabaya memiliki: [list]"

5. DO NOT invent information not in context
   - If context incomplete, say so
   - If answer not available: "I don't have information about that in my knowledge base."

6. Answer in the same language the user used (Indonesian or English)

7. SPECIFICITY over generic:
   - Say motif names explicitly rather than "batik memiliki motif-motif"
   - If context has motif names, MUST list them in answer"""


# ── Named-entity location detection (proper nouns only — NOT intent routing) ─
def _detect_locations(query: str):
    """Return LIST of locations found in query: [], ['surabaya'], ['jetis'], or ['jetis', 'surabaya'].
    Only checks proper nouns (city/village names) — not topic or intent.
    
    This supports BOTH single-location and multi-location (comparative) queries.
    """
    locs = []
    q = query.lower()
    
    # Check for Surabaya (first, but don't return early)
    if any(w in q for w in ['surabaya', 'putat jaya', 'wonokromo', 'gembili', 'gadung', 'bendul merisi']):
        locs.append('surabaya')
    
    # Check for Jetis (second, so both can be detected)
    if any(w in q for w in ['jetis', 'sidoarjo', 'kampung batik jetis']):
        locs.append('jetis')
    
    return locs


def _is_motif_enumeration_query(query: str) -> bool:
    """Detect queries that likely require exhaustive motif retrieval/listing."""
    q = query.lower()
    keywords = [
        'motif', 'berapa', 'jumlah', 'hitung', 'count', 'how many',
        'semua', 'daftar', 'list', 'sebutkan', 'apa saja'
    ]
    return any(k in q for k in keywords)


def retrieve_topk(query, k=None):
    """Embed query → FAISS top-k → metadata-based location filter.
    
    Location filtering strategy:
    - No location detected: keep all chunks (generic query), use default k
    - One location detected: keep only that location + general chunks (focused query), increase k to capture all motifs
    - Two locations detected: keep both locations + general chunks (comparative query), use larger k
    
    This enables both focused and comparative queries to work correctly.
    """
    if not embedder or not faiss_index:
        return [], []
    
    # Auto-determine k. Use a wider candidate pool for motif counting/listing
    # so generic motif queries can still surface complete motif coverage.
    if k is None:
        locs = _detect_locations(query)
        motif_enumeration = _is_motif_enumeration_query(query)
        if motif_enumeration:
            k = min(63, faiss_index.ntotal)  # exhaustive search for motif enumeration/count queries
        elif locs:  # Location filter will be applied
            k = 40  # Larger for location-specific queries (to capture all motifs from that location)
        else:
            k = 25  # Default for generic queries
    
    try:
        q_emb = embedder.encode(
            [query], convert_to_numpy=True, normalize_embeddings=True, device="cpu"
        ).astype("float32")
        scores, ids = faiss_index.search(q_emb, min(k, faiss_index.ntotal))
        id_list    = ids[0].tolist()
        score_list = scores[0].tolist()

        # Metadata-based location filtering
        locs = _detect_locations(query)
        
        if locs and chunk_location_map:
            if len(locs) == 1:
                # Single location: filter out the opposite location for focus
                loc = locs[0]
                opposite = 'jetis' if loc == 'surabaya' else 'surabaya'
                filtered_ids, filtered_scores = [], []
                for cid, sc in zip(id_list, score_list):
                    chunk_loc = chunk_location_map.get(cid, 'general')
                    if chunk_loc != opposite:  # Keep: same location + general
                        filtered_ids.append(cid)
                        filtered_scores.append(sc)
                id_list, score_list = filtered_ids, filtered_scores
                logger.info(f"📍 Location filter '{loc}' (single): {len(id_list)} chunks remain")
            else:
                # Multiple locations (comparative query): keep all detected locations + general
                # Don't filter by opposite — both locations are important for comparison
                filtered_ids, filtered_scores = [], []
                for cid, sc in zip(id_list, score_list):
                    chunk_loc = chunk_location_map.get(cid, 'general')
                    if chunk_loc in locs or chunk_loc == 'general':
                        filtered_ids.append(cid)
                        filtered_scores.append(sc)
                id_list, score_list = filtered_ids, filtered_scores
                logger.info(f"📍 Locations detected: {locs} (comparative query) → {len(id_list)} chunks")

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
        #       Ollama num_ctx=8192 allows ~2000 tokens ≈ 8000 chars; bumped to 9500 to ensure
        #       all motifs are captured for location-specific queries.
        MAX_CONTEXT_CHARS = 9_500
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
                "temperature":    0.3,  # Increased from 0.1 for better list generation and motif extraction
                "top_p":          0.95,  # Slightly increased for more diverse structured outputs
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
        
        # Generate answer with RAG + LLM (retrieve_topk auto-tunes candidate size)
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
    print("[STARTUP] Batik AI-Tutor Starting Up")
    print("="*80)
    print(f"[OK] Chunks loaded: {len(chunks)}")
    print(f"[OK] FAISS index: {'Ready' if faiss_index else 'Not found'}")
    print(f"[OK] Embedder model: {'Loaded' if embedder else 'Failed'}")
    print(f"[OK] Ollama model: {ollama_model_name if ollama_model_name else 'Not reachable (using fallback)'}")
    print(f"[OK] Model status: {'FULL RAG+LLM' if MODEL_READY else 'FALLBACK MODE'}")
    print("\n[INFO] Starting server on http://0.0.0.0:5000")
    print("="*80 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
