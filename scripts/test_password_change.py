#!/usr/bin/env python3
"""
Test script to change admin password directly
"""

import sys
import os

# Add path to twelvelabvideoai/src
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
twelvelabs_src = os.path.join(project_root, 'twelvelabvideoai', 'src')
sys.path.insert(0, twelvelabs_src)

from auth_utils import get_user_by_username, verify_password, update_user_password
import bcrypt

def test_password_change(username, old_password, new_password):
    """Test password change process"""
    
    print(f"\n🔍 Testing password change for user: {username}")
    print("=" * 60)
    
    # Step 1: Get user
    print("\n1️⃣  Fetching user from database...")
    user = get_user_by_username(username)
    if not user:
        print(f"❌ User '{username}' not found")
        return False
    
    print(f"✅ User found: {user.username} (ID: {user.id})")
    
    # Step 2: Verify old password
    print(f"\n2️⃣  Verifying current password...")
    if not verify_password(old_password, user.password_hash):
        print(f"❌ Current password is incorrect")
        return False
    
    print(f"✅ Current password verified")
    
    # Step 3: Update password
    print(f"\n3️⃣  Updating password...")
    if not update_user_password(user.id, new_password):
        print(f"❌ Failed to update password")
        return False
    
    print(f"✅ Password updated in database")
    
    # Step 4: Verify new password works
    print(f"\n4️⃣  Verifying new password...")
    user_after = get_user_by_username(username)
    if not user_after:
        print(f"❌ Could not fetch user after update")
        return False
    
    if not verify_password(new_password, user_after.password_hash):
        print(f"❌ New password verification failed")
        return False
    
    print(f"✅ New password verified successfully")
    
    # Step 5: Confirm old password doesn't work
    print(f"\n5️⃣  Confirming old password no longer works...")
    if verify_password(old_password, user_after.password_hash):
        print(f"❌ Old password still works (update may have failed)")
        return False
    
    print(f"✅ Old password correctly rejected")
    
    print("\n" + "=" * 60)
    print("🎉 Password change completed successfully!")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Password Change Test Script")
    print("=" * 60)
    
    username = input("\nEnter username [admin]: ").strip() or "admin"
    old_password = input("Enter current password: ").strip()
    new_password = input("Enter new password: ").strip()
    confirm_password = input("Confirm new password: ").strip()
    
    if not old_password or not new_password:
        print("\n❌ Password cannot be empty")
        sys.exit(1)
    
    if new_password != confirm_password:
        print("\n❌ New passwords do not match")
        sys.exit(1)
    
    if len(new_password) < 8:
        print("\n❌ New password must be at least 8 characters")
        sys.exit(1)
    
    success = test_password_change(username, old_password, new_password)
    
    if success:
        print(f"\n✅ You can now login with:")
        print(f"   Username: {username}")
        print(f"   Password: {new_password}")
        sys.exit(0)
    else:
        print(f"\n❌ Password change failed")
        sys.exit(1)
