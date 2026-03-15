#!/usr/bin/env python3
"""Test RAG pipeline WITH COMPARATIVE QUERY debugging"""
import json
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test dengan app.py langsung (import dari situ)
print("\n" + "="*80)
print("TESTING RAG WITH APP.PY (COMPARATIVE QUERY)")
print("="*80)

# Load artifacts
with open('artifacts/chunks.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

chunks = data.get('chunks', [])
chunk_metadata = data.get('chunk_metadata', [])
print(f"\nLoaded {len(chunks)} chunks")

# Import dari app.py
import sys
sys.path.insert(0, '.')
from app import retrieve_topk, generate_rag_answer, _SYSTEM_PROMPT

# Test comparative query
query_comp = "Apa perbedaan batik Jetis dan Surabaya?"
print(f"\n{'='*80}")
print(f"TEST QUERY: {query_comp}")
print(f"{'='*80}")

# 1. Test retrieval
print("\n1️⃣ RETRIEVAL PHASE:")
ids, scores = retrieve_topk(query_comp, k=25)
print(f"   Retrieved {len(ids)} chunks")

# Analyze
jetis = sum(1 for cid in ids if chunk_metadata[cid].get('location', '').lower().__contains__('jetis'))
surabaya = sum(1 for cid in ids if chunk_metadata[cid].get('location', '').lower().__contains__('surabaya'))
print(f"   Breakdown: {jetis} Jetis + {surabaya} Surabaya")

# 2. Check context building
print("\n2️⃣ CONTEXT BUILDING:")
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
print(f"   Using {len(parts)}/{len(ids)} chunks ({len(context)} chars)")

# Sample context
print(f"\n   📝 SAMPLE CONTEXT (first 500 chars):")
print("   " + context[:500].replace('\n', '\n   ') + "...")

# 3. Test LLM generation
print("\n3️⃣ LLM GENERATION PHASE:")
print("   Calling Ollama qwen2.5:14b...")

try:
    OLLAMA_BASE_URL = "http://localhost:11434"
    OLLAMA_MODEL = "qwen2.5:14b"
    
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {query_comp}"
            },
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
    
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json=payload,
        timeout=180
    )
    response.raise_for_status()
    
    answer = response.json()["message"]["content"].strip()
    print(f"   ✓ Got response ({len(answer)} chars)")
    print(f"\n   📢 OLLAMA ANSWER:")
    print("   " + answer.replace('\n', '\n   '))
    
    # Analyze answer quality
    print(f"\n4️⃣ ANSWER QUALITY CHECK:")
    has_jetis = 'jetis' in answer.lower()
    has_surabaya = 'surabaya' in answer.lower()
    has_motif_names = any(name.lower() in answer.lower() for name in [
        'alun-alun contong', 'burung merak', 'liris', 'love putihan', 'parang jabon', 'sekar jagad',
        'abhi boyo', 'gembili', 'kembang bungur', 'kintir kintiran', 'remo suroboyoan', 'sparkling'
    ])
    
    print(f"   ✓ Mentions Jetis: {has_jetis}")
    print(f"   ✓ Mentions Surabaya: {has_surabaya}")
    print(f"   ✓ Mentions specific motif names: {has_motif_names}")
    
    if has_jetis and has_surabaya and has_motif_names:
        print(f"   ✅ GOOD: Answer is comparative and specific!")
    elif has_jetis and has_surabaya:
        print(f"   ⚠️  PARTIAL: Mentions both but lacks specific motif names")
    elif has_jetis or has_surabaya:
        print(f"   ❌ BAD: Mentions only one location (not comparative)")
    else:
        print(f"   ❌ VERY BAD: Generic answer, doesn't follow context")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Also test a simple Jetis query
print(f"\n\n{'='*80}")
print("TEST QUERY #2: Berapa banyak motif dari Jetis?")
print(f"{'='*80}")

query_single = "Berapa banyak motif batik dari Jetis?"
ids2, scores2 = retrieve_topk(query_single, k=25)
jetis2 = sum(1 for cid in ids2 if chunk_metadata[cid].get('location', '').lower().__contains__('jetis'))
surabaya2 = sum(1 for cid in ids2 if chunk_metadata[cid].get('location', '').lower().__contains__('surabaya'))
print(f"Retrieved {len(ids2)} chunks: {jetis2} Jetis + {surabaya2} Surabaya")

if surabaya2 > 0:
    print(f"⚠️  WARNING: Query is for Jetis only, but got {surabaya2} Surabaya chunks!")

print("\n" + "="*80)
