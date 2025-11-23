"""
Migration script to move data from JSON files to database.
Run this once to migrate existing data.
"""

from backend.email_service.database import init_db, get_db_session
from backend.email_service.database import EmailThread, EmailMessage, Lawyer, ProcessedEmail
from datetime import datetime
import json
import os

def migrate_conversations():
    """Migrate email conversations from JSON to database."""
    conversations_file = "email_conversations.json"
    
    if not os.path.exists(conversations_file):
        print("No conversations file to migrate")
        return
    
    db = get_db_session()
    try:
        with open(conversations_file, 'r') as f:
            conversations = json.load(f)
        
        migrated = 0
        for thread_id, thread_data in conversations.items():
            # Check if thread already exists
            existing = db.query(EmailThread).filter(EmailThread.thread_id == thread_id).first()
            if existing:
                continue
            
            # Create thread
            thread = EmailThread(
                thread_id=thread_id,
                subject=thread_data.get('subject', ''),
                participants=thread_data.get('participants', []),
                created_at=datetime.fromisoformat(thread_data.get('created_at', datetime.utcnow().isoformat())),
                updated_at=datetime.fromisoformat(thread_data.get('updated_at', datetime.utcnow().isoformat()))
            )
            db.add(thread)
            
            # Add messages
            for email_data in thread_data.get('emails', []):
                msg = EmailMessage(
                    thread_id=thread_id,
                    from_email=email_data.get('from', ''),
                    to_email=email_data.get('to', ''),
                    subject=email_data.get('subject', ''),
                    body=email_data.get('body', ''),
                    date=email_data.get('date', ''),
                    uid=email_data.get('uid', ''),
                    timestamp=datetime.fromisoformat(email_data.get('timestamp', datetime.utcnow().isoformat()))
                )
                db.add(msg)
            
            migrated += 1
        
        db.commit()
        print(f"✅ Migrated {migrated} conversation threads")
    except Exception as e:
        db.rollback()
        print(f"❌ Error migrating conversations: {e}")
    finally:
        db.close()


def migrate_lawyers():
    """Migrate lawyer data from JSON to database."""
    lawyers_file = "lawyers_data.json"
    
    if not os.path.exists(lawyers_file):
        print("No lawyers file to migrate")
        return
    
    db = get_db_session()
    try:
        with open(lawyers_file, 'r') as f:
            lawyers_data = json.load(f)
        
        migrated = 0
        for email, lawyer_data in lawyers_data.items():
            # Check if lawyer already exists
            existing = db.query(Lawyer).filter(Lawyer.lawyer_email == email.lower()).first()
            if existing:
                continue
            
            # Create lawyer
            lawyer = Lawyer(
                lawyer_email=email.lower(),
                lawyer_name=lawyer_data.get('lawyer_name', ''),
                firm_name=lawyer_data.get('firm_name', ''),
                hourly_rate=lawyer_data.get('hourly_rate'),
                flat_fee=lawyer_data.get('flat_fee'),
                contingency_rate=lawyer_data.get('contingency_rate'),
                retainer_amount=lawyer_data.get('retainer_amount'),
                estimated_total=lawyer_data.get('estimated_total'),
                payment_plan=lawyer_data.get('payment_plan', ''),
                experience_years=lawyer_data.get('experience_years'),
                case_types=lawyer_data.get('case_types', []),
                availability=lawyer_data.get('availability', ''),
                response_time=lawyer_data.get('response_time', ''),
                terms=lawyer_data.get('terms', ''),
                notes=lawyer_data.get('notes', ''),
                first_contact_date=datetime.fromisoformat(lawyer_data.get('first_contact_date', datetime.utcnow().isoformat())) if lawyer_data.get('first_contact_date') else None,
                last_contact_date=datetime.fromisoformat(lawyer_data.get('last_contact_date', datetime.utcnow().isoformat())) if lawyer_data.get('last_contact_date') else None,
                email_count=lawyer_data.get('email_count', 0),
                thread_id=lawyer_data.get('thread_id', '')
            )
            db.add(lawyer)
            migrated += 1
        
        db.commit()
        print(f"✅ Migrated {migrated} lawyers")
    except Exception as e:
        db.rollback()
        print(f"❌ Error migrating lawyers: {e}")
    finally:
        db.close()


def migrate_processed_emails():
    """Migrate processed emails from JSON to database."""
    processed_file = "processed_emails.json"
    
    if not os.path.exists(processed_file):
        print("No processed emails file to migrate")
        return
    
    db = get_db_session()
    try:
        with open(processed_file, 'r') as f:
            data = json.load(f)
        
        uids = data.get('processed_uids', [])
        migrated = 0
        
        for uid in uids:
            # Check if already exists
            existing = db.query(ProcessedEmail).filter(ProcessedEmail.uid == uid).first()
            if existing:
                continue
            
            processed = ProcessedEmail(uid=uid)
            db.add(processed)
            migrated += 1
        
        db.commit()
        print(f"✅ Migrated {migrated} processed email UIDs")
    except Exception as e:
        db.rollback()
        print(f"❌ Error migrating processed emails: {e}")
    finally:
        db.close()


def main():
    """Run all migrations."""
    print("=" * 60)
    print("Migrating from JSON files to database...")
    print("=" * 60)
    
    # Initialize database
    init_db()
    
    # Change to email_service directory
    original_dir = os.getcwd()
    os.chdir(os.path.join(original_dir, 'backend', 'email_service'))
    
    try:
        migrate_conversations()
        migrate_lawyers()
        migrate_processed_emails()
        
        print("=" * 60)
        print("✅ Migration complete!")
        print("=" * 60)
        print("\nNote: JSON files are kept as backup. You can delete them after verifying the migration.")
    finally:
        os.chdir(original_dir)


if __name__ == "__main__":
    main()

