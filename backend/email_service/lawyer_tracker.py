"""
Tracks lawyer conversations and extracts key information for comparison.
"""

import os
import json
import re
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

load_dotenv()

LAWYERS_DATA_FILE = "lawyers_data.json"


@dataclass
class LawyerOffer:
    """Represents a lawyer's offer/quote."""
    lawyer_name: str
    lawyer_email: str
    firm_name: str = ""
    hourly_rate: Optional[float] = None
    flat_fee: Optional[float] = None
    contingency_rate: Optional[float] = None  # e.g., 33% for personal injury
    retainer_amount: Optional[float] = None
    estimated_total: Optional[float] = None
    payment_plan: str = ""
    experience_years: Optional[int] = None
    case_types: List[str] = None
    availability: str = ""
    response_time: str = ""
    terms: str = ""
    notes: str = ""
    first_contact_date: str = ""
    last_contact_date: str = ""
    email_count: int = 0
    thread_id: str = ""
    location: str = ""  # City, State or full address
    price_value: Optional[float] = None
    price_text: str = ""
    years_experience: Optional[int] = None  # Extracted from recent messages
    experience_text: str = ""
    location_text: str = ""
    rank_score: Optional[int] = None
    
    def __post_init__(self):
        if self.case_types is None:
            self.case_types = []


