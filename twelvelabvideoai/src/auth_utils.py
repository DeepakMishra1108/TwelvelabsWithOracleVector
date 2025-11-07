#!/usr/bin/env python3
"""
Authentication Utilities for Data Guardian
Provides user authentication, password hashing, and session management
"""

import bcrypt
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from flask_login import UserMixin
from utils.db_utils_vector import get_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class User(UserMixin):
    """User class for Flask-Login"""
    
    def __init__(self, id: int, username: str, email: str, role: str, is_active: bool = True, 
                 password_hash: str = None, created_at: datetime = None, last_login: datetime = None):
        self.id = id
        self.username = username
        self.email = email
        self.role = role
        self.active = is_active
        self.password_hash = password_hash
        self.created_at = created_at
        self.last_login = last_login
    
    def is_active(self):
        """Check if user account is active"""
        return self.active
    
    def has_role(self, role: str) -> bool:
        """Check if user has a specific role"""
        return self.role == role
    
    def can_edit(self) -> bool:
        """Check if user can edit content"""
        return self.role in ['admin', 'editor']
    
    def can_delete(self) -> bool:
        """Check if user can delete content"""
        return self.role == 'admin'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'is_active': self.active
        }


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def get_user_by_id(user_id: int) -> Optional[User]:
    """Load user by ID"""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT id, username, email, role, is_active, password_hash, created_at, last_login
            FROM users
            WHERE id = :user_id
        """, {"user_id": user_id})
        
        row = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if row:
            return User(
                id=row[0],
                username=row[1],
                email=row[2],
                role=row[3],
                is_active=bool(row[4]),
                password_hash=row[5],
                created_at=row[6],
                last_login=row[7]
            )
        
        return None
        
    except Exception as e:
        logger.error(f"Error loading user by ID: {e}")
        return None


def get_user_by_username(username: str) -> Optional[User]:
    """Load user by username"""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT id, username, email, role, is_active, password_hash, created_at, last_login
            FROM users
            WHERE username = :username
        """, {"username": username})
        
        row = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if row:
            return User(
                id=row[0],
                username=row[1],
                email=row[2],
                role=row[3],
                is_active=bool(row[4]),
                password_hash=row[5],
                created_at=row[6],
                last_login=row[7]
            )
        
        return None
        
    except Exception as e:
        logger.error(f"Error loading user by username: {e}")
        return None


def authenticate_user(username: str, password: str, ip_address: str = None) -> Optional[User]:
    """Authenticate a user with username and password"""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get user with password hash
        cursor.execute("""
            SELECT id, username, email, role, is_active, password_hash
            FROM users
            WHERE username = :username
        """, {"username": username})
        
        row = cursor.fetchone()
        
        if not row:
            # Log failed attempt (user not found)
            log_login_attempt(username, False, ip_address)
            cursor.close()
            connection.close()
            return None
        
        user_id, username, email, role, is_active, password_hash = row
        
        # Verify password
        if not verify_password(password, password_hash):
            # Log failed attempt (wrong password)
            log_login_attempt(username, False, ip_address)
            cursor.close()
            connection.close()
            return None
        
        # Check if account is active
        if not is_active:
            logger.warning(f"Login attempt for disabled account: {username}")
            log_login_attempt(username, False, ip_address)
            cursor.close()
            connection.close()
            return None
        
        # Update last login time
        cursor.execute("""
            UPDATE users
            SET last_login = CURRENT_TIMESTAMP
            WHERE id = :user_id
        """, {"user_id": user_id})
        
        connection.commit()
        
        # Log successful attempt
        log_login_attempt(username, True, ip_address)
        
        cursor.close()
        connection.close()
        
        logger.info(f"✅ User authenticated: {username} (role: {role})")
        
        return User(
            id=user_id,
            username=username,
            email=email,
            role=role,
            is_active=bool(is_active)
        )
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return None


def log_login_attempt(username: str, success: bool, ip_address: str = None):
    """Log a login attempt to the audit table"""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO login_attempts (username, ip_address, success)
            VALUES (:username, :ip_address, :success)
        """, {
            "username": username,
            "ip_address": ip_address,
            "success": 1 if success else 0
        })
        
        connection.commit()
        cursor.close()
        connection.close()
        
    except Exception as e:
        logger.error(f"Error logging login attempt: {e}")


def get_recent_failed_attempts(username: str, minutes: int = 30) -> int:
    """Get count of recent failed login attempts"""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT COUNT(*)
            FROM login_attempts
            WHERE username = :username
              AND success = 0
              AND attempt_time > CURRENT_TIMESTAMP - INTERVAL '{minutes}' MINUTE
        """.format(minutes=minutes), {"username": username})
        
        count = cursor.fetchone()[0]
        cursor.close()
        connection.close()
        
        return count
        
    except Exception as e:
        logger.error(f"Error getting failed attempts: {e}")
        return 0


def create_user(username: str, password: str, email: str = None, role: str = 'viewer') -> bool:
    """Create a new user (admin function)"""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if username already exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = :username", {"username": username})
        if cursor.fetchone()[0] > 0:
            logger.warning(f"Username already exists: {username}")
            cursor.close()
            connection.close()
            return False
        
        # Hash password and insert
        password_hash = hash_password(password)
        
        cursor.execute("""
            INSERT INTO users (username, password_hash, email, role, is_active)
            VALUES (:username, :password_hash, :email, :role, 1)
        """, {
            "username": username,
            "password_hash": password_hash,
            "email": email,
            "role": role
        })
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info(f"✅ User created: {username} (role: {role})")
        return True
        
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return False


def update_user_password(user_id: int, new_password: str) -> bool:
    """
    Update user's password
    
    Args:
        user_id: User ID
        new_password: New plain text password
        
    Returns:
        bool: True if password updated successfully
    """
    try:
        connection = get_db_connection()
        if not connection:
            logger.error("Failed to connect to database")
            return False
        
        cursor = connection.cursor()
        
        # Hash the new password
        password_hash = hash_password(new_password)
        
        # Update password
        cursor.execute("""
            UPDATE users 
            SET password_hash = :password_hash
            WHERE id = :user_id
        """, {
            "password_hash": password_hash,
            "user_id": user_id
        })
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info(f"✅ Password updated for user ID: {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating password: {e}")
        return False
