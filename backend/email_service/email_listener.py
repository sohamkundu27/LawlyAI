"""
Email listener and auto-responder using the AI agent.
Checks for incoming emails and automatically generates responses.
"""

import os
import imaplib
import email
import time
import json
from email.header import decode_header
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv

from backend.email_service.email_agent import create_email_agent, send_email_tool
from backend.email_service.conversation_manager_db import ConversationManagerDB as ConversationManager
from backend.email_service.email_conversation_manager import extract_email_headers  # Keep this utility function
from backend.email_service.email_filters import EmailFilter
from backend.email_service.lawyer_tracker_db import LawyerTrackerDB as LawyerTracker

load_dotenv()

# Email configuration
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "your-email@gmail.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "your-app-password")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))

# File to track processed emails
PROCESSED_EMAILS_FILE = "processed_emails.json"


def load_processed_emails() -> set:
    """Load set of processed email UIDs from database."""
    from backend.email_service.database import ProcessedEmail, get_db_session
    
    db = get_db_session()
    try:
        processed = db.query(ProcessedEmail).all()
        return set(p.uid for p in processed)
    finally:
        db.close()


def save_processed_email(uid: str):
    """Save processed email UID to database."""
    from backend.email_service.database import ProcessedEmail, get_db_session
    
    db = get_db_session()
    try:
        # Check if already exists
        existing = db.query(ProcessedEmail).filter(ProcessedEmail.uid == uid).first()
        if not existing:
            processed = ProcessedEmail(uid=uid)
            db.add(processed)
            db.commit()
        
        # Clean up old entries (keep last 1000)
        all_processed = db.query(ProcessedEmail).order_by(ProcessedEmail.processed_at.desc()).all()
        if len(all_processed) > 1000:
            for old_entry in all_processed[1000:]:
                db.delete(old_entry)
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error saving processed email: {e}")
    finally:
        db.close()


def decode_mime_words(s):
    """Decode MIME encoded words in email headers."""
    if s is None:
        return ""
    decoded_fragments = decode_header(s)
    decoded_str = ""
    for fragment, encoding in decoded_fragments:
        if isinstance(fragment, bytes):
            decoded_str += fragment.decode(encoding or 'utf-8', errors='ignore')
        else:
            decoded_str += fragment
    return decoded_str


def get_email_body(msg):
    """Extract email body text."""
    body = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
                except:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        except:
            body = str(msg.get_payload())
    
    return body.strip()


