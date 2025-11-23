"""
Migration script to add location column to lawyers table.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import inspect, text
from backend.email_service.database import engine, Lawyer

def migrate_add_location():
    """Add location column to lawyers table if it doesn't exist."""
    print("=" * 60)
    print("Lawyers Migration: Adding location column")
    print("=" * 60)
    
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('lawyers')]
    
    if 'location' not in columns:
        print("Adding location column...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE lawyers ADD COLUMN location VARCHAR"))
            conn.commit()
        print("✓ location column added")
    else:
        print("✓ location column already exists")
    
    print("\n✅ Migration completed successfully!")

if __name__ == "__main__":
    migrate_add_location()

