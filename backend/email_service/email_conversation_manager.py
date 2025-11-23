"""
Conversation manager for tracking email threads and maintaining context.
"""

import os
import json
import email
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

CONVERSATIONS_FILE = "email_conversations.json"


class ConversationManager:
    """Manages email conversation threads and history."""
    
    def __init__(self):
        self.conversations = self._load_conversations()
    
    def _load_conversations(self) -> Dict:
        """Load conversation history from file."""
        if os.path.exists(CONVERSATIONS_FILE):
            try:
                with open(CONVERSATIONS_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_conversations(self):
        """Save conversation history to file."""
        with open(CONVERSATIONS_FILE, 'w') as f:
            json.dump(self.conversations, f, indent=2)
    
    def _get_thread_id(self, email_data: Dict) -> str:
        """
        Generate a thread ID from email data.
        Uses In-Reply-To, References, or subject line.
        """
        # Try to get thread from email headers
        msg_id = email_data.get('message_id', '')
        in_reply_to = email_data.get('in_reply_to', '')
        references = email_data.get('references', '')
        
        # If it's a reply, use the original message ID
        if in_reply_to:
            return in_reply_to
        
        # If it references other messages, use the first one
        if references:
            ref_ids = references.split()
            if ref_ids:
                return ref_ids[0]
        
        # Otherwise, create thread ID from subject (normalized)
        subject = email_data.get('subject', '').lower().strip()
        # Remove "Re:" and "Fwd:" prefixes
        subject = subject.replace('re:', '').replace('fwd:', '').strip()
        
        # Use sender + normalized subject as thread ID
        sender = email_data.get('from', '').lower().strip()
        return f"{sender}:{subject}"
    
    def add_email(self, email_data: Dict) -> str:
        """
        Add an email to conversation history.
        Returns the thread ID.
        """
        thread_id = self._get_thread_id(email_data)
        
        if thread_id not in self.conversations:
            self.conversations[thread_id] = {
                'thread_id': thread_id,
                'subject': email_data.get('subject', ''),
                'participants': [],  # Use list instead of set for JSON serialization
                'emails': [],
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
        
        # Add email to thread
        email_entry = {
            'from': email_data.get('from', ''),
            'to': email_data.get('to', ''),
            'subject': email_data.get('subject', ''),
            'body': email_data.get('body', ''),
            'date': email_data.get('date', ''),
            'uid': email_data.get('uid', ''),
            'timestamp': datetime.now().isoformat()
        }
        
        self.conversations[thread_id]['emails'].append(email_entry)
        
        # Add participant (convert to list immediately to avoid set serialization issues)
        participant = email_data.get('from', '').lower()
        participants_list = list(self.conversations[thread_id]['participants'])
        if participant not in participants_list:
            participants_list.append(participant)
        self.conversations[thread_id]['participants'] = participants_list
        
        self.conversations[thread_id]['updated_at'] = datetime.now().isoformat()
        
        self._save_conversations()
        return thread_id
    
    def get_conversation_history(self, thread_id: str, limit: int = 10) -> List[Dict]:
        """Get conversation history for a thread."""
        if thread_id not in self.conversations:
            return []
        
        emails = self.conversations[thread_id]['emails']
        # Return most recent emails
        return emails[-limit:]
    
    def get_conversation_context(self, thread_id: str) -> str:
        """
        Get formatted conversation context for AI agent.
        """
        if thread_id not in self.conversations:
            return ""
        
        conv = self.conversations[thread_id]
        emails = conv['emails']
        
        if not emails:
            return ""
        
        # Ensure participants is a list
        participants = conv.get('participants', [])
        if not isinstance(participants, list):
            participants = list(participants) if participants else []
        
        context_parts = [f"Conversation Thread: {conv['subject']}\n"]
        context_parts.append(f"Participants: {', '.join(participants)}\n")
        context_parts.append("\nPrevious messages in this thread:\n")
        
        for i, email_entry in enumerate(emails, 1):
            context_parts.append(f"\n--- Message {i} ({email_entry['date']}) ---")
            context_parts.append(f"From: {email_entry['from']}")
            context_parts.append(f"Subject: {email_entry['subject']}")
            context_parts.append(f"Body: {email_entry['body'][:500]}...")  # Limit body length
        
        return "\n".join(context_parts)
    
    def find_thread_by_email(self, email_data: Dict) -> Optional[str]:
        """Find thread ID for an email."""
        thread_id = self._get_thread_id(email_data)
        return thread_id if thread_id in self.conversations else None


def extract_email_headers(msg) -> Dict:
    """Extract email headers needed for threading."""
    return {
        'message_id': msg.get('Message-ID', ''),
        'in_reply_to': msg.get('In-Reply-To', ''),
        'references': msg.get('References', ''),
    }

