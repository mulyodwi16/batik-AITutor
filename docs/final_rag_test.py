#!/usr/bin/env python3
"""COMPREHENSIVE FINAL TEST - All RAG Pipeline After Fixes"""
import json
import sys
sys.path.insert(0, '.')
from app import retrieve_topk, generate_rag_answer

test_queries = [
    ("Berapa banyak motif batik dari Jetis?", "COUNT - Should list all 6 Jetis motifs with exact count"),
    ("Sebutkan motif batik dari Surabaya", "ENUMERATE - Should list Surabaya motifs"),
    ("Apa perbedaan batik Jetis dan Surabaya?", "COMPARATIVE - Should compare both with specific motifs"),
]

print("\n" + "="*100)
print("FINAL RAG PIPELINE TEST - AFTER ALL FIXES")
print("="*100)

for query, description in test_queries:
    print(f"\n{'='*100}")
    print(f"QUERY: {query}")
    print(f"TEST: {description}")
    print(f"{'='*100}")
    
    # Get answer
    answer, ids, scores = generate_rag_answer(query)
    
    print(f"\nANSWER:\n{answer}")
    
    # Quality checks
    has_numbers = any(c.isdigit() for c in answer)
    has_specific_motifs = any(motif.lower() in answer.lower() for motif in [
        'alun-alun', 'burung merak', 'liris', 'love putihan', 'parang jabon', 'sekar jagad',
        'abhi boyo', 'gembili', 'kembang bungur', 'kintir kintiran', 'remo suroboyoan', 'sparkling'
    ])
    
    print(f"\nQUALITY:")
    print(f"  • Has numbers/counts: {has_numbers} {'✅' if has_numbers or 'perbedaan' in query.lower() else '⚠'}")
    print(f"  • Has specific motif names: {has_specific_motifs} {'✅' if has_specific_motifs else '❌'}")

print("\n" + "="*100)
print("TEST COMPLETE")
print("="*100 + "\n")
