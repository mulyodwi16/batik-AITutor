#!/usr/bin/env python3
"""Test location detection"""

def _detect_locations(query: str):
    """From app.py"""
    locs = []
    q = query.lower()
    
    # Check for Surabaya (first, but don't return early)
    if any(w in q for w in ['surabaya', 'putat jaya', 'wonokromo', 'gembili', 'gadung', 'bendul merisi']):
        locs.append('surabaya')
    
    # Check for Jetis (second, so both can be detected)
    if any(w in q for w in ['jetis', 'sidoarjo', 'kampung batik jetis']):
        locs.append('jetis')
    
    return locs

# Test cases
test_queries = [
    "Berapa banyak motif batik dari Jetis?",
    "Sebutkan semua motif batik dari Surabaya",
    "Apa perbedaan batik Jetis dan Surabaya?",
    "Apa itu Batik?",
]

print("\n" + "="*80)
print("LOCATION DETECTION TEST")
print("="*80)

for query in test_queries:
    result = _detect_locations(query)
    print(f"\nQuery: {query}")
    print(f"Detected: {result}")
    
    # Check filtering logic
    if len(result) == 0:
        print("  → No location filter (all chunks)")
    elif len(result) == 1:
        print(f"  → Single-location filter: {result[0]}")
    else:
        print(f"  → Comparative query: {' + '.join(result)}")
