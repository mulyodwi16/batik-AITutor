#!/usr/bin/env python3
import json
with open("artifacts/chunks.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Find Putat Jaya entries
print("Looking for Putat Jaya entries:")
found = False
for i, meta in enumerate(data.get("chunk_metadata", [])):
    if "putat" in meta.get("file", "").lower() or "putat" in meta.get("file_title", "").lower():
        found = True
        print(f"\n[Chunk {i}]")
        print(f"  File: {meta.get('file')}")
        print(f"  Title: {meta.get('file_title')}")
        print(f"  Location: {meta.get('location')}")
        print(f"  Category: {meta.get('category')}")
        print(f"  Subcategory: {meta.get('subcategory')}")
        print(f"  Chunk preview: {data['chunks'][i][:150]}...")

if not found:
    print("❌ Putat Jaya not found in metadata!")
    print("\nAll files that were processed:")
    files_seen = set()
    for meta in data.get("chunk_metadata", []):
        file = meta.get("file")
        if file and file not in files_seen:
            files_seen.add(file)
            print(f"  - {file}")
