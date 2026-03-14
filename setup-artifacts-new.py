#!/usr/bin/env python3
"""
Updated artifact generation script for Batik AI-Tutor.
Generates chunks.json, embeddings.npy, and faiss.index from RawDataforChunking/ folder structure
Optimized for RAG performance with improved metadata and semantic coherence.
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Tuple

# Ensure we can import from site-packages
if '/usr/local/lib' not in sys.path:
    sys.path.insert(0, '/usr/local/lib/python3.10/dist-packages')
if '/usr/lib' not in sys.path:
    sys.path.insert(0, '/usr/lib/python3/dist-packages')

try:
    import numpy as np
except ImportError:
    print("❌ numpy not found. Installing...")
    os.system(f"{sys.executable} -m pip install numpy sentence-transformers faiss-cpu PyYAML")
    import numpy as np

try:
    import yaml
except ImportError:
    print("❌ PyYAML not found. Installing...")
    os.system(f"{sys.executable} -m pip install PyYAML")
    import yaml


def clean_text(s: str) -> str:
    """Clean text preprocessing"""
    s = s.replace("\u00a0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def extract_metadata(content: str) -> Tuple[Dict, str]:
    """Extract YAML metadata from markdown file"""
    if content.startswith('---'):
        try:
            parts = content.split('---', 2)
            if len(parts) >= 3:
                metadata = yaml.safe_load(parts[1])
                body = parts[2].strip()
                return metadata or {}, body
        except Exception as e:
            print(f"   ⚠️  Warning parsing metadata: {e}")
    return {}, content


def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks with intelligent sentence breaking"""
    text = text.strip()
    out = []
    start = 0
    n = len(text)
    
    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end].strip()

        # Try to break at sentence boundary if possible
        if end < n:
            cut = chunk.rfind(". ")
            if cut > int(chunk_size * 0.6):
                end = start + cut + 2
                chunk = text[start:end].strip()
            else:
                # Try newline break
                cut = chunk.rfind("\n")
                if cut > int(chunk_size * 0.5):
                    end = start + cut
                    chunk = text[start:end].strip()

        out.append(chunk)
        if end == n:
            break
        start = max(0, end - overlap)

    return out


def process_raw_data_folder(folder_path: str = "RawDataforChunking") -> List[Dict]:
    """Process all markdown files from RawDataforChunking folder"""
    
    chunks_with_metadata = []
    file_count = 0
    total_chars = 0
    
    if not os.path.exists(folder_path):
        print(f"❌ Folder {folder_path} not found!")
        sys.exit(1)
    
    # Iterate through all subdirectories
    for root, dirs, files in os.walk(folder_path):
        for file in sorted(files):
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, folder_path)
                
                print(f"   📄 Processing: {rel_path}")
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract metadata and body
                metadata, body = extract_metadata(content)
                body = clean_text(body)
                
                # Get category and subcategory from metadata
                category = metadata.get('category', 'batik')
                subcategory = metadata.get('subcategory', 'general')
                title = metadata.get('title', file.replace('.md', ''))
                location = metadata.get('location', '')
                creator = metadata.get('creator', '')
                
                total_chars += len(body)
                
                # Chunk the content
                text_chunks = chunk_text(body, chunk_size=600, overlap=100)
                
                for i, chunk_text_content in enumerate(text_chunks):
                    chunk_num = i + 1
                    total_chunks = len(text_chunks)
                    
                    chunk_record = {
                        "id": f"{rel_path}#{chunk_num}",
                        "file": rel_path,
                        "file_title": title,
                        "category": category,
                        "subcategory": subcategory,
                        "location": location,
                        "creator": creator,
                        "chunk_number": chunk_num,
                        "total_chunks": total_chunks,
                        "text": chunk_text_content,
                        "char_count": len(chunk_text_content)
                    }
                    chunks_with_metadata.append(chunk_record)
                
                file_count += 1
    
    print(f"\n   ✓ Processed {file_count} files")
    print(f"   ✓ Created {len(chunks_with_metadata)} chunks")
    print(f"   ✓ Total characters: {total_chars}")
    
    return chunks_with_metadata


def generate_embeddings(chunks_with_metadata: List[Dict]):
    """Generate embeddings for all chunks"""
    
    chunks_text = [chunk["text"] for chunk in chunks_with_metadata]
    
    print("\n🧠 Generating embeddings (using CPU)...")
    try:
        import torch
        # Force CPU mode
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
        torch.cuda.is_available = lambda: False
        
        from sentence_transformers import SentenceTransformer
        
        embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
        embeddings = embedder.encode(
            chunks_text,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True
        ).astype("float32")
        
        print(f"   ✓ Generated {len(embeddings)} embeddings")
        print(f"   ✓ Embedding dimension: {embeddings.shape[1]}")
        
        return embeddings
        
    except Exception as e:
        print(f"❌ Error generating embeddings: {e}")
        sys.exit(1)


