"""
Database-backed conversation manager for tracking email threads.
"""

from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.email_service.database import (
    EmailThread, EmailMessage, get_db_session, init_db
)


class ConversationManagerDB:
    """Manages email conversation threads using database."""
    
    def __init__(self):
        # Initialize database on first use
        init_db()
    
    def _get_thread_id(self, email_data: Dict) -> str:
        """
        Generate a thread ID from email data.
        Uses In-Reply-To, References, or subject line.
        """
        # Try to get thread from email headers
        msg_id = email_data.get('message_id', '')
        in_reply_to = email_data.get('in_reply_to', '')
        references = email_data.get('references', '')
        
        # If it's a reply, try to find the existing thread by looking up the message
        # But also prepare fallback to participants+subject matching
        if in_reply_to or references:
            db = get_db_session()
            try:
                # Try to find a message with this in_reply_to or in references
                message_id_to_find = in_reply_to or (references.split()[0] if references else '')
                if message_id_to_find:
                    existing_msg = db.query(EmailMessage).filter(
                        EmailMessage.message_id == message_id_to_find
                    ).first()
                    if existing_msg:
                        # Found the original message, use its thread_id
                        return existing_msg.thread_id
                    
                    # Also check if in_reply_to matches any message_id in the database
                    # Sometimes in_reply_to might be a different format
                    existing_msg = db.query(EmailMessage).filter(
                        EmailMessage.message_id.like(f"%{message_id_to_find}%")
                    ).first()
                    if existing_msg:
                        return existing_msg.thread_id
            finally:
                db.close()
            # If we couldn't find by message_id, fall through to participants+subject matching
            # But first, try to find an existing thread by participants+subject
            db = get_db_session()
            try:
                subject = email_data.get('subject', '').lower().strip()
                subject = subject.replace('re:', '').replace('fwd:', '').strip()
                sender = email_data.get('from', '').lower().strip()
                recipient = email_data.get('to', '').lower().strip()
                participants = sorted([p for p in [sender, recipient] if p])
                participants_str = ':'.join(participants)
                potential_thread_id = f"{participants_str}:{subject}"
                
                # Check if a thread with this ID already exists
                existing_thread = db.query(EmailThread).filter(
                    EmailThread.thread_id == potential_thread_id
                ).first()
                if existing_thread:
                    return potential_thread_id
            finally:
                db.close()
        
        # Otherwise, create thread ID from participants and subject (normalized)
        subject = email_data.get('subject', '').lower().strip()
        # Remove "Re:" and "Fwd:" prefixes
        subject = subject.replace('re:', '').replace('fwd:', '').strip()
        
        # Use both sender and recipient to create unique thread per conversation pair
        # This ensures each lawyer gets their own thread
        sender = email_data.get('from', '').lower().strip()
        recipient = email_data.get('to', '').lower().strip()
        
        # Create thread ID from both participants (sorted for consistency) and subject
        # This ensures each lawyer conversation is separate
        participants = sorted([p for p in [sender, recipient] if p])
        participants_str = ':'.join(participants)
        return f"{participants_str}:{subject}"
    
    def add_email(self, email_data: Dict) -> str:
        """
        Add an email to conversation history.
        Returns the thread ID.
        """
        db = get_db_session()
        try:
            thread_id = self._get_thread_id(email_data)
            
            # Get or create thread
            thread = db.query(EmailThread).filter(EmailThread.thread_id == thread_id).first()
            
            if not thread:
                # Create new thread - add both from and to as participants
                participants = []
                from_email = email_data.get('from', '').lower().strip()
                to_email = email_data.get('to', '').lower().strip()
                if from_email:
                    participants.append(from_email)
                if to_email and to_email not in participants:
                    participants.append(to_email)
                
                thread = EmailThread(
                    thread_id=thread_id,
                    subject=email_data.get('subject', ''),
                    participants=participants,
                    manual_mode=0,  # Default to auto mode
                    phone_call_requested=0,  # Default to no phone call request
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(thread)
            else:
                # Update existing thread
                thread.updated_at = datetime.utcnow()
                # Add both from and to participants if not already in list
                participants = thread.participants or []
                from_email = email_data.get('from', '').lower().strip()
                to_email = email_data.get('to', '').lower().strip()
                
                if from_email and from_email not in participants:
                    participants.append(from_email)
                if to_email and to_email not in participants:
                    participants.append(to_email)
                
                thread.participants = participants
            
            # Check for duplicate email before adding
            # Check by UID first (for received emails), then by message_id, then by from/to/subject/body
            uid = email_data.get('uid', '')
            message_id = email_data.get('message_id', '')
            from_email = email_data.get('from', '')
            to_email = email_data.get('to', '')
            subject = email_data.get('subject', '')
            body = email_data.get('body', '')
            
            existing_email = None
            if uid:
                # Check by UID (for received emails)
                existing_email = db.query(EmailMessage).filter(
                    EmailMessage.uid == uid,
                    EmailMessage.thread_id == thread_id
                ).first()
            elif message_id:
                # Check by message_id
                existing_email = db.query(EmailMessage).filter(
                    EmailMessage.message_id == message_id,
                    EmailMessage.thread_id == thread_id
                ).first()
            else:
                # For sent emails without UID/message_id, check by from/to/subject/body in this thread
                # Also check if a very similar email was saved recently (within last 2 minutes)
                # to prevent rapid duplicate saves
                from datetime import timedelta
                recent_cutoff = datetime.utcnow() - timedelta(minutes=2)
                
                existing_email = db.query(EmailMessage).filter(
                    EmailMessage.thread_id == thread_id,
                    EmailMessage.from_email == from_email,
                    EmailMessage.to_email == to_email,
                    EmailMessage.subject == subject,
                    EmailMessage.body == body
                ).first()
                
                # If not found, also check for very recent similar emails (same from/to/subject, within 2 min)
                # This catches cases where the same email is saved multiple times rapidly
                if not existing_email:
                    existing_email = db.query(EmailMessage).filter(
                        EmailMessage.thread_id == thread_id,
                        EmailMessage.from_email == from_email,
                        EmailMessage.to_email == to_email,
                        EmailMessage.subject == subject,
                        EmailMessage.timestamp >= recent_cutoff
                    ).first()
            
            if existing_email:
                # Email already exists, skip adding duplicate
                return thread_id
            
            # Create email message
            email_msg = EmailMessage(
                thread_id=thread_id,
                from_email=from_email,
                to_email=to_email,
                subject=subject,
                body=body,
                date=email_data.get('date', ''),
                uid=uid,
                message_id=message_id,
                in_reply_to=email_data.get('in_reply_to', ''),
                references=email_data.get('references', ''),
                timestamp=datetime.utcnow()
            )
            db.add(email_msg)
            
            db.commit()
            return thread_id
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def get_conversation_history(self, thread_id: str, limit: int = 10) -> List[Dict]:
        """Get conversation history for a thread."""
        db = get_db_session()
        try:
            messages = db.query(EmailMessage)\
                .filter(EmailMessage.thread_id == thread_id)\
                .order_by(EmailMessage.timestamp)\
                .limit(limit)\
                .all()
            
            return [{
                'from': msg.from_email,
                'to': msg.to_email,
                'subject': msg.subject,
                'body': msg.body,
                'date': msg.date,
                'uid': msg.uid,
                'timestamp': msg.timestamp.isoformat() if msg.timestamp else None
            } for msg in messages]
        finally:
            db.close()
    
    def get_conversation_context(self, thread_id: str) -> str:
        """
        Get formatted conversation context for AI agent.
        """
        db = get_db_session()
        try:
            thread = db.query(EmailThread).filter(EmailThread.thread_id == thread_id).first()
            if not thread:
                return ""
            
            messages = db.query(EmailMessage)\
                .filter(EmailMessage.thread_id == thread_id)\
                .order_by(EmailMessage.timestamp)\
                .all()
            
            if not messages:
                return ""
            
            participants = thread.participants or []
            
            context_parts = [f"Conversation Thread: {thread.subject}\n"]
            context_parts.append(f"Participants: {', '.join(participants)}\n")
            context_parts.append("\nPrevious messages in this thread:\n")
            
            for i, msg in enumerate(messages, 1):
                context_parts.append(f"\n--- Message {i} ({msg.date}) ---")
                context_parts.append(f"From: {msg.from_email}")
                context_parts.append(f"Subject: {msg.subject}")
                context_parts.append(f"Body: {msg.body[:500] if msg.body else ''}...")
            
            return "\n".join(context_parts)
        finally:
            db.close()
    
    def find_thread_by_email(self, email_data: Dict) -> Optional[str]:
        """Find thread ID for an email."""
        thread_id = self._get_thread_id(email_data)
        db = get_db_session()
        try:
            thread = db.query(EmailThread).filter(EmailThread.thread_id == thread_id).first()
            return thread_id if thread else None
        finally:
            db.close()
    
    def get_all_conversations(self) -> Dict:
        """Get all conversations (for API compatibility)."""
        db = get_db_session()
        try:
            threads = db.query(EmailThread).all()
            conversations = {}
            
            for thread in threads:
                messages = db.query(EmailMessage)\
                    .filter(EmailMessage.thread_id == thread.thread_id)\
                    .order_by(EmailMessage.timestamp)\
                    .all()
                
                conversations[thread.thread_id] = {
                    'thread_id': thread.thread_id,
                    'subject': thread.subject,
                    'participants': thread.participants or [],
                    'manual_mode': bool(thread.manual_mode) if thread.manual_mode is not None else False,
                    'phone_call_requested': bool(thread.phone_call_requested) if thread.phone_call_requested is not None else False,
                    'emails': [{
                        'from': msg.from_email,
                        'to': msg.to_email,
                        'subject': msg.subject,
                        'body': msg.body,
                        'date': msg.date,
                        'uid': msg.uid,
                        'timestamp': msg.timestamp.isoformat() if msg.timestamp else None
                    } for msg in messages],
                    'created_at': thread.created_at.isoformat() if thread.created_at else None,
                    'updated_at': thread.updated_at.isoformat() if thread.updated_at else None
                }
            
            return conversations
        finally:
            db.close()
    
    def set_manual_mode(self, thread_id: str, manual_mode: bool) -> bool:
        """Set manual mode for a thread (pause auto-replies)."""
        db = get_db_session()
        try:
            thread = db.query(EmailThread).filter(EmailThread.thread_id == thread_id).first()
            if thread:
                thread.manual_mode = 1 if manual_mode else 0
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def is_manual_mode(self, thread_id: str) -> bool:
        """Check if a thread is in manual mode."""
        db = get_db_session()
        try:
            thread = db.query(EmailThread).filter(EmailThread.thread_id == thread_id).first()
            if thread:
                return bool(thread.manual_mode) if thread.manual_mode is not None else False
            return False
        finally:
            db.close()
    
    def detect_phone_call_request(self, email_body: str) -> bool:
        """Detect if email contains a phone call request."""
        body_lower = email_body.lower()
        phone_call_keywords = [
            'call me', 'phone call', 'give me a call', 'let\'s call', 'can we call',
            'schedule a call', 'hop on a call', 'jump on a call', 'quick call',
            'talk on the phone', 'speak on the phone', 'phone conversation',
            'call you', 'call us', 'reach me at', 'call at', 'phone number'
        ]
        return any(keyword in body_lower for keyword in phone_call_keywords)
    
    def set_phone_call_requested(self, thread_id: str, requested: bool) -> bool:
        """Mark a thread as having a phone call request."""
        db = get_db_session()
        try:
            thread = db.query(EmailThread).filter(EmailThread.thread_id == thread_id).first()
            if thread:
                thread.phone_call_requested = 1 if requested else 0
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def _load_conversations(self) -> Dict:
        """Compatibility method - returns all conversations."""
        return self.get_all_conversations()
    
    @property
    def conversations(self) -> Dict:
        """Property for compatibility with old code."""
        return self.get_all_conversations()

