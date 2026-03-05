#!/usr/bin/env python3
"""
Quick artifact generation script for Batik AI-Tutor.
Generates chunks.json, embeddings.npy, and faiss.index from learn-batikindonesia.md
"""

import os
import sys
import json
import re

# Ensure we can import from site-packages
if '/usr/local/lib' not in sys.path:
    sys.path.insert(0, '/usr/local/lib/python3.10/dist-packages')
if '/usr/lib' not in sys.path:
    sys.path.insert(0, '/usr/lib/python3/dist-packages')

try:
    import numpy as np
except ImportError:
    print("❌ numpy not found. Installing...")
    os.system(f"{sys.executable} -m pip install numpy sentence-transformers faiss-cpu")
    import numpy as np

def clean_text(s: str) -> str:
    """Clean text preprocessing"""
    s = s.replace("\u00a0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list:
    """Split text into overlapping chunks"""
    text = text.strip()
    out = []
    start = 0
    n = len(text)
    
    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end].strip()

        if end < n:
            cut = chunk.rfind(". ")
            if cut > int(chunk_size * 0.6):
                end = start + cut + 1
                chunk = text[start:end].strip()

        out.append(chunk)
        if end == n:
            break
        start = max(0, end - overlap)

    return out

def main():
    print("="*80)
    print("🎨 Batik AI-Tutor Artifact Generator")
    print("="*80)
    
    # Load markdown file
    md_file = "learn-batikindonesia.md"
    if not os.path.exists(md_file):
        print(f"❌ File {md_file} not found!")
        print("   Make sure to run this script from the project directory.")
        sys.exit(1)
    
    print(f"\n📖 Loading {md_file}...")
    with open(md_file, "r", encoding="utf-8") as f:
        raw = f.read()
    
    print(f"   ✓ Loaded {len(raw)} characters")
    
    # Clean text
    print("\n🧹 Cleaning text...")
    text = clean_text(raw)
    print(f"   ✓ Cleaned to {len(text)} characters")
    
    # Chunk text
    print("\n✂️  Chunking text...")
    chunks = chunk_text(text, chunk_size=800, overlap=150)
    print(f"   ✓ Created {len(chunks)} chunks")
    
    # Generate embeddings
    print("\n🧠 Generating embeddings...")
    try:
        from sentence_transformers import SentenceTransformer
        
        embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        embeddings = embedder.encode(
            chunks,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True
        ).astype("float32")
        print(f"   ✓ Generated embeddings: {embeddings.shape}")
    except ImportError:
        print("   ❌ sentence-transformers not found. Installing...")
        os.system(f"{sys.executable} -m pip install sentence-transformers")
        from sentence_transformers import SentenceTransformer
        embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        embeddings = embedder.encode(
            chunks,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True
        ).astype("float32")
        print(f"   ✓ Generated embeddings: {embeddings.shape}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        sys.exit(1)
    
    # Build FAISS index
    print("\n🔍 Building FAISS index...")
    try:
        import faiss
        
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        print(f"   ✓ FAISS index with {index.ntotal} vectors")
    except ImportError:
        print("   ❌ faiss-cpu not found. Installing...")
        os.system(f"{sys.executable} -m pip install faiss-cpu")
        import faiss
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        print(f"   ✓ FAISS index with {index.ntotal} vectors")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        sys.exit(1)
    
    # Save artifacts
    print("\n💾 Saving artifacts...")
    os.makedirs("artifacts", exist_ok=True)
    
    # Save chunks
    chunks_file = "artifacts/chunks.json"
    with open(chunks_file, "w", encoding="utf-8") as f:
        json.dump({"chunks": chunks}, f, ensure_ascii=False, indent=2)
    print(f"   ✓ {chunks_file} ({len(chunks)} chunks)")
    
    # Save embeddings
    emb_file = "artifacts/embeddings.npy"
    np.save(emb_file, embeddings)
    print(f"   ✓ {emb_file} ({embeddings.shape})")
    
    # Save FAISS index
    index_file = "artifacts/faiss.index"
    faiss.write_index(index, index_file)
    print(f"   ✓ {index_file}")
    
    print("\n" + "="*80)
    print("✅ ARTIFACT GENERATION COMPLETE!")
    print("="*80)
    print("\nYou can now run the chatbot:")
    print("  docker-compose up --build")
    print("\nOr locally:")
    print("  python app.py")
    print("="*80)

if __name__ == "__main__":
    main()
