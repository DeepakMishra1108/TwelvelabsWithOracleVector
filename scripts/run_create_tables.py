#!/usr/bin/env python3
"""
Run the create_users_table.sql script
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'twelvelabvideoai' / 'src'))

from utils.db_utils_vector import get_db_connection

def run_sql_file():
    """Execute the SQL file to create tables"""
    print("=" * 60)
    print("CREATING AUTHENTICATION TABLES")
    print("=" * 60)
    print()
    
    try:
        # Read SQL file
        sql_file = Path(__file__).parent / 'create_users_table.sql'
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        # Connect to database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Split SQL by statements (separated by semicolon)
        statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
        
        executed = 0
        for stmt in statements:
            # Skip comments and grant statements
            if stmt.startswith('--') or stmt.upper().startswith('COMMENT') or stmt.upper().startswith('GRANT'):
                continue
            
            try:
                print(f"Executing: {stmt[:60]}...")
                cursor.execute(stmt)
                executed += 1
                print("✅ Success")
            except Exception as e:
                # Ignore "table already exists" errors
                if 'ORA-00955' in str(e) or 'already exists' in str(e).lower():
                    print(f"⚠️  Table already exists, skipping")
                else:
                    print(f"❌ Error: {e}")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print()
        print(f"✅ Successfully executed {executed} SQL statements")
        print()
        print("Tables created:")
        print("  - users (authentication)")
        print("  - login_attempts (audit log)")
        print()
        print("Next step: Run create_admin_user.py to create your admin account")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = run_sql_file()
    sys.exit(0 if success else 1)
