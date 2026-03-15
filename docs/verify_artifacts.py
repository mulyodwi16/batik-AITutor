#!/usr/bin/env python3
"""Verify new artifacts with Putat Jaya"""
import json

with open('artifacts/chunks.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('✅ NEW ARTIFACTS LOADED SUCCESSFULLY')
print(f'Total chunks: {len(data.get("chunks", []))}')
print(f'Metadata entries: {len(data.get("chunk_metadata", []))}')

# Count by location
locations = {}
motifs_per_loc = {}
villages_per_loc = {}

for meta in data.get('chunk_metadata', []):
    loc = meta.get('location', 'unknown')
    subcat = meta.get('subcategory', '')
    locations[loc] = locations.get(loc, 0) + 1
    
    if subcat == 'motif':
        if loc not in motifs_per_loc:
            motifs_per_loc[loc] = set()
        motifs_per_loc[loc].add(meta['file_title'])
    elif subcat == 'village':
        if loc not in villages_per_loc:
            villages_per_loc[loc] = set()
        villages_per_loc[loc].add(meta['file_title'])

print()
print('📍 LOCATIONS & DISTRIBUTION:')
for loc in sorted(locations.keys()):
    print(f'  {loc}: {locations[loc]} chunks')

print()
print('🎨 MOTIF COUNT BY LOCATION:')
total_motifs = 0
for loc in sorted(motifs_per_loc.keys()):
    count = len(motifs_per_loc[loc])
    total_motifs += count
    print(f'  {loc}: {count} motif')

print()
print('🏘️ VILLAGES BY LOCATION:')
for loc in sorted(villages_per_loc.keys()):
    villages = villages_per_loc[loc]
    print(f'  {loc}:')
    for v in sorted(villages):
        print(f'    - {v}')

print()
print(f'📊 TOTAL: {total_motifs} motif')
