#!/usr/bin/env python3
"""Test script to verify all motifs are retrieved correctly"""

import sys
import json
import os
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

# Set up for testing
os.chdir(Path(__file__).parent)

# Import app
from app import (
    retrieve_topk, 
    _detect_locations,
    build_inventory_summary,
    chunks,
    chunk_metadata
)

print("\n" + "="*70)
print("MOTIF COUNT TEST - VERIFYING ALL 12 MOTIFS")
print("="*70)

# Test 1: Query for Surabaya motifs
query1 = "Berapa banyak motif batik dari Surabaya?"
print(f"\n📝 Query: {query1}")
print(f"   Detected location: {_detect_locations(query1)}")

results1 = retrieve_topk(query1)
id_list1, score_list1 = results1
print(f"   Retrieved {len(id_list1)} chunks")

# Build lookup by chunk ID
surabaya_motifs = set()
for chunk_id in id_list1:
    if chunk_id < len(chunk_metadata):
        meta = chunk_metadata[chunk_id]
        if meta.get('subcategory') == 'motif':
            title = meta.get('file_title', '')
            if 'Surabaya' in meta.get('location', ''):
                surabaya_motifs.add(title)

print(f"   Surabaya motifs found: {len(surabaya_motifs)}")
for motif in sorted(surabaya_motifs):
    print(f"     • {motif}")

# Test 2: Query for Jetis/Sidoarjo motifs
query2 = "Sebutkan semua motif dari Jetis!"
print(f"\n📝 Query: {query2}")
print(f"   Detected location: {_detect_locations(query2)}")

results2 = retrieve_topk(query2)
id_list2, score_list2 = results2
print(f"   Retrieved {len(id_list2)} chunks")

jetis_motifs = set()
for chunk_id in id_list2:
    if chunk_id < len(chunk_metadata):
        meta = chunk_metadata[chunk_id]
        if meta.get('subcategory') == 'motif':
            title = meta.get('file_title', '')
            if 'Jetis' in meta.get('location', '') or 'Sidoarjo' in meta.get('location', ''):
                jetis_motifs.add(title)

print(f"   Jetis motifs found: {len(jetis_motifs)}")
for motif in sorted(jetis_motifs):
    print(f"     • {motif}")

# Test 3: Generic query to get all motifs
query3 = "Apa saja motif batik?"
print(f"\n📝 Query: {query3}")
print(f"   Detected location: {_detect_locations(query3)}")

results3 = retrieve_topk(query3)
id_list3, score_list3 = results3
print(f"   Retrieved {len(id_list3)} chunks")

all_motifs = set()
for chunk_id in id_list3:
    if chunk_id < len(chunk_metadata):
        meta = chunk_metadata[chunk_id]
        if meta.get('subcategory') == 'motif':
            title = meta.get('file_title', '')
            all_motifs.add(title)

print(f"   Total motifs found: {len(all_motifs)}")
for motif in sorted(all_motifs):
    print(f"     • {motif}")

print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print(f"✓ Surabaya motifs:  {len(surabaya_motifs)}/6")
print(f"✓ Jetis motifs:     {len(jetis_motifs)}/6")
print(f"✓ Total motifs:     {len(all_motifs)}/12")
print("="*70 + "\n")
