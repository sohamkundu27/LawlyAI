"""
Database-backed lawyer tracker.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from backend.email_service.database import Lawyer, get_db_session, init_db
from backend.email_service.lawyer_tracker import LawyerOffer

# Baselines for ranking
BASELINE_PRICE = 400.0
BASELINE_EXPERIENCE = 10


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def extract_lawyer_facts_from_message(body: str) -> Dict[str, Optional[object]]:
    """
    Extract price, experience, and location snippets from a single email body.
    Returns dict with price_value (float), price_text, years_experience (int),
    experience_text, location_text.
    """
    if not body:
        return {
            "price_value": None,
            "price_text": None,
            "years_experience": None,
            "experience_text": None,
            "location_text": None,
        }
    
    price_value = None
    price_text = None
    years_experience = None
    experience_text = None
    location_text = None
    
    text = body
    lower_text = body.lower()
    
    # Price extraction heuristics
    price_patterns = [
        # Hourly rates (e.g., $250/hour, 300 per hour)
        (re.compile(r'(\$?\s*\d[\d,]*)(?:\s*(?:per)?\s*(?:hour|hr|/hour|/hr))', re.IGNORECASE), "hourly"),
        # Flat fees (e.g., flat fee of $2,000)
        (re.compile(r'(?:flat\s+fee(?:\s+of)?|fixed\s+fee|one[-\s]?time\s+fee).*?(\$?\s*\d[\d,]*)', re.IGNORECASE), "flat"),
        # Contingency (e.g., 33% contingency)
        (re.compile(r'(\d{1,2})\s*%[^.\n]*(?:contingency|contingent)', re.IGNORECASE), "contingency"),
    ]
    
    for pattern, price_type in price_patterns:
        match = pattern.search(text)
        if not match:
            continue
        price_text = match.group(0).strip()
        numeric_part = match.group(1) if match.groups() else None
        if price_type == "contingency":
            # Use baseline as neutral numeric representation for contingency fees
            price_value = BASELINE_PRICE
        else:
            if numeric_part:
                digits = re.sub(r'[^\d.]', '', numeric_part)
                if digits:
                    value = float(digits)
                    if price_type == "flat":
                        # Roughly convert flat fees into an hourly-esque figure
                        price_value = value / 10.0
                    else:
                        price_value = value
        if price_text:
            break
    
    # Years of experience
    experience_patterns = [
        # "20 years of experience", "15 yrs practice"
        re.compile(r'(\d{1,2})\s*(?:\+?\s*)?(?:years?|yrs?)\s*(?:of\s+)?(?:experience|practice)', re.IGNORECASE),
        # "practicing since 2004"
        re.compile(r'(?:since|from)\s+(19\d{2}|20\d{2})', re.IGNORECASE),
    ]
    for pattern in experience_patterns:
        match = pattern.search(text)
        if not match:
            continue
        experience_text = match.group(0).strip()
        if pattern == experience_patterns[0]:
            years = int(match.group(1))
            if 0 < years < 80:
                years_experience = years
                break
        else:
            year = int(match.group(1))
            current_year = datetime.utcnow().year
            years = current_year - year
            if years > 0:
                years_experience = years
                break
    
    # Location extraction (prefer explicit City, ST)
    location_patterns = [
        re.compile(r'(?:based|located|offices?|practic(?:e|ing)|serving)\s+(?:in|out of)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)(?:,\s*([A-Z]{2}|[A-Z][a-z]+))?', re.IGNORECASE),
        re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2}|[A-Z][a-z]+)'),
    ]
    for pattern in location_patterns:
        match = pattern.search(text)
        if not match:
            continue
        groups = [g for g in match.groups() if g]
        if groups:
            location_text = ", ".join(groups)
            break
    
    return {
        "price_value": price_value,
        "price_text": price_text,
        "years_experience": years_experience,
        "experience_text": experience_text,
        "location_text": location_text,
    }


def compute_overall_score(price_value: Optional[float], years_experience: Optional[int], has_location: bool = False) -> Tuple[float, int]:
    """
    Compute overall float score (0-100) plus rounded rank_score based on price and experience.
    If neither metric is available, returns (0, 0) unless location exists, which gives a neutral score.
    """
    if price_value is None and years_experience is None:
        if has_location:
            return 50.0, 50
        return 0.0, 0
    
    if price_value is None:
        price_score = 50.0
    else:
        ratio = clamp(BASELINE_PRICE / max(price_value, 1e-6), 0.0, 2.0)
        price_score = clamp(ratio * 50.0 + 50.0, 0.0, 100.0)
    
    if years_experience is None:
        experience_score = 50.0
    else:
        exp_ratio = clamp(years_experience / BASELINE_EXPERIENCE, 0.0, 2.0)
        experience_score = clamp(exp_ratio * 50.0, 0.0, 100.0)
    
    overall = (price_score + experience_score) / 2.0
    return overall, int(round(overall))


class LawyerTrackerDB:
    """Tracks and manages lawyer offers using database."""
    
    def __init__(self):
        # Initialize database on first use
        init_db()
    
    def _lawyer_to_offer(self, lawyer: Lawyer) -> LawyerOffer:
        """Convert database Lawyer to LawyerOffer dataclass."""
        return LawyerOffer(
            lawyer_name=lawyer.lawyer_name or "",
            lawyer_email=lawyer.lawyer_email,
            firm_name=lawyer.firm_name or "",
            hourly_rate=lawyer.hourly_rate,
            flat_fee=lawyer.flat_fee,
            contingency_rate=lawyer.contingency_rate,
            retainer_amount=lawyer.retainer_amount,
            estimated_total=lawyer.estimated_total,
            payment_plan=lawyer.payment_plan or "",
            experience_years=lawyer.experience_years,
            case_types=lawyer.case_types or [],
            availability=lawyer.availability or "",
            response_time=lawyer.response_time or "",
            terms=lawyer.terms or "",
            notes=lawyer.notes or "",
            first_contact_date=lawyer.first_contact_date.isoformat() if lawyer.first_contact_date else "",
            last_contact_date=lawyer.last_contact_date.isoformat() if lawyer.last_contact_date else "",
            email_count=lawyer.email_count or 0,
            thread_id=lawyer.thread_id or "",
            location=getattr(lawyer, 'location', '') or "",
            price_value=getattr(lawyer, 'price_value', None),
            price_text=getattr(lawyer, 'price_text', '') or "",
            years_experience=getattr(lawyer, 'years_experience', None),
            experience_text=getattr(lawyer, 'experience_text', '') or "",
            location_text=getattr(lawyer, 'location_text', '') or "",
            rank_score=getattr(lawyer, 'rank_score', None),
        )
    
    def get_all_lawyers(self) -> List[LawyerOffer]:
        """Get all tracked lawyers."""
        db = get_db_session()
        try:
            lawyers = db.query(Lawyer).all()
            return [self._lawyer_to_offer(lawyer) for lawyer in lawyers]
        finally:
            db.close()
    
    def add_lawyer_email(self, email_data: Dict, thread_id: str = ""):
        """Add or update lawyer information from an email."""
        from backend.email_service.lawyer_tracker import LawyerTracker
        
        # Use the original extract_lawyer_info logic
        original_tracker = LawyerTracker()
        lawyer_offer = original_tracker.extract_lawyer_info(
            email_data, 
            email_data.get('body', '')
        )
        
        if not lawyer_offer:
            return None
        
        # Save to database
        db = get_db_session()
        try:
            lawyer = db.query(Lawyer).filter(
                Lawyer.lawyer_email == lawyer_offer.lawyer_email.lower()
            ).first()
            
            if lawyer:
                # Update existing
                lawyer.lawyer_name = lawyer_offer.lawyer_name
                lawyer.firm_name = lawyer_offer.firm_name
                lawyer.hourly_rate = lawyer_offer.hourly_rate
                lawyer.flat_fee = lawyer_offer.flat_fee
                lawyer.contingency_rate = lawyer_offer.contingency_rate
                lawyer.retainer_amount = lawyer_offer.retainer_amount
                lawyer.estimated_total = lawyer_offer.estimated_total
                lawyer.payment_plan = lawyer_offer.payment_plan
                lawyer.experience_years = lawyer_offer.experience_years
                lawyer.case_types = lawyer_offer.case_types
                lawyer.availability = lawyer_offer.availability
                lawyer.response_time = lawyer_offer.response_time
                lawyer.terms = lawyer_offer.terms
                lawyer.notes = lawyer_offer.notes
                lawyer.location = lawyer_offer.location
                lawyer.last_contact_date = datetime.utcnow()
                lawyer.email_count = (lawyer.email_count or 0) + 1
                lawyer.thread_id = thread_id or lawyer.thread_id
            else:
                # Create new
                lawyer = Lawyer(
                    lawyer_email=lawyer_offer.lawyer_email.lower(),
                    lawyer_name=lawyer_offer.lawyer_name,
                    firm_name=lawyer_offer.firm_name,
                    hourly_rate=lawyer_offer.hourly_rate,
                    flat_fee=lawyer_offer.flat_fee,
                    contingency_rate=lawyer_offer.contingency_rate,
                    retainer_amount=lawyer_offer.retainer_amount,
                    estimated_total=lawyer_offer.estimated_total,
                    payment_plan=lawyer_offer.payment_plan,
                    experience_years=lawyer_offer.experience_years,
                    case_types=lawyer_offer.case_types,
                    availability=lawyer_offer.availability,
                    response_time=lawyer_offer.response_time,
                    terms=lawyer_offer.terms,
                    notes=lawyer_offer.notes,
                    location=lawyer_offer.location,
                    first_contact_date=datetime.utcnow(),
                    last_contact_date=datetime.utcnow(),
                    email_count=1,
                    thread_id=thread_id
                )
                db.add(lawyer)
            
            self._update_rank_score(lawyer)
            db.commit()
            return lawyer_offer
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def create_lawyer(
        self, 
        lawyer_email: str, 
        lawyer_name: str = "", 
        thread_id: str = "", 
        firm_name: str = ""
    ):
        """Create or update a basic lawyer entry (for initial contact tracking)."""
        db = get_db_session()
        try:
            lawyer = db.query(Lawyer).filter(
                Lawyer.lawyer_email == lawyer_email.lower()
            ).first()
            
            if not lawyer:
                lawyer = Lawyer(
                    lawyer_email=lawyer_email.lower(),
                    lawyer_name=lawyer_name,
                    firm_name=firm_name,
                    first_contact_date=datetime.utcnow(),
                    last_contact_date=datetime.utcnow(),
                    email_count=1,
                    thread_id=thread_id,
                    case_types=[]
                )
                db.add(lawyer)
                db.commit()
            else:
                updated = False
                if lawyer_name and lawyer.lawyer_name != lawyer_name:
                    lawyer.lawyer_name = lawyer_name
                    updated = True
                if firm_name and (lawyer.firm_name or "") != firm_name:
                    lawyer.firm_name = firm_name
                    updated = True
                if thread_id and not lawyer.thread_id:
                    lawyer.thread_id = thread_id
                    updated = True
                if updated:
                    db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def update_lawyer_facts_from_message(self, lawyer_email: str, email_body: str) -> bool:
        """
        Extract facts from a message and persist them if we don't already have values.
        Returns True if any field (or the rank score) changed.
        """
        if not lawyer_email or not email_body:
            return False
        
        facts = extract_lawyer_facts_from_message(email_body)
        if not any(facts.values()):
            return False
        
        db = get_db_session()
        try:
            lawyer = db.query(Lawyer).filter(
                Lawyer.lawyer_email == lawyer_email.lower().strip()
            ).first()
            if not lawyer:
                return False
            
            changed = False
            if facts.get("price_value") is not None and lawyer.price_value is None:
                lawyer.price_value = facts["price_value"]
                lawyer.price_text = facts.get("price_text") or ""
                changed = True
            elif facts.get("price_text") and not (lawyer.price_text or "").strip():
                lawyer.price_text = facts["price_text"]
                changed = True
            
            if facts.get("years_experience") is not None and lawyer.years_experience is None:
                lawyer.years_experience = facts["years_experience"]
                lawyer.experience_text = facts.get("experience_text") or ""
                changed = True
            elif facts.get("experience_text") and not (lawyer.experience_text or "").strip():
                lawyer.experience_text = facts["experience_text"]
                changed = True
            
            if facts.get("location_text") and not (lawyer.location_text or "").strip():
                lawyer.location_text = facts["location_text"]
                changed = True
            
            if not changed:
                return False
            
            self._update_rank_score(lawyer)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    
    def _update_rank_score(self, lawyer: Lawyer):
        """Recompute and store the latest rank_score for a lawyer."""
        has_location = bool((getattr(lawyer, "location_text", "") or "").strip())
        _, rank_score = compute_overall_score(
            getattr(lawyer, "price_value", None),
            getattr(lawyer, "years_experience", None),
            has_location=has_location,
        )
        lawyer.rank_score = rank_score
    
    def rank_lawyers(self, case_type: str = "", max_price: Optional[float] = None, user_location: Optional[str] = None) -> List[LawyerOffer]:
        """
        Rank lawyers by extracted fact-based score first, then fall back to remaining entries.
        """
        _ = user_location  # Currently unused but kept for signature compatibility
        lawyers = self.get_all_lawyers()
        
        if case_type:
            lawyers = [l for l in lawyers if case_type.lower() in [ct.lower() for ct in l.case_types]]
        
        if max_price:
            lawyers = [
                l for l in lawyers
                if (l.estimated_total and l.estimated_total <= max_price)
                or (l.flat_fee and l.flat_fee <= max_price)
                or (l.hourly_rate and l.hourly_rate * 10 <= max_price)
            ]
        
        fact_enriched = [l for l in lawyers if (l.rank_score or 0) > 0]
        fallback = [l for l in lawyers if (l.rank_score or 0) == 0]
        
        fact_enriched.sort(key=lambda l: l.rank_score or 0, reverse=True)
        # For fallback entries (no email-derived facts yet), keep deterministic order (e.g., most emails first)
        fallback.sort(key=lambda l: l.email_count, reverse=True)
        
        return fact_enriched + fallback

