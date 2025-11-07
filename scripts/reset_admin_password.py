#!/usr/bin/env python3
"""
Reset admin password to a known value
Usage: python reset_admin_password.py
"""

import sys
import os

# Add path to twelvelabvideoai/src
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
twelvelabs_src = os.path.join(project_root, 'twelvelabvideoai', 'src')
sys.path.insert(0, twelvelabs_src)

from auth_utils import update_user_password, get_user_by_username, verify_password

def reset_password():
    """Reset admin password"""
    
    username = "admin"
    new_password = "Admin@123"
    
    print(f"\n🔄 Resetting password for user: {username}")
    print("=" * 60)
    
    # Get user
    user = get_user_by_username(username)
    if not user:
        print(f"❌ User '{username}' not found")
        return False
    
    print(f"✅ User found: {user.username} (ID: {user.id})")
    
    # Update password
    print(f"\n🔧 Setting password to: {new_password}")
    if not update_user_password(user.id, new_password):
        print(f"❌ Failed to update password")
        return False
    
    print(f"✅ Password updated in database")
    
    # Verify it works
    print(f"\n🔍 Verifying new password...")
    user_after = get_user_by_username(username)
    if verify_password(new_password, user_after.password_hash):
        print(f"✅ Password verified successfully")
    else:
        print(f"❌ Password verification failed")
        return False
    
    print("\n" + "=" * 60)
    print("✅ Password reset completed!")
    print("=" * 60)
    print(f"\nYou can now login with:")
    print(f"  Username: {username}")
    print(f"  Password: {new_password}")
    print()
    
    return True


if __name__ == "__main__":
    reset_password()
