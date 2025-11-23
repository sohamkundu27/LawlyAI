"""
Migration script to add manual_mode and phone_call_requested columns to email_threads table.
Run this once to update existing database.
"""

import sqlite3
import os
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent / "email_service.db"

def migrate():
    """Add manual_mode and phone_call_requested columns to email_threads table."""
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        print("Database will be created automatically on next startup.")
        return
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(email_threads)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Add manual_mode column if it doesn't exist
        if 'manual_mode' not in columns:
            print("Adding manual_mode column...")
            cursor.execute("ALTER TABLE email_threads ADD COLUMN manual_mode INTEGER DEFAULT 0")
            print("✓ Added manual_mode column")
        else:
            print("✓ manual_mode column already exists")
        
        # Add phone_call_requested column if it doesn't exist
        if 'phone_call_requested' not in columns:
            print("Adding phone_call_requested column...")
            cursor.execute("ALTER TABLE email_threads ADD COLUMN phone_call_requested INTEGER DEFAULT 0")
            print("✓ Added phone_call_requested column")
        else:
            print("✓ phone_call_requested column already exists")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during migration: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Email Threads Migration: Adding manual_mode and phone_call_requested")
    print("=" * 60)
    migrate()

