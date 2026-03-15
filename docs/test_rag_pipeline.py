#!/usr/bin/env python3
"""Test the full RAG pipeline: retrieval + LLM generation"""
import json
import os
import sys
import requests

# Load artifacts
print("\n" + "="*80)
print("🔧 LOADING ARTIFACTS")
print("="*80)

with open('artifacts/chunks.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

chunks = data.get('chunks', [])
chunk_metadata = data.get('chunk_metadata', [])
print(f"✓ Loaded {len(chunks)} chunks")

# Load embedder
from sentence_transformers import SentenceTransformer
import faiss

embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
faiss_index = faiss.read_index('artifacts/faiss.index')
print(f"✓ Embedder and FAISS loaded")

# Test queries
test_queries = [
    "Apa itu Batik?",
    "Berapa banyak motif batik yang ada dari Jetis Sidoarjo?",
    "Sebutkan motif-motif batik dari Surabaya",
    "Apa perbedaan batik Jetis dan Surabaya?",
]

def _detect_location(query):
    """Return 'surabaya', 'jetis', or None."""
    q = query.lower()
    if any(w in q for w in ['surabaya', 'putat jaya', 'wonokromo']):
        return 'surabaya'
    if any(w in q for w in ['jetis', 'sidoarjo', 'kampung batik jetis']):
        return 'jetis'
    return None

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

chunk_location_map = _build_chunk_locations_from_metadata(chunk_metadata)

def retrieve_topk(query, k=25):
    """Same retrieval function from app.py"""
    try:
        q_emb = embedder.encode(
            [query], convert_to_numpy=True, normalize_embeddings=True, device="cpu"
        ).astype("float32")
        scores, ids = faiss_index.search(q_emb, min(k, faiss_index.ntotal))
        id_list    = ids[0].tolist()
        score_list = scores[0].tolist()

        loc = _detect_location(query)
        if loc and chunk_location_map:
            opposite = 'jetis' if loc == 'surabaya' else 'surabaya'
            filtered_ids, filtered_scores = [], []
            for cid, sc in zip(id_list, score_list):
                chunk_loc = chunk_location_map.get(cid, 'general')
                if chunk_loc != opposite:
                    filtered_ids.append(cid)
                    filtered_scores.append(sc)
            id_list, score_list = filtered_ids, filtered_scores

        return id_list, score_list
    except Exception as e:
        print(f"Error in retrieve_topk: {e}")
        return [], []

# Test retrieval for each query
for query in test_queries:
    print("\n" + "="*80)
    print(f"🔍 QUERY: {query}")
    print("="*80)
    
    ids, scores = retrieve_topk(query)
    print(f"Retrieved {len(ids)} chunks:")
    
    for i, (cid, score) in enumerate(list(zip(ids, scores))[:5]):
        meta = chunk_metadata[cid]
        print(f"\n  [{i+1}] Score: {score:.4f}")
        print(f"      Title: {meta.get('file_title', 'N/A')[:60]}")
        print(f"      Location: {meta.get('location', 'N/A')}")
        print(f"      Preview: {chunks[cid][:100]}...")
    
    # Build context like app.py does
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
    print(f"\n📝 Context summary:")
    print(f"   Chunks used: {len(parts)}/{len(ids)}")
    print(f"   Context chars: {len(context)}")
    
    # Show start of context
    print(f"\n📋 CONTEXT PREVIEW (first 800 chars):")
    print("-"*80)
    print(context[:800])
    print("-"*80 + "\n")

# Now test with Ollama
print("\n" + "="*80)
print("🧠 TESTING WITH OLLAMA")
print("="*80)

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:14b"

try:
    r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
    available = [m["name"] for m in r.json().get("models", [])]
    if OLLAMA_MODEL in available:
        print(f"✓ Ollama is ready and model '{OLLAMA_MODEL}' found")
    else:
        print(f"✗ Model '{OLLAMA_MODEL}' not found. Available: {available}")
        sys.exit(1)
except Exception as e:
    print(f"✗ Cannot reach Ollama at {OLLAMA_BASE_URL}: {e}")
    sys.exit(1)

# Test with first query
query = test_queries[0]
ids, scores = retrieve_topk(query)
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

SYSTEM_PROMPT = """You are an expert AI tutor on Indonesian batik (Batik AI-Tutor).
Answer the user's question using ONLY the context provided.

Rules:
1. COUNT carefully — if asked how many motifs exist (overall or per location), count the distinct motif headings in the context and state the exact number.
2. FILTER by location — if the question mentions a specific place (e.g. Surabaya, Jetis, Sidoarjo), include only motifs/information from that place.
3. LIST completely — if asked to list or enumerate, include every relevant item from the context without skipping any.
4. DO NOT invent information that is not in the context.
5. If the context does not contain the answer, say: "I don't have information about that in my knowledge base."
6. Answer in the same language the user used (Indonesian or English)."""

payload = {
    "model": OLLAMA_MODEL,
    "messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": f"Context:\n{context}\n\nQuestion: {query}"},
    ],
    "stream": False,
    "options": {
        "temperature": 0.1,
        "top_p": 0.9,
        "repeat_penalty": 1.2,
        "num_predict": 512,
        "num_ctx": 8192,
    },
}

print(f"\n📊 Payload info:")
print(f"   Query: {query}")
print(f"   System prompt length: {len(SYSTEM_PROMPT)} chars")
print(f"   Context length: {len(context)} chars")
print(f"   Total message length: {len(SYSTEM_PROMPT) + len(context) + len(query)} chars")

print(f"\n⏳ Sending to Ollama...")
try:
    r = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=180)
    r.raise_for_status()
    response = r.json()["message"]["content"].strip()
    print(f"\n✓ Ollama responded ({len(response)} chars):")
    print("-"*80)
    print(response)
    print("-"*80)
except Exception as e:
    print(f"✗ Error calling Ollama: {e}")
    sys.exit(1)

print("\n" + "="*80)
