#!/usr/bin/env python3
"""Debug script to check chunks and test retrieval"""
import json
import sys
import os

# Check chunks
print("\n" + "="*80)
print("📊 CHUNK ANALYSIS")
print("="*80)

with open('artifacts/chunks.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

chunks = data.get('chunks', [])
chunk_metadata = data.get('chunk_metadata', [])
metadata = data.get('metadata', {})

print(f"✓ Total chunks: {len(chunks)}")
print(f"✓ Metadata entries: {len(chunk_metadata)}")
print(f"✓ Artifacts version: {metadata.get('version', 'unknown')}")
print(f"✓ Total chars: {metadata.get('total_chars', 0)}")

# Show sample chunk
if chunks:
    print("\n" + "-"*80)
    print("📝 SAMPLE CHUNK #0:")
    print("-"*80)
    print(f"Text length: {len(chunks[0])} chars")
    print(f"Preview: {chunks[0][:300]}...")
    
if chunk_metadata:
    print("\n" + "-"*80)
    print("📋 SAMPLE METADATA #0:")
    print("-"*80)
    for key, val in list(chunk_metadata[0].items())[:8]:
        print(f"  {key}: {val}")

# Check FAISS index
print("\n" + "="*80)
print("🔍 FAISS INDEX")
print("="*80)
try:
    import faiss
    index = faiss.read_index('artifacts/faiss.index')
    print(f"✓ Index loaded: {index.ntotal} vectors")
    print(f"✓ Index dimension: {index.d}")
except Exception as e:
    print(f"✗ Error loading FAISS: {e}")

# Test embedder
print("\n" + "="*80)
print("🧠 EMBEDDER TEST")
print("="*80)
try:
    from sentence_transformers import SentenceTransformer
    embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
    test_query = "Apa itu Batik?"
    q_emb = embedder.encode([test_query], convert_to_numpy=True, normalize_embeddings=True)
    print(f"✓ Embedder loaded successfully")
    print(f"✓ Query embedding dimension: {q_emb.shape}")
except Exception as e:
    print(f"✗ Error loading embedder: {e}")

# Analyze locations in metadata
print("\n" + "="*80)
print("📍 LOCATION DISTRIBUTION")
print("="*80)
locations = {}
for meta in chunk_metadata:
    loc = meta.get('location', 'unknown')
    locations[loc] = locations.get(loc, 0) + 1

for loc, count in sorted(locations.items()):
    print(f"  {loc}: {count} chunks")

# Analyze categories
print("\n" + "="*80)
print("📂 CATEGORY DISTRIBUTION")
print("="*80)
categories = {}
subcategories = {}
for meta in chunk_metadata:
    cat = meta.get('category', 'unknown')
    subcat = meta.get('subcategory', 'unknown')
    categories[cat] = categories.get(cat, 0) + 1
    subcategories[subcat] = subcategories.get(subcat, 0) + 1

print("Categories:")
for cat, count in sorted(categories.items()):
    print(f"  {cat}: {count}")
print("Subcategories:")
for subcat, count in sorted(subcategories.items()):
    print(f"  {subcat}: {count}")

print("\n" + "="*80)