class LawyerTracker:
    """Tracks and manages lawyer offers."""
    
    def __init__(self):
        self.lawyers = self._load_lawyers()
    
    def _load_lawyers(self) -> Dict[str, LawyerOffer]:
        """Load lawyer data from file."""
        if os.path.exists(LAWYERS_DATA_FILE):
            try:
                with open(LAWYERS_DATA_FILE, 'r') as f:
                    data = json.load(f)
                    lawyers = {}
                    for email, lawyer_data in data.items():
                        lawyers[email] = LawyerOffer(**lawyer_data)
                    return lawyers
            except:
                return {}
        return {}
    
    def _save_lawyers(self):
        """Save lawyer data to file."""
        data = {}
        for email, lawyer in self.lawyers.items():
            data[email] = asdict(lawyer)
        
        with open(LAWYERS_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    
    def extract_lawyer_info(self, email_data: Dict, email_body: str) -> Optional[LawyerOffer]:
        """
        Extract lawyer information from an email.
        Uses AI-like pattern matching to find key terms.
        """
        from_email = email_data.get('from', '').lower()
        from_name = email_data.get('from_display', '')
        
        # Check if we already have this lawyer
        if from_email in self.lawyers:
            lawyer = self.lawyers[from_email]
            lawyer.last_contact_date = datetime.now().isoformat()
            lawyer.email_count += 1
        else:
            # Create new lawyer entry
            lawyer = LawyerOffer(
                lawyer_name=from_name.split('<')[0].strip() if '<' in from_name else from_name,
                lawyer_email=from_email,
                first_contact_date=datetime.now().isoformat(),
                last_contact_date=datetime.now().isoformat(),
                email_count=1
            )
        
        # Extract information from email body
        body_lower = email_body.lower()
        
        # Extract rates
        # Hourly rate patterns: "$200/hour", "$200/hr", "200 per hour"
        hourly_match = re.search(r'\$?(\d+)\s*(?:per\s*)?(?:hour|hr|/h)', body_lower)
        if hourly_match:
            lawyer.hourly_rate = float(hourly_match.group(1))
        
        # Flat fee patterns: "$5000 flat fee", "$5000 one-time", "flat fee of $5000"
        flat_fee_match = re.search(r'(?:flat\s*fee|one[\s-]?time|fixed\s*fee).*?\$?(\d+(?:,\d{3})*)', body_lower)
        if not flat_fee_match:
            flat_fee_match = re.search(r'\$(\d+(?:,\d{3})*)\s*(?:flat|one[\s-]?time|fixed)', body_lower)
        if flat_fee_match:
            lawyer.flat_fee = float(flat_fee_match.group(1).replace(',', ''))
        
        # Contingency rate patterns: "33% contingency", "contingency fee of 33%", "no win no fee"
        contingency_match = re.search(r'(\d+)\s*%?\s*(?:contingency|contingent)', body_lower)
        if contingency_match:
            lawyer.contingency_rate = float(contingency_match.group(1))
        elif 'no win no fee' in body_lower or 'contingency' in body_lower:
            # Default contingency if mentioned but not specified
            lawyer.contingency_rate = 33.0
        
        # Retainer patterns: "$2000 retainer", "retainer of $2000"
        retainer_match = re.search(r'(?:retainer|retain).*?\$?(\d+(?:,\d{3})*)', body_lower)
        if retainer_match:
            lawyer.retainer_amount = float(retainer_match.group(1).replace(',', ''))
        
        # Estimated total
        total_match = re.search(r'(?:estimated|total|cost).*?\$?(\d+(?:,\d{3})*)', body_lower)
        if total_match:
            lawyer.estimated_total = float(total_match.group(1).replace(',', ''))
        
        # Payment plan
        if 'payment plan' in body_lower or 'installment' in body_lower:
            lawyer.payment_plan = "Available"
        
        # Experience
        exp_match = re.search(r'(\d+)\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|practice)', body_lower)
        if exp_match:
            lawyer.experience_years = int(exp_match.group(1))
        
        # Case types
        case_type_keywords = {
            'personal injury': ['personal injury', 'car accident', 'slip and fall'],
            'family law': ['divorce', 'custody', 'family law', 'alimony'],
            'criminal': ['criminal', 'defense', 'dui', 'felony'],
            'business': ['business', 'corporate', 'contract', 'llc'],
            'real estate': ['real estate', 'property', 'landlord'],
            'employment': ['employment', 'discrimination', 'wrongful termination']
        }
        
        for case_type, keywords in case_type_keywords.items():
            if any(keyword in body_lower for keyword in keywords):
                if case_type not in lawyer.case_types:
                    lawyer.case_types.append(case_type)
        
        # Firm name
        firm_match = re.search(r'(?:firm|law\s*group|attorney|legal).*?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', email_body)
        if firm_match:
            lawyer.firm_name = firm_match.group(1)
        
        # Extract location (city, state patterns)
        # Patterns: "New York, NY", "Los Angeles, California", "Chicago, IL", "based in San Francisco"
        location_patterns = [
            r'(?:located|based|office|practicing|serving).*?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2}|[A-Z][a-z]+)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2}|[A-Z][a-z]+)',
            r'(?:in|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        ]
        for pattern in location_patterns:
            loc_match = re.search(pattern, email_body)
            if loc_match:
                if len(loc_match.groups()) >= 2:
                    lawyer.location = f"{loc_match.group(1)}, {loc_match.group(2)}"
                else:
                    lawyer.location = loc_match.group(1)
                break
        
        # Store thread ID if available
        if 'thread_id' in email_data:
            lawyer.thread_id = email_data['thread_id']
        
        # Store notes (first 500 chars of email)
        lawyer.notes = email_body[:500]
        
        return lawyer
    
    def add_lawyer_email(self, email_data: Dict, thread_id: str = ""):
        """Add or update lawyer information from an email."""
        email_body = email_data.get('body', '')
        email_data['thread_id'] = thread_id
        
        lawyer = self.extract_lawyer_info(email_data, email_body)
        if lawyer:
            self.lawyers[lawyer.lawyer_email] = lawyer
            self._save_lawyers()
            return lawyer
        return None
    
    def get_all_lawyers(self) -> List[LawyerOffer]:
        """Get all tracked lawyers."""
        return list(self.lawyers.values())
    
    def rank_lawyers(self, case_type: str = "", max_price: Optional[float] = None) -> List[LawyerOffer]:
        """
        Rank lawyers based on various factors.
        
        Args:
            case_type: Filter by case type
            max_price: Maximum price filter
        
        Returns:
            Ranked list of lawyers
        """
        lawyers = self.get_all_lawyers()
        
        # Filter by case type if specified
        if case_type:
            lawyers = [l for l in lawyers if case_type.lower() in [ct.lower() for ct in l.case_types]]
        
        # Filter by max price
        if max_price:
            lawyers = [l for l in lawyers if 
                      (l.estimated_total and l.estimated_total <= max_price) or
                      (l.flat_fee and l.flat_fee <= max_price) or
                      (l.hourly_rate and l.hourly_rate * 10 <= max_price)]  # Rough estimate
        
        # Score and rank
        scored_lawyers = []
        for lawyer in lawyers:
            score = self._calculate_score(lawyer)
            scored_lawyers.append((score, lawyer))
        
        # Sort by score (highest first)
        scored_lawyers.sort(key=lambda x: x[0], reverse=True)
        
        return [lawyer for score, lawyer in scored_lawyers]
    
    def _calculate_score(self, lawyer: LawyerOffer) -> float:
        """
        Calculate a score for ranking lawyers.
        Higher score = better option.
        """
        score = 0.0
        
        # Price factors (lower is better, but we want to balance with quality)
        if lawyer.flat_fee:
            # Lower flat fee = higher score (inverted)
            score += 1000 / max(lawyer.flat_fee, 1)
        elif lawyer.hourly_rate:
            # Lower hourly rate = higher score
            score += 100 / max(lawyer.hourly_rate, 1)
        elif lawyer.contingency_rate:
            # Lower contingency = higher score
            score += 100 / max(lawyer.contingency_rate, 1)
        
        # Experience (more is better)
        if lawyer.experience_years:
            score += lawyer.experience_years * 2
        
        # Responsiveness (more emails = more engagement)
        score += lawyer.email_count * 5
        
        # Payment plan availability
        if lawyer.payment_plan:
            score += 20
        
        return score