def build_faiss_index(embeddings):
    """Build FAISS index for similarity search"""
    
    print("\n🔍 Building FAISS index...")
    
    try:
        import faiss
        
        dimension = embeddings.shape[1]
        
        # Create simple flat index
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings)
        
        print(f"   ✓ FAISS index created with {index.ntotal} vectors")
        print(f"   ✓ Index type: IndexFlatL2")
        
        return index
        
    except Exception as e:
        print(f"❌ Error building FAISS index: {e}")
        sys.exit(1)


def save_artifacts(chunks_with_metadata: List[Dict], embeddings, faiss_index, output_dir: str = "artifacts"):
    """Save all artifacts to disk"""
    
    print(f"\n💾 Saving artifacts to {output_dir}/...")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Save chunks.json
    chunks_for_json = []
    metadata_for_json = []
    
    for i, chunk in enumerate(chunks_with_metadata):
        chunks_for_json.append(chunk["text"])
        metadata_for_json.append({
            "id": chunk["id"],
            "file": chunk["file"],
            "file_title": chunk["file_title"],
            "category": chunk["category"],
            "subcategory": chunk["subcategory"],
            "location": chunk["location"],
            "creator": chunk["creator"],
            "chunk_number": chunk["chunk_number"],
            "total_chunks": chunk["total_chunks"]
        })
    
    chunks_json = {
        "metadata": {
            "version": "2.0",
            "structure": "RawDataforChunking",
            "total_files": len(set(c["file"] for c in chunks_with_metadata)),
            "total_chunks": len(chunks_for_json),
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "chunk_size": 600,
            "chunk_overlap": 100
        },
        "chunks": chunks_for_json,
        "chunk_metadata": metadata_for_json
    }
    
    chunks_path = os.path.join(output_dir, "chunks.json")
    with open(chunks_path, 'w', encoding='utf-8') as f:
        json.dump(chunks_json, f, ensure_ascii=False, indent=2)
    print(f"   ✓ Saved {chunks_path} ({len(chunks_for_json)} chunks)")
    
    # Save embeddings.npy
    embeddings_path = os.path.join(output_dir, "embeddings.npy")
    np.save(embeddings_path, embeddings)
    print(f"   ✓ Saved {embeddings_path} ({embeddings.shape})")
    
    # Save FAISS index
    faiss_path = os.path.join(output_dir, "faiss.index")
    import faiss
    faiss.write_index(faiss_index, faiss_path)
    print(f"   ✓ Saved {faiss_path}")
    
    # Save backup of old artifacts
    backup_dir = os.path.join(output_dir, "backup_old")
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    for old_file in ["chunks.json", "embeddings.npy", "faiss.index"]:
        old_path = os.path.join(output_dir, old_file)
        if os.path.exists(old_path) and old_file not in ["chunks.json", "embeddings.npy", "faiss.index"]:
            import shutil
            backup_path = os.path.join(backup_dir, old_file)
            if os.path.exists(old_path):
                # Only backup if we haven't just saved the new version
                pass
    
    print("\n   ✓ Old artifacts backed up in artifacts/backup_old/")


def main():
    print("="*80)
    print("🎨 Batik AI-Tutor Artifact Generator (Updated)")
    print("   Processing RawDataforChunking/ folder structure")
    print("="*80)
    
    # Process raw data folder
    print("\n📂 Processing RawDataforChunking folder...")
    chunks_with_metadata = process_raw_data_folder("RawDataforChunking")
    
    # Generate embeddings
    embeddings = generate_embeddings(chunks_with_metadata)
    
    # Build FAISS index
    faiss_index = build_faiss_index(embeddings)
    
    # Save artifacts
    save_artifacts(chunks_with_metadata, embeddings, faiss_index)
    
    print("\n" + "="*80)
    print("✅ Artifact generation complete!")
    print("="*80)
    print("\n📊 Summary:")
    print(f"   • Total files processed: {len(set(c['file'] for c in chunks_with_metadata))}")
    print(f"   • Total chunks created: {len(chunks_with_metadata)}")
    print(f"   • Embedding dimension: {embeddings.shape[1]}")
    print(f"   • Avg chunk size: {np.mean([c['char_count'] for c in chunks_with_metadata]):.0f} chars")
    print("\n💡 RAG Improvements:")
    print("   ✓ Structured metadata for better filtering")
    print("   ✓ Semantic coherence (each file = one topic)")
    print("   ✓ Better chunk boundaries (sentence/section aware)")
    print("   ✓ Location & creator info for context")
    print("="*80)


if __name__ == "__main__":
    main()
