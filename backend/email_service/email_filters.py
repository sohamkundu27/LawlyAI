"""
Email filtering system to skip unwanted emails.
"""

from typing import Dict, List
import re


class EmailFilter:
    """Filters emails based on various criteria."""
    
    def __init__(self):
        # Common system/no-reply addresses to skip
        self.system_domains = [
            'no-reply@',
            'noreply@',
            'donotreply@',
            'mailer-daemon@',
            'postmaster@',
            'automated@',
            'notification@',
            'notifications@',
        ]
        
        # Common system email patterns
        self.system_patterns = [
            r'security.*alert',
            r'account.*notification',
            r'password.*reset',
            r'verification.*code',
            r'welcome.*email',
            r'unsubscribe',
        ]
        
        # Whitelist - always process these (optional)
        self.whitelist = []
        
        # Blacklist - never process these (optional)
        self.blacklist = []
    
    def should_process(self, email_data: Dict) -> tuple[bool, str]:
        """
        Determine if an email should be processed.
        
        Returns:
            (should_process: bool, reason: str)
        """
        from_addr = email_data.get('from', '').lower()
        subject = email_data.get('subject', '').lower()
        
        # Check whitelist first
        if self.whitelist:
            for pattern in self.whitelist:
                if pattern.lower() in from_addr or pattern.lower() in subject:
                    return True, "Whitelisted"
        
        # Check blacklist
        if self.blacklist:
            for pattern in self.blacklist:
                if pattern.lower() in from_addr or pattern.lower() in subject:
                    return False, f"Blacklisted: {pattern}"
        
        # Check for system emails
        for domain in self.system_domains:
            if domain in from_addr:
                return False, f"System email from {domain}"
        
        # Check for system email patterns in subject
        for pattern in self.system_patterns:
            if re.search(pattern, subject, re.IGNORECASE):
                return False, f"System notification pattern: {pattern}"
        
        # Default: process the email
        return True, "OK"
    
    def add_to_whitelist(self, pattern: str):
        """Add a pattern to the whitelist."""
        if pattern not in self.whitelist:
            self.whitelist.append(pattern)
    
    def add_to_blacklist(self, pattern: str):
        """Add a pattern to the blacklist."""
        if pattern not in self.blacklist:
            self.blacklist.append(pattern)
    
    def remove_from_whitelist(self, pattern: str):
        """Remove a pattern from the whitelist."""
        if pattern in self.whitelist:
            self.whitelist.remove(pattern)
    
    def remove_from_blacklist(self, pattern: str):
        """Remove a pattern from the blacklist."""
        if pattern in self.blacklist:
            self.blacklist.remove(pattern)


# Global filter instance
default_filter = EmailFilter()

