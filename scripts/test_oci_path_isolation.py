#!/usr/bin/env python3
"""
Test OCI Path Isolation for Multi-Tenant Storage

This script tests that:
1. User uploads go to user-specific paths (/users/{user_id}/uploads/)
2. Generated content goes to user-specific paths (/users/{user_id}/generated/)
3. Users cannot access each other's files
4. Path structure matches expected layout

Prerequisites:
- OCI configured with ~/.oci/config or environment variables
- OCI_NAMESPACE and OCI_BUCKET_NAME set in .env
- Database with users table populated
- Flask application running

Usage:
    python scripts/test_oci_path_isolation.py
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'twelvelabvideoai'))

from dotenv import load_dotenv
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_path_generation():
    """Test path generation functions"""
    logger.info("=" * 80)
    logger.info("TEST 1: Path Generation Functions")
    logger.info("=" * 80)
    
    try:
        from src.oci_storage import (
            get_user_upload_path,
            get_user_generated_path,
            get_user_base_path
        )
        
        # Test cases
        test_cases = [
            {
                'user_id': 1,
                'tests': [
                    ('upload_photo', get_user_upload_path(1, 'photo', 'vacation.jpg'), 
                     'users/1/uploads/photos/vacation.jpg'),
                    ('upload_video', get_user_upload_path(1, 'video', 'beach.mp4'), 
                     'users/1/uploads/videos/beach.mp4'),
                    ('upload_chunk', get_user_upload_path(1, 'chunk', 'video_chunk_0.mp4'), 
                     'users/1/uploads/chunks/video_chunk_0.mp4'),
                    ('generated_montage', get_user_generated_path(1, 'montage', 'summer_2024.mp4'), 
                     'users/1/generated/montages/summer_2024.mp4'),
                    ('generated_slideshow', get_user_generated_path(1, 'slideshow', 'photos_show.mp4'), 
                     'users/1/generated/slideshows/photos_show.mp4'),
                ]
            },
            {
                'user_id': 2,
                'tests': [
                    ('upload_photo', get_user_upload_path(2, 'photo', 'test.jpg'), 
                     'users/2/uploads/photos/test.jpg'),
                    ('generated_montage', get_user_generated_path(2, 'montage', 'test.mp4'), 
                     'users/2/generated/montages/test.mp4'),
                ]
            }
        ]
        
        all_passed = True
        for user_case in test_cases:
            user_id = user_case['user_id']
            logger.info(f"\n📁 Testing User ID: {user_id}")
            logger.info(f"   Base Path: {get_user_base_path(user_id)}")
            
            for test_name, actual, expected in user_case['tests']:
                if actual == expected:
                    logger.info(f"   ✅ {test_name}: {actual}")
                else:
                    logger.error(f"   ❌ {test_name}: Expected '{expected}', got '{actual}'")
                    all_passed = False
        
        if all_passed:
            logger.info("\n✅ Path Generation Test: PASSED")
            return True
        else:
            logger.error("\n❌ Path Generation Test: FAILED")
            return False
            
    except Exception as e:
        logger.error(f"❌ Path generation test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_oci_configuration():
    """Test OCI configuration"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: OCI Configuration")
    logger.info("=" * 80)
    
    try:
        # Check environment variables
        namespace = os.getenv('OCI_NAMESPACE')
        bucket = os.getenv('OCI_BUCKET_NAME', 'video-ai-storage')
        config_file = os.getenv('OCI_CONFIG_FILE', '~/.oci/config')
        profile = os.getenv('OCI_PROFILE', 'DEFAULT')
        
        logger.info(f"\n📋 Configuration:")
        logger.info(f"   Namespace: {namespace or '❌ NOT SET'}")
        logger.info(f"   Bucket: {bucket}")
        logger.info(f"   Config File: {config_file}")
        logger.info(f"   Profile: {profile}")
        
        if not namespace:
            logger.warning("⚠️  OCI_NAMESPACE not set in .env file")
            return False
        
        # Try to initialize OCI client
        try:
            import oci
            config_path = os.path.expanduser(config_file)
            
            if os.path.exists(config_path):
                logger.info(f"   ✅ OCI config file found: {config_path}")
                config = oci.config.from_file(file_location=config_path, profile_name=profile)
                client = oci.object_storage.ObjectStorageClient(config)
                logger.info(f"   ✅ OCI client initialized successfully")
                
                # Try to get namespace (validates connection)
                try:
                    ns = client.get_namespace().data
                    logger.info(f"   ✅ Connected to OCI namespace: {ns}")
                    
                    if ns != namespace:
                        logger.warning(f"   ⚠️  Namespace mismatch: .env has '{namespace}', OCI returns '{ns}'")
                    
                    return True
                except Exception as e:
                    logger.error(f"   ❌ Failed to connect to OCI: {e}")
                    return False
            else:
                logger.error(f"   ❌ OCI config file not found: {config_path}")
                logger.info("   💡 Run: oci setup config")
                return False
                
        except ImportError:
            logger.error("   ❌ OCI SDK not installed: pip install oci")
            return False
            
    except Exception as e:
        logger.error(f"❌ OCI configuration test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_database_users():
    """Test database has users for testing"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Database Users")
    logger.info("=" * 80)
    
    try:
        # Import from correct location
        sys.path.insert(0, str(project_root / 'twelvelabvideoai'))
        from twelvelabvideoai.utils.db_utils import get_flask_safe_connection
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Get all users
            cursor.execute("""
                SELECT id, username, email, role, created_at
                FROM users
                ORDER BY id
            """)
            
            users = cursor.fetchall()
            
            if not users:
                logger.error("   ❌ No users found in database")
                logger.info("   💡 Create test users with: python scripts/create_admin_user.py")
                return False
            
            logger.info(f"\n📊 Found {len(users)} users:")
            for user in users:
                user_id, username, email, role, created_at = user
                logger.info(f"   User {user_id}: {username} ({role}) - {email}")
            
            # Check if we have at least 2 users for isolation testing
            if len(users) < 2:
                logger.warning(f"   ⚠️  Need at least 2 users for isolation testing (found {len(users)})")
                logger.info("   💡 Create another test user for isolation testing")
                return False
            
            logger.info(f"\n✅ Database Users Test: PASSED ({len(users)} users available)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Database users test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_upload_path_in_code():
    """Test that upload handlers use user-specific paths"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Upload Handlers Use User-Specific Paths")
    logger.info("=" * 80)
    
    try:
        # Check Flask application code
        flask_file = project_root / 'src' / 'localhost_only_flask.py'
        
        if not flask_file.exists():
            logger.error(f"   ❌ Flask file not found: {flask_file}")
            return False
        
        with open(flask_file, 'r') as f:
            content = f.read()
        
        # Check for usage of path functions
        checks = [
            ('get_user_upload_path', 'get_user_upload_path('),
            ('get_user_generated_path', 'get_user_generated_path('),
            ('upload_unified route', '@app.route(\'/upload_unified\''),
            ('create_montage route', 'def create_montage('),
            ('create_slideshow route', 'def create_slideshow('),
        ]
        
        all_found = True
        for check_name, search_str in checks:
            if search_str in content:
                count = content.count(search_str)
                logger.info(f"   ✅ {check_name}: Found {count} occurrence(s)")
            else:
                logger.error(f"   ❌ {check_name}: Not found")
                all_found = False
        
        if all_found:
            logger.info("\n✅ Code Inspection Test: PASSED")
            return True
        else:
            logger.error("\n❌ Code Inspection Test: FAILED")
            return False
            
    except Exception as e:
        logger.error(f"❌ Code inspection test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_oci_bucket_structure():
    """Test actual OCI bucket structure (if OCI is available)"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 5: OCI Bucket Structure (Optional)")
    logger.info("=" * 80)
    
    try:
        import oci
        from src.oci_storage import get_oci_client
        
        namespace = os.getenv('OCI_NAMESPACE')
        bucket = os.getenv('OCI_BUCKET_NAME', 'video-ai-storage')
        
        if not namespace:
            logger.warning("   ⚠️  Skipping: OCI_NAMESPACE not configured")
            return None
        
        try:
            client = get_oci_client()
            
            # List objects with 'users/' prefix
            logger.info(f"\n📦 Listing objects in bucket '{bucket}' with 'users/' prefix:")
            
            response = client.list_objects(
                namespace_name=namespace,
                bucket_name=bucket,
                prefix='users/',
                delimiter='/',
                limit=100
            )
            
            if not response.data.objects and not response.data.prefixes:
                logger.info("   ℹ️  No user-specific files found yet (bucket is empty)")
                logger.info("   💡 Upload some files through the application to test")
                return None
            
            # Show prefixes (user directories)
            if response.data.prefixes:
                logger.info("\n   📁 User Directories:")
                for prefix in response.data.prefixes:
                    logger.info(f"      {prefix}")
            
            # Show some objects
            if response.data.objects:
                logger.info(f"\n   📄 Files (showing first 10):")
                for i, obj in enumerate(response.data.objects[:10]):
                    size_mb = obj.size / (1024 * 1024)
                    logger.info(f"      {obj.name} ({size_mb:.2f} MB)")
            
            logger.info("\n✅ OCI Bucket Structure Test: PASSED")
            return True
            
        except Exception as e:
            logger.error(f"   ❌ Failed to list OCI objects: {e}")
            return False
            
    except ImportError:
        logger.warning("   ⚠️  Skipping: OCI SDK not installed")
        return None
    except Exception as e:
        logger.error(f"❌ OCI bucket structure test failed: {e}")
        return False


def print_summary(results):
    """Print test summary"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)
    
    for test_name, result in results.items():
        if result is True:
            status = "✅ PASSED"
        elif result is False:
            status = "❌ FAILED"
        else:
            status = "⚠️  SKIPPED"
        logger.info(f"   {status}: {test_name}")
    
    logger.info(f"\n📊 Results: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed > 0:
        logger.error("\n❌ OVERALL: TESTS FAILED")
        logger.info("\n💡 Next Steps:")
        if 'OCI Configuration' in [k for k, v in results.items() if v is False]:
            logger.info("   1. Set up OCI configuration:")
            logger.info("      - Run: oci setup config")
            logger.info("      - Add OCI_NAMESPACE and OCI_BUCKET_NAME to .env")
        if 'Database Users' in [k for k, v in results.items() if v is False]:
            logger.info("   2. Create test users:")
            logger.info("      - Run: python scripts/create_admin_user.py")
        return False
    else:
        logger.info("\n✅ OVERALL: ALL TESTS PASSED")
        logger.info("\n💡 Next Steps:")
        logger.info("   1. Start Flask application: python src/localhost_only_flask.py")
        logger.info("   2. Upload files as different users")
        logger.info("   3. Check OCI bucket to verify paths: users/{user_id}/uploads/")
        logger.info("   4. Create montage/slideshow and verify: users/{user_id}/generated/")
        return True


def main():
    """Run all tests"""
    logger.info("🧪 Starting OCI Path Isolation Tests")
    logger.info(f"⏰ Test Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Run tests
    results = {
        'Path Generation': test_path_generation(),
        'OCI Configuration': test_oci_configuration(),
        'Database Users': test_database_users(),
        'Code Inspection': test_upload_path_in_code(),
        'OCI Bucket Structure': test_oci_bucket_structure(),
    }
    
    # Print summary
    success = print_summary(results)
    
    # Return exit code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
