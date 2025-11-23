"""
Database-backed lawyer tracker.
"""

from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from dataclasses import dataclass, asdict
import json

from backend.email_service.database import Lawyer, get_db_session, init_db
from backend.email_service.lawyer_tracker import LawyerOffer


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
            location=getattr(lawyer, 'location', '') or ""
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
            
            db.commit()
            return lawyer_offer
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def create_lawyer(self, lawyer_email: str, lawyer_name: str = "", thread_id: str = ""):
        """Create a basic lawyer entry (for initial contact tracking)."""
        db = get_db_session()
        try:
            lawyer = db.query(Lawyer).filter(
                Lawyer.lawyer_email == lawyer_email.lower()
            ).first()
            
            if not lawyer:
                lawyer = Lawyer(
                    lawyer_email=lawyer_email.lower(),
                    lawyer_name=lawyer_name,
                    first_contact_date=datetime.utcnow(),
                    last_contact_date=datetime.utcnow(),
                    email_count=1,
                    thread_id=thread_id,
                    case_types=[]
                )
                db.add(lawyer)
                db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def rank_lawyers(self, case_type: str = "", max_price: Optional[float] = None, user_location: Optional[str] = None) -> List[LawyerOffer]:
        """
        Rank lawyers based on three key metrics:
        1. Quote for service (pricing - lower is better)
        2. Years of experience (higher is better)
        3. Location-based (closer is better)
        
        Args:
            case_type: Optional case type filter
            max_price: Optional maximum price filter
            user_location: Optional user location for location-based ranking (e.g., "New York, NY")
        
        Returns:
            List of ranked LawyerOffer objects
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
                      (l.hourly_rate and l.hourly_rate * 10 <= max_price)]
        
        if not lawyers:
            return []
        
        # Calculate normalized scores for each metric
        scored_lawyers = []
        for lawyer in lawyers:
            score_data = self._calculate_ranking_score(lawyer, lawyers, user_location)
            scored_lawyers.append((score_data['total_score'], score_data, lawyer))
        
        # Sort by total score (highest first)
        scored_lawyers.sort(key=lambda x: x[0], reverse=True)
        return [lawyer for score, score_data, lawyer in scored_lawyers]
    
    def _calculate_ranking_score(self, lawyer: LawyerOffer, all_lawyers: List[LawyerOffer], user_location: Optional[str] = None) -> Dict:
        """
        Calculate normalized ranking score based on three metrics:
        1. Quote (price) - normalized 0-1, lower is better
        2. Experience - normalized 0-1, higher is better
        3. Location - normalized 0-1, closer is better (or 0.5 if no location data)
        
        Returns dict with individual scores and total_score.
        """
        # 1. PRICE SCORE (lower is better, normalized 0-1)
        price_score = 0.0
        lawyer_price = None
        
        # Get the best available price metric
        if lawyer.flat_fee:
            lawyer_price = lawyer.flat_fee
        elif lawyer.estimated_total:
            lawyer_price = lawyer.estimated_total
        elif lawyer.hourly_rate:
            lawyer_price = lawyer.hourly_rate * 10  # Rough estimate for 10 hours
        elif lawyer.retainer_amount:
            lawyer_price = lawyer.retainer_amount * 2  # Rough estimate
        
        if lawyer_price:
            # Get price range from all lawyers
            all_prices = []
            for l in all_lawyers:
                p = None
                if l.flat_fee:
                    p = l.flat_fee
                elif l.estimated_total:
                    p = l.estimated_total
                elif l.hourly_rate:
                    p = l.hourly_rate * 10
                elif l.retainer_amount:
                    p = l.retainer_amount * 2
                if p:
                    all_prices.append(p)
            
            if all_prices:
                min_price = min(all_prices)
                max_price = max(all_prices)
                if max_price > min_price:
                    # Normalize: lower price = higher score (inverted)
                    price_score = 1.0 - ((lawyer_price - min_price) / (max_price - min_price))
                else:
                    price_score = 1.0
        else:
            # No price data = neutral score
            price_score = 0.5
        
        # 2. EXPERIENCE SCORE (higher is better, normalized 0-1)
        experience_score = 0.0
        if lawyer.experience_years:
            # Get experience range from all lawyers
            all_experience = [l.experience_years for l in all_lawyers if l.experience_years]
            if all_experience:
                min_exp = min(all_experience)
                max_exp = max(all_experience)
                if max_exp > min_exp:
                    # Normalize: higher experience = higher score
                    experience_score = (lawyer.experience_years - min_exp) / (max_exp - min_exp)
                else:
                    experience_score = 1.0
            else:
                experience_score = 0.5
        else:
            # No experience data = neutral score
            experience_score = 0.3
        
        # 3. LOCATION SCORE (closer is better, normalized 0-1)
        location_score = 0.5  # Default neutral score
        if user_location and lawyer.location:
            # Simple location matching (exact match = 1.0, same state = 0.7, different = 0.3)
            user_loc_lower = user_location.lower().strip()
            lawyer_loc_lower = lawyer.location.lower().strip()
            
            if user_loc_lower == lawyer_loc_lower:
                location_score = 1.0
            elif user_loc_lower in lawyer_loc_lower or lawyer_loc_lower in user_loc_lower:
                location_score = 0.9
            else:
                # Extract state/city for partial matching
                user_parts = [p.strip() for p in user_loc_lower.split(',')]
                lawyer_parts = [p.strip() for p in lawyer_loc_lower.split(',')]
                
                # Check if same state
                if len(user_parts) > 1 and len(lawyer_parts) > 1:
                    if user_parts[-1] == lawyer_parts[-1]:  # Same state
                        location_score = 0.7
                    else:
                        location_score = 0.3
                else:
                    location_score = 0.5
        elif lawyer.location:
            # Has location but no user location = slight bonus
            location_score = 0.6
        else:
            # No location data = neutral
            location_score = 0.5
        
        # Weighted total score (can adjust weights)
        # Default: 40% price, 35% experience, 25% location
        total_score = (
            price_score * 0.40 +
            experience_score * 0.35 +
            location_score * 0.25
        )
        
        return {
            'price_score': price_score,
            'experience_score': experience_score,
            'location_score': location_score,
            'total_score': total_score
        }

