#!/usr/bin/env python3
"""Test script for photo album feature with TwelveLabs Marengo embeddings

This script demonstrates the complete workflow:
1. Create photo_embeddings table in Oracle
2. Upload sample photos to albums
3. Create embeddings using Marengo model
4. Search photos
5. Perform unified search across photos and videos

Usage:
    python scripts/test_photo_albums.py
"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'twelvelabvideoai', 'src'))

from dotenv import load_dotenv
load_dotenv()


def test_schema_creation():
    """Test 1: Create photo_embeddings table"""
    print("\n" + "="*60)
    print("TEST 1: Creating photo_embeddings table schema")
    print("="*60)
    
    try:
        from create_schema_photo_embeddings import create_photo_embeddings_table
        create_photo_embeddings_table()
        print("✓ Schema creation successful")
        return True
    except Exception as e:
        print(f"✗ Schema creation failed: {e}")
        return False


def test_photo_embedding_creation():
    """Test 2: Create embeddings for sample photos"""
    print("\n" + "="*60)
    print("TEST 2: Creating photo embeddings")
    print("="*60)
    
    # You'll need to provide actual photo URLs or paths
    sample_photos = [
        # Replace with real photo URLs from OCI or web
        # "https://example.com/sunset.jpg",
        # "https://example.com/beach.jpg",
    ]
    
    if not sample_photos:
        print("⚠ No sample photos configured. Skipping this test.")
        print("  To test, add photo URLs to this script.")
        return None
    
    try:
        from store_photo_embeddings import create_photo_embeddings_for_album
        
        album_name = "test_album"
        print(f"Creating embeddings for album: {album_name}")
        print(f"Photos: {len(sample_photos)}")
        
        results = create_photo_embeddings_for_album(album_name, sample_photos)
        
        print(f"\nResults:")
        print(f"  Success: {results['success']}")
        print(f"  Failed: {results['failed']}")
        
        if results['errors']:
            print(f"  Errors:")
            for err in results['errors']:
                print(f"    - {err}")
        
        if results['success'] > 0:
            print("✓ Photo embedding creation successful")
            return True
        else:
            print("✗ No embeddings were created")
            return False
            
    except Exception as e:
        print(f"✗ Photo embedding creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_photo_search():
    """Test 3: Search photos using text query"""
    print("\n" + "="*60)
    print("TEST 3: Searching photos")
    print("="*60)
    
    try:
        from query_photo_embeddings import search_photos
        
        query = "sunset"
        print(f"Query: '{query}'")
        
        results = search_photos(query, top_k=5)
        
        print(f"\nFound {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result['photo_file']}")
            print(f"   Album: {result['album_name']}")
            print(f"   Similarity: {result['similarity_score']:.4f}")
        
        if len(results) > 0:
            print("\n✓ Photo search successful")
            return True
        else:
            print("\n⚠ No results found (may be expected if no photos in DB)")
            return None
            
    except Exception as e:
        print(f"✗ Photo search failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_unified_search():
    """Test 4: Unified search across photos and videos"""
    print("\n" + "="*60)
    print("TEST 4: Unified search (photos + videos)")
    print("="*60)
    
    try:
        from unified_search import unified_search, format_unified_results
        
        queries = ["inspection", "tower"]
        print(f"Queries: {queries}")
        
        results = unified_search(queries, top_k_photos=3, top_k_videos=3)
        
        print(format_unified_results(results))
        
        total_results = sum(s['total_count'] for s in results['summary'].values())
        
        if total_results > 0:
            print("\n✓ Unified search successful")
            return True
        else:
            print("\n⚠ No results found (may be expected if DB is empty)")
            return None
            
    except Exception as e:
        print(f"✗ Unified search failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def print_summary(results):
    """Print test summary"""
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    total = len(results)
    passed = sum(1 for r in results if r is True)
    failed = sum(1 for r in results if r is False)
    skipped = sum(1 for r in results if r is None)
    
    print(f"Total tests: {total}")
    print(f"Passed: {passed} ✓")
    print(f"Failed: {failed} ✗")
    print(f"Skipped: {skipped} ⚠")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠ {failed} test(s) failed")


def main():
    print("TwelveLabs Photo Album Feature Test Suite")
    print("==========================================")
    
    # Check prerequisites
    if not os.getenv('TWELVE_LABS_API_KEY'):
        print("✗ TWELVE_LABS_API_KEY not set in environment")
        sys.exit(1)
    
    if not os.getenv('ORACLE_DB_USERNAME'):
        print("✗ Oracle DB credentials not set")
        sys.exit(1)
    
    print("✓ Environment configured")
    
    # Run tests
    results = []
    
    results.append(test_schema_creation())
    results.append(test_photo_embedding_creation())
    results.append(test_photo_search())
    results.append(test_unified_search())
    
    print_summary(results)


if __name__ == '__main__':
    main()