def fetch_new_emails() -> List[Dict]:
    """Fetch new emails from inbox."""
    emails = []
    
    try:
        # Connect to IMAP server
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(SENDER_EMAIL, SENDER_PASSWORD)
        mail.select("inbox")
        
        # Search for unread emails
        status, messages = mail.search(None, "UNSEEN")
        
        if status != "OK":
            print(f"  [WARNING] IMAP search returned status: {status}")
            mail.close()
            mail.logout()
            return emails
        
        email_ids = messages[0].split()
        processed = load_processed_emails()
        
        if not email_ids:
            mail.close()
            mail.logout()
            return emails
        
        print(f"  Found {len(email_ids)} unread email(s) in inbox")
        
        for email_id in email_ids:
            uid = email_id.decode('utf-8')
            
            # Skip if already processed
            if uid in processed:
                print(f"  Skipping email {uid} (already processed)")
                continue
            
            # Fetch email
            status, msg_data = mail.fetch(email_id, "(RFC822)")
            
            if status != "OK":
                print(f"  [WARNING] Failed to fetch email {uid}")
                continue
            
            # Parse email
            email_body = msg_data[0][1]
            msg = email.message_from_bytes(email_body)
            
            # Extract email details
            subject = decode_mime_words(msg["Subject"]) or "(No Subject)"
            from_addr = decode_mime_words(msg["From"]) or "Unknown"
            to_addr = decode_mime_words(msg["To"]) or SENDER_EMAIL
            date = msg["Date"] or "Unknown"
            body = get_email_body(msg)
            
            # Extract email address from "Name <email@example.com>" format
            from_email = from_addr
            if "<" in from_addr and ">" in from_addr:
                from_email = from_addr.split("<")[1].split(">")[0].strip()
            elif "@" in from_addr:
                from_email = from_addr.strip()
            
            # Extract threading headers
            headers = extract_email_headers(msg)
            
            emails.append({
                'uid': uid,
                'from': from_email,
                'from_display': from_addr,
                'to': to_addr,
                'subject': subject,
                'body': body,
                'date': date,
                **headers  # Add message_id, in_reply_to, references
            })
        
        mail.close()
        mail.logout()
        
    except imaplib.IMAP4.error as e:
        print(f"[ERROR] IMAP error: {str(e)}")
        print("  Check your IMAP settings and app-specific password")
    except Exception as e:
        print(f"[ERROR] Failed to fetch emails: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return emails


def generate_reply(agent, original_email: Dict, conversation_manager: ConversationManager) -> Optional[str]:
    """
    Use the agent to generate a reply to an email with conversation context.
    
    Args:
        agent: The email agent instance
        original_email: Dictionary with email details
        conversation_manager: Conversation manager for thread context
    
    Returns:
        Reply text or None if no reply should be sent
    """
    # Get thread ID (email should already be saved, but add_email is idempotent with duplicate checking)
    thread_id = conversation_manager.add_email(original_email)
    conversation_context = conversation_manager.get_conversation_context(thread_id)
    
    from_email = original_email.get('from', '').lower().strip()
    
    # Check if this is from a tracked lawyer
    if hasattr(agent, 'is_lawyer_email') and agent.is_lawyer_email(from_email):
        # Use lawyer-specific reply generation
        # Don't pass full conversation context - only use the lawyer's actual response
        # This prevents the AI from getting confused about roles
        try:
            reply = agent.generate_lawyer_reply(
                lawyer_email=from_email,
                incoming_email=original_email,
                conversation_context=None  # Don't pass context - focus only on lawyer's response
            )
            return reply if reply else None
        except Exception as e:
            print(f"[ERROR] Failed to generate lawyer reply: {str(e)}")
            import traceback
            traceback.print_exc()
            # Fall through to regular reply generation
    
    # Regular reply generation for non-lawyer emails or fallback
    # Create context for the agent
    if conversation_context and len(conversation_manager.get_conversation_history(thread_id)) > 1:
        # This is part of an ongoing conversation
        context = f"""You are continuing a conversation thread. Here's the conversation history:

{conversation_context}

The most recent message is from {original_email['from_display']}:

{original_email['body']}

Please generate an appropriate response that:
- Acknowledges the conversation history
- Responds to the most recent message
- Maintains context from previous exchanges
- Be helpful, professional, and concise

Generate your response now:"""
    else:
        # This is a new conversation
        context = f"""You received a new email from {original_email['from_display']} with subject: "{original_email['subject']}"

Email content:
{original_email['body']}

Please generate an appropriate response to this email. Be helpful, professional, and concise. If the email requires action, acknowledge it. If it's a question, provide a helpful answer.

Generate your response now:"""
    
    try:
        result = agent.invoke(context)
        reply = result.get('output', '').strip()
        
        # Check if agent wants to send an email (it might use the tool)
        # If not, return the generated text
        return reply
        
    except Exception as e:
        print(f"[ERROR] Failed to generate reply: {str(e)}")
        return None


def send_reply(original_email: Dict, reply_text: str, conversation_manager=None) -> bool:
    """Send a reply email and save it to conversation history."""
    try:
        # Create reply subject
        subject = original_email['subject']
        if not subject.lower().startswith('re:'):
            subject = f"Re: {subject}"
        
        # Send email using the tool
        result = send_email_tool.invoke({
            'recipient_email': original_email['from'],
            'subject': subject,
            'body': reply_text
        })
        
        success = "successfully" in result.lower()
        
        # Save the sent reply to conversation history
        if success and conversation_manager:
            try:
                reply_email_data = {
                    'from': SENDER_EMAIL,
                    'to': original_email['from'],
                    'subject': subject,
                    'body': reply_text,
                    'date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z'),
                    'uid': '',  # Sent emails don't have UIDs
                    'message_id': '',
                    'in_reply_to': original_email.get('message_id', ''),
                    'references': original_email.get('message_id', '')
                }
                conversation_manager.add_email(reply_email_data)
            except Exception as e:
                print(f"[WARNING] Failed to save reply to conversation history: {str(e)}")
        
        return success
        
    except Exception as e:
        print(f"[ERROR] Failed to send reply: {str(e)}")
        return False


