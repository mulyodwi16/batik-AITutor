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
    """Load LLM model (Llama-3.2-3B-Instruct)"""
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        
        MODEL_NAME = "meta-llama/Llama-3.1-8B-Instruct"
        
        # Force CPU mode (CUDA disabled at top of file)
        device = "cpu"
        dtype = torch.float32
        
        logger.info(f"Loading LLM on {device} with dtype={dtype}")
        logger.info(f"Model: {MODEL_NAME} (requires HuggingFace login with accepted license)")
        
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            device_map={"": device},
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
        )
        model = model.to(device)
        
        logger.info(f"✅ LLM model loaded: {MODEL_NAME} on {device}")
        return tokenizer, model
    except Exception as e:
        logger.error(f"❌ Error loading LLM: {e}")
        import traceback
        logger.error(traceback.format_exc())
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
tokenizer, llm_model = load_llm_model()

# Build inventory summary dynamically from chunks
inventory_summary = build_inventory_summary(chunks) if chunks else None

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
    
    # Special handling: detect inventory/total count questions
    query_lower = query.lower()
    if any(phrase in query_lower for phrase in ['berapa batik', 'ada berapa batik', 'total batik', 'jumlah batik', 'berapa banyak batik']):
        if any(word in query_lower for word in ['total', 'semua', 'seluruh', 'yang kamu', 'ketahui']):
            # Return dynamic inventory summary if available
            if inventory_summary:
                logger.info(f"Answered inventory question with dynamic summary")
                return inventory_summary, [], []
            else:
                logger.warning(f"Inventory summary not available, using fallback")
                return _fallback_answer(query), [], []
    
    try:
        # Detect if this is a counting/enumeration question
        is_counting_question = any(word in query.lower() for word in ['berapa', 'berapa banyak', 'sebutkan', 'apa saja', 'ada berapa', 'jumlah', 'jenis'])
        
        # For counting questions, use enough chunks but not too many to avoid confusion
        effective_k = 12 if is_counting_question else k
        
        # Build context dari retrieval
        context, chunk_ids, scores = build_rag_context(query, k=effective_k, threshold=0.25)
        
        # Build messages using standard chat format (apply_chat_template handles any model)
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
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        # Generate dengan LLM
        logger.info(f"Generating answer (counting={is_counting_question}, k={effective_k}) with context ({len(chunk_ids)} chunks)")
        inputs = tokenizer(prompt, return_tensors="pt").to(llm_model.device)
        
        # Build eos_token_ids - include <|eot_id|> for Llama 3.x
        eos_ids = [tokenizer.eos_token_id]
        eot_id = tokenizer.convert_tokens_to_ids("<|eot_id|>")
        if eot_id and eot_id != tokenizer.unk_token_id:
            eos_ids.append(eot_id)
        
        with torch.no_grad():
            output = llm_model.generate(
                **inputs,
                max_new_tokens=250 if is_counting_question else 180,
                temperature=0.2,
                top_p=0.5,
                do_sample=True,
                repetition_penalty=1.4,
                no_repeat_ngram_size=4,
                eos_token_id=eos_ids,
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
    
    # Remove prompt leakage patterns (any model special tokens)
    text = re.sub(r'<\|[^|>]+\|>', '', text)  # <|eot_id|>, <|start_header_id|>, etc.
    text = re.sub(r'<\|system\|>.*?<\|assistant\|>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<\|user\|>.*', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'Context about.*?Question:', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'Answer in \d[-\w\s]+sentences.*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'List all relevant.*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Question:.*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Answer:', '', text, flags=re.IGNORECASE)
    
    # Remove [Source X] tags
    text = re.sub(r'\[Source \d+\]', '', text)
    
    # Remove markdown headers
    text = re.sub(r'#{2,}\s+', '', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold** → bold
    text = re.sub(r'__([^_]+)__', r'\1', text)
    
    # Remove bullet points at start of lines (optional: keep for counting)
    if not is_counting:
        text = re.sub(r'^\s*[-•*]\s+', '', text, flags=re.MULTILINE)
    
    # For counting questions - remove repetitive lines aggressively
    if is_counting:
        lines = text.split('\n')
        seen_lines = set()
        unique_lines = []
        for line in lines:
            line = line.strip()
            norm_line = re.sub(r'\s+', ' ', line).lower()
            if line and norm_line not in seen_lines and len(line) > 3:
                seen_lines.add(norm_line)
                unique_lines.append(line)
        text = '\n'.join(unique_lines)
    
    # Collapse whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = text.strip()
    
    # Remove obvious word-level repetition (3+ same word in a row)
    text = re.sub(r'(\b\w+\b)( \1){2,}', r'\1', text)
    
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
