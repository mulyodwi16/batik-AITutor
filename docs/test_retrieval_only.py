#!/usr/bin/env python3
"""Test the retrieval and context building part of RAG (without LLM)"""
import json
import os

# Load artifacts
print("\n" + "="*80)
print("🔍 TESTING RETRIEVAL & CONTEXT BUILDING")
print("="*80)

with open('artifacts/chunks.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

chunks = data.get('chunks', [])
chunk_metadata = data.get('chunk_metadata', [])
print(f"✓ Loaded {len(chunks)} chunks with metadata")

# Load embedder
from sentence_transformers import SentenceTransformer
import faiss

embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
faiss_index = faiss.read_index('artifacts/faiss.index')
print(f"✓ Embedder and FAISS loaded\n")

# Test queries designed to reveal issues
test_cases = [
    {
        "query": "Berapa banyak motif batik dari Jetis?",
        "expected": "Should list all 'Jetis' motifs from metadata"
    },
    {
        "query": "Sebutkan semua motif batik dari Surabaya",
        "expected": "Should list all 'Surabaya' motifs from metadata"
    },
    {
        "query": "Apa perbedaan batik Jetis dan Surabaya?",
        "expected": "Should retrieve chunks from BOTH locations"
    },
    {
        "query": "Apa itu Batik?",
        "expected": "Should retrieve general batik information first"
    },
]

def _detect_location(query):
    q = query.lower()
    if any(w in q for w in ['surabaya', 'putat jaya', 'wonokromo']):
        return 'surabaya'
    if any(w in q for w in ['jetis', 'sidoarjo', 'kampung batik jetis']):
        return 'jetis'
    return None

def _build_chunk_locations_from_metadata(metadata_list):
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
            print(f"   📍 Location filter applied: '{loc}' → {len(id_list)} chunks (filtered {len(ids)-len(id_list)})")

        return id_list, score_list
    except Exception as e:
        print(f"Error in retrieve_topk: {e}")
        return [], []

# Run tests
for test_case in test_cases:
    query = test_case["query"]
    expected = test_case["expected"]
    
    print("=" * 80)
    print(f"❓ Query: {query}")
    print(f"📌 Expected behavior: {expected}")
    print("-" * 80)
    
    ids, scores = retrieve_topk(query)
    
    # Analyze retrieved chunks
    jetis_count = 0
    surabaya_count = 0
    other_count = 0
    motif_titles = []
    
    print(f"\n📊 Retrieved {len(ids)} chunks:")
    for i, (cid, score) in enumerate(list(zip(ids, scores))[:10]):
        meta = chunk_metadata[cid]
        location = meta.get('location', '')
        title = meta.get('file_title', 'N/A')
        subcat = meta.get('subcategory', '')
        
        # Categorize
        if 'jetis' in location.lower() or 'sidoarjo' in location.lower():
            jetis_count += 1
            loc_label = "🔵 JETIS"
        elif 'surabaya' in location.lower():
            surabaya_count += 1
            loc_label = "🟢 SURABAYA"
        else:
            other_count += 1
            loc_label = "⚪ OTHER"
        
        if subcat == 'motif':
            motif_titles.append(title)
        
        print(f"   [{i+1}] {loc_label} | Score: {score:.4f} | {title[:50]}")
    
    print(f"\n📈 Analysis:")
    print(f"   Jetis chunks:     {jetis_count}")
    print(f"   Surabaya chunks:  {surabaya_count}")
    print(f"   Other chunks:     {other_count}")
    print(f"   Motif titles:     {len(motif_titles)}")
    
    # Build context
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
    
    print(f"\n📝 Context building:")
    print(f"   Chunks used:  {len(parts)}/{len(ids)}")
    print(f"   Context size: {len(context)} chars")
    
    # Check if context is good
    if "motif" not in context.lower():
        print(f"   ⚠️  WARNING: Context doesn't contain 'motif' keyword!")
    if len(context) < 1000:
        print(f"   ⚠️  WARNING: Context is quite small ({len(context)} chars)")
    
    print()

# Additional analysis
print("=" * 80)
print("📊 METADATA ANALYSIS - MOTIF DISTRIBUTION")
print("=" * 80)

jetis_motifs = []
surabaya_motifs = []

for meta in chunk_metadata:
    if meta.get('subcategory') == 'motif':
        title = meta.get('file_title', '')
        location = meta.get('location', '')
        if 'jetis' in location.lower() or 'sidoarjo' in location.lower():
            jetis_motifs.append(title)
        elif 'surabaya' in location.lower():
            surabaya_motifs.append(title)

print(f"\n🔵 JETIS MOTIFS ({len(jetis_motifs)}):")
for motif in sorted(set(jetis_motifs)):
    count = jetis_motifs.count(motif)
    print(f"   • {motif} ({count} chunk{'s' if count > 1 else ''})")

print(f"\n🟢 SURABAYA MOTIFS ({len(surabaya_motifs)}):")
for motif in sorted(set(surabaya_motifs)):
    count = surabaya_motifs.count(motif)
    print(f"   • {motif} ({count} chunk{'s' if count > 1 else ''})")

print("\n" + "=" * 80)
