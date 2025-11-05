#!/usr/bin/env python3
"""Test updated search with similarity threshold"""
import sys
sys.path.insert(0, 'twelvelabvideoai/src')
from dotenv import load_dotenv
load_dotenv()
from search_flask_safe import search_photos_flask_safe

print("="*70)
print("🎯 TEST 1: Search 'blue dress' with DEFAULT threshold (30%)")
print("="*70)
results = search_photos_flask_safe(query_text="blue dress", album_name="Isha", top_k=16, min_similarity=0.30)

print(f"Results returned: {len(results)}")
for i, result in enumerate(results[:5], 1):
    similarity_pct = result['similarity'] * 100
    print(f"  {i}. {result['file_name'][:40]:40s} {similarity_pct:5.2f}%")

print("\n" + "="*70)
print("🎯 TEST 2: Search 'blue dress' with STRICT threshold (35%)")
print("="*70)
results2 = search_photos_flask_safe(query_text="blue dress", album_name="Isha", top_k=16, min_similarity=0.35)

print(f"Results returned: {len(results2)}")
for i, result in enumerate(results2[:5], 1):
    similarity_pct = result['similarity'] * 100
    print(f"  {i}. {result['file_name'][:40]:40s} {similarity_pct:5.2f}%")

print("\n" + "="*70)
print("🎯 TEST 3: Search 'black dress' with DEFAULT threshold (30%)")
print("="*70)
results3 = search_photos_flask_safe(query_text="black dress", album_name="Isha", top_k=10, min_similarity=0.30)

print(f"Results returned: {len(results3)}")
for i, result in enumerate(results3[:5], 1):
    similarity_pct = result['similarity'] * 100
    print(f"  {i}. {result['file_name'][:40]:40s} {similarity_pct:5.2f}%")

print("\n" + "="*70)
print("✅ SUMMARY:")
print("="*70)
print(f"• 'blue dress' with 30% threshold: {len(results)} results (low matches)")
print(f"• 'blue dress' with 35% threshold: {len(results2)} results (NO results expected)")
print(f"• 'black dress' with 30% threshold: {len(results3)} results (better matches)")
print("\n💡 The 30% threshold filters out poor matches while keeping relevant ones")