def process_emails(agent, conversation_manager=None, lawyer_tracker=None, auto_reply: bool = True, verbose: bool = True):
    """
    Process new emails and optionally send replies.
    
    Args:
        agent: The email agent instance
        conversation_manager: Conversation manager instance (if None, creates file-based one)
        lawyer_tracker: Lawyer tracker instance (if None, creates file-based one)
        auto_reply: If True, automatically send replies
        verbose: If True, show detailed output
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if verbose:
        print(f"[{timestamp}] Checking for new emails...")
    
    # Use provided managers or create file-based ones (for backward compatibility)
    if conversation_manager is None:
        from backend.email_service.email_conversation_manager import ConversationManager as FileConversationManager
        conversation_manager = FileConversationManager()
    if lawyer_tracker is None:
        from backend.email_service.lawyer_tracker import LawyerTracker as FileLawyerTracker
        lawyer_tracker = FileLawyerTracker()
    
    email_filter = EmailFilter()
    
    try:
        emails = fetch_new_emails()
    except Exception as e:
        print(f"[{timestamp}] [ERROR] Failed to check emails: {str(e)}")
        return
    
    if not emails:
        if verbose:
            print(f"  No new emails found.")
        return
    
    print(f"\n[{timestamp}] Found {len(emails)} new email(s)!")
    print("=" * 60)
    
    processed_count = 0
    skipped_count = 0
    
    for i, email_data in enumerate(emails, 1):
        print(f"\n{'='*80}")
        print(f"[Email {i}/{len(emails)}]")
        print(f"{'='*80}")
        print(f"  From: {email_data['from_display']}")
        print(f"  To: {email_data.get('to', 'N/A')}")
        print(f"  Subject: {email_data['subject']}")
        print(f"  Date: {email_data['date']}")
        print(f"  Message ID: {email_data.get('message_id', 'N/A')}")
        print(f"  In-Reply-To: {email_data.get('in_reply_to', 'N/A')}")
        print(f"  References: {email_data.get('references', 'N/A')}")
        print(f"\n  {'-'*80}")
        print(f"  FULL EMAIL BODY:")
        print(f"  {'-'*80}")
        print(f"  {email_data['body']}")
        print(f"  {'-'*80}")
        print(f"{'='*80}\n")
        
        # Save incoming email to conversation history FIRST (even if skipped)
        # This ensures all emails are tracked, not just ones we reply to
        try:
            thread_id = conversation_manager.add_email(email_data)
            print(f"  [OK] Saved email to conversation history (Thread ID: {thread_id})")
        except Exception as e:
            print(f"  [WARNING] Failed to save email to conversation history: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Check if email should be processed
        should_process, reason = email_filter.should_process(email_data)
        if not should_process:
            print(f"  [SKIPPED] {reason}")
            print(f"  Body preview: {email_data['body'][:100]}..." if len(email_data['body']) > 100 else f"  Body: {email_data['body']}")
            save_processed_email(email_data['uid'])  # Mark as processed so we don't check again
            skipped_count += 1
            continue
        
        # Check if this is part of an existing thread
        thread_id = conversation_manager.find_thread_by_email(email_data)
        if thread_id:
            history = conversation_manager.get_conversation_history(thread_id)
            print(f"  Thread: Existing conversation ({len(history)} previous messages)")
        else:
            print(f"  Thread: New conversation")
        
        # Check if this is from a tracked lawyer
        from_email = email_data.get('from', '').lower()
        is_tracked_lawyer = False
        
        if hasattr(agent, 'is_lawyer_email'):
            is_tracked_lawyer = agent.is_lawyer_email(from_email)
            if is_tracked_lawyer:
                print(f"\n  {'#'*80}")
                print(f"  # LAWYER RESPONSE DETECTED!")
                print(f"  {'#'*80}")
                print(f"  [LAWYER] Email from tracked lawyer: {from_email}")
                conv_status = agent.get_lawyer_conversation_status(from_email)
                if conv_status:
                    print(f"           Status: {conv_status.get('status', 'unknown')}")
                    print(f"           Message count: {conv_status.get('message_count', 0)}")
                print(f"  {'#'*80}\n")
        
        # Check if this might be from a lawyer (even if not tracked) and track it
        body_lower = email_data.get('body', '').lower()
        is_lawyer_email = any(keyword in body_lower for keyword in [
            'attorney', 'lawyer', 'legal', 'law firm', 'counsel', 
            'litigation', 'representation', 'retainer', 'contingency'
        ])
        
        if is_lawyer_email or is_tracked_lawyer:
            print(f"  [LAWYER] Detected lawyer email - tracking offer...")
            lawyer = lawyer_tracker.add_lawyer_email(email_data, thread_id or "")
            if lawyer:
                print(f"  [LAWYER] Extracted: {lawyer.lawyer_name}")
                if lawyer.flat_fee:
                    print(f"           Flat fee: ${lawyer.flat_fee:,.2f}")
                elif lawyer.hourly_rate:
                    print(f"           Hourly: ${lawyer.hourly_rate:,.2f}/hr")
                elif lawyer.contingency_rate:
                    print(f"           Contingency: {lawyer.contingency_rate}%")
            
            # Update fact extraction + ranking if the tracker supports it
            if hasattr(lawyer_tracker, "update_lawyer_facts_from_message"):
                try:
                    updated = lawyer_tracker.update_lawyer_facts_from_message(
                        from_email,
                        email_data.get('body', '')
                    )
                    if updated:
                        print("  [LAWYER] Updated extracted facts from this message.")
                except Exception as fact_err:
                    print(f"  [WARNING] Failed to update lawyer facts: {fact_err}")
        
        print(f"  Body preview: {email_data['body'][:100]}..." if len(email_data['body']) > 100 else f"  Body: {email_data['body']}")
        
        # Check for phone call request
        if thread_id and conversation_manager:
            email_body = email_data.get('body', '')
            if conversation_manager.detect_phone_call_request(email_body):
                print(f"\n  {'!'*80}")
                print(f"  ⚠️  PHONE CALL REQUEST DETECTED!")
                print(f"  {'!'*80}")
                print(f"  The lawyer has requested a phone call in this email.")
                print(f"  Thread ID: {thread_id}")
                print(f"  Check the frontend for phone call notifications.")
                print(f"  {'!'*80}\n")
                conversation_manager.set_phone_call_requested(thread_id, True)
        
        # Generate reply with conversation context
        print(f"\n  Generating AI reply...")
        reply = generate_reply(agent, email_data, conversation_manager)
        
        if reply:
            print(f"  [OK] Generated reply ({len(reply)} characters)")
            
            if auto_reply:
                # Send reply
                print(f"  Sending reply...")
                if send_reply(email_data, reply, conversation_manager):
                    print(f"  [OK] Reply sent successfully!")
                    save_processed_email(email_data['uid'])
                    processed_count += 1
                else:
                    print(f"  [ERROR] Failed to send reply")
            else:
                # Just show the reply
                print(f"\n  {'=' * 60}")
                print(f"  GENERATED REPLY (not sent - auto-reply disabled):")
                print(f"  {'=' * 60}")
                print(f"  {reply}")
                print(f"  {'=' * 60}\n")
                save_processed_email(email_data['uid'])  # Mark as processed even in preview mode
                processed_count += 1
        else:
            print(f"  [WARNING] No reply generated")
    
    print(f"\n[{timestamp}] Finished processing emails.")
    print(f"  Processed: {processed_count}, Skipped: {skipped_count}\n")


def listen_loop(agent, conversation_manager=None, lawyer_tracker=None, check_interval: int = 60, auto_reply: bool = True):
    """
    Main loop to continuously check for emails.
    
    Args:
        agent: The email agent instance
        conversation_manager: Conversation manager instance (optional)
        lawyer_tracker: Lawyer tracker instance (optional)
        check_interval: Seconds between checks (default: 60)
        auto_reply: If True, automatically send replies
    """
    print("=" * 60)
    print("Email Listener Started")
    print("=" * 60)
    print(f"Checking every {check_interval} seconds")
    print(f"Auto-reply: {'ENABLED' if auto_reply else 'DISABLED (Preview Mode)'}")
    print(f"Email: {SENDER_EMAIL}")
    print(f"IMAP Server: {IMAP_SERVER}:{IMAP_PORT}")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    try:
        while True:
            process_emails(agent, conversation_manager=conversation_manager, lawyer_tracker=lawyer_tracker, auto_reply=auto_reply, verbose=True)
            time.sleep(check_interval)
            
    except KeyboardInterrupt:
        print("\n\n[INFO] Stopping email listener...")
        print("Goodbye!")


def main():
    """Main function to run the email listener."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Email listener and auto-responder")
    parser.add_argument("--interval", type=int, default=60, 
                       help="Check interval in seconds (default: 60)")
    parser.add_argument("--no-auto-reply", action="store_true",
                       help="Don't automatically send replies (just generate them)")
    parser.add_argument("--once", action="store_true",
                       help="Check once and exit (don't loop)")
    
    args = parser.parse_args()
    
    # Check configuration
    if SENDER_EMAIL == "your-email@gmail.com" or SENDER_PASSWORD == "your-app-password":
        print("[ERROR] Please configure SENDER_EMAIL and SENDER_PASSWORD in your .env file")
        return
    
    # Create agent
    print("Initializing email agent...")
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY not set in .env file")
        return
    
    agent = create_email_agent(api_key=api_key)
    print("[OK] Agent ready\n")
    
    if args.once:
        # Check once and exit
        process_emails(agent, auto_reply=not args.no_auto_reply)
    else:
        # Continuous loop
        listen_loop(agent, check_interval=args.interval, auto_reply=not args.no_auto_reply)


if __name__ == "__main__":
    main()

