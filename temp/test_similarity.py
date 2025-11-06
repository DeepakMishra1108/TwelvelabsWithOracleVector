#!/usr/bin/env python3
"""Test similarity scores for search queries"""
import sys
sys.path.insert(0, 'twelvelabvideoai/src')
from dotenv import load_dotenv
load_dotenv()
from search_flask_safe import search_photos_flask_safe

# Test search with "blue dress" query
print("="*70)
print("🔍 TESTING: Search for 'blue dress' (should have LOW similarity)")
print("="*70)
results = search_photos_flask_safe(query_text="blue dress", album_name="Isha", top_k=16)

print(f"\nTotal results: {len(results)}\n")

for i, result in enumerate(results, 1):
    similarity_pct = result['similarity'] * 100
    print(f"{i:2d}. {result['file_name'][:40]:40s} Similarity: {similarity_pct:5.2f}%")

print("\n" + "="*70)
print("🔍 TESTING: Search for 'black dress' (should have HIGH similarity)")
print("="*70)
results2 = search_photos_flask_safe(query_text="black dress", album_name="Isha", top_k=5)

for i, result in enumerate(results2, 1):
    similarity_pct = result['similarity'] * 100
    print(f"{i:2d}. {result['file_name'][:40]:40s} Similarity: {similarity_pct:5.2f}%")

print("\n" + "="*70)
print("📊 ANALYSIS:")
print("="*70)
print("If 'blue dress' results have similarity < 50%, we need a threshold filter")
print("Common thresholds: 0.5 (50%), 0.6 (60%), or 0.7 (70%)")
