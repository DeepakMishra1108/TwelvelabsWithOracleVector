#!/usr/bin/env python3
"""
Create Initial Admin User
Run this script after creating the users table to set up the first admin account
"""

import sys
import os
import getpass
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'twelvelabvideoai' / 'src'))

import bcrypt
from utils.db_utils_vector import get_db_connection

def create_admin_user():
    """Create the initial admin user"""
    
    print("=" * 60)
    print("CREATE ADMIN USER FOR DATA GUARDIAN")
    print("=" * 60)
    print()
    
    # Get admin credentials
    username = input("Enter admin username: ").strip()
    if not username:
        print("❌ Username cannot be empty!")
        return False
    
    email = input("Enter admin email (optional): ").strip()
    
    # Get password with confirmation
    while True:
        password = getpass.getpass("Enter admin password: ")
        if len(password) < 8:
            print("❌ Password must be at least 8 characters!")
            continue
        
        confirm_password = getpass.getpass("Confirm password: ")
        if password != confirm_password:
            print("❌ Passwords don't match! Try again.")
            continue
        
        break
    
    # Hash the password
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Insert into database
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if user already exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = :username", {"username": username})
        if cursor.fetchone()[0] > 0:
            print(f"❌ User '{username}' already exists!")
            cursor.close()
            connection.close()
            return False
        
        # Insert admin user
        cursor.execute("""
            INSERT INTO users (username, password_hash, email, role, is_active)
            VALUES (:username, :password_hash, :email, 'admin', 1)
        """, {
            "username": username,
            "password_hash": password_hash,
            "email": email if email else None
        })
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print()
        print("✅ Admin user created successfully!")
        print(f"   Username: {username}")
        print(f"   Role: admin")
        print(f"   Email: {email if email else 'Not provided'}")
        print()
        print("You can now login at: http://150.136.235.189/login")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        return False

if __name__ == "__main__":
    success = create_admin_user()
    sys.exit(0 if success else 1)
