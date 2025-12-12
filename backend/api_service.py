"""
FastAPI application for Hybrid Legal Search.

Run with:
    uvicorn backend.main:app --reload
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import os

# Optional imports - hybrid search is optional
try:
    from backend.hybrid_search import HybridSearcher
    HYBRID_SEARCH_AVAILABLE = True
except ImportError:
    HYBRID_SEARCH_AVAILABLE = False
    HybridSearcher = None

# Use database-backed managers
from backend.email_service.conversation_manager_db import ConversationManagerDB as ConversationManager
from backend.email_service.lawyer_tracker_db import LawyerTrackerDB as LawyerTracker
from backend.email_service.email_agent import create_email_agent
import threading

app = FastAPI(title="LawlyAI Email Service API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
searcher: Optional[HybridSearcher] = None
conversation_manager: Optional[ConversationManager] = None
lawyer_tracker: Optional[LawyerTracker] = None
email_agent = None
listener_thread = None

@app.on_event("startup")
def startup_event():
    """
    Initialize services on startup.
    """
    global searcher, conversation_manager, lawyer_tracker
    
    # Initialize HybridSearcher (optional - only if available)
    if HYBRID_SEARCH_AVAILABLE:
        dataset_path = "./vectorized_dataset"
        if not os.path.exists(dataset_path):
            print(f"INFO: Dataset path '{dataset_path}' not found. Hybrid search disabled.")
        else:
            try:
                searcher = HybridSearcher(dataset_path=dataset_path)
                print("Hybrid search initialized")
            except Exception as e:
                print(f"Warning: Could not initialize hybrid search: {e}")
    else:
        print("INFO: Hybrid search not available (dependencies not installed). Email service will work normally.")
    
    # Initialize email services
    try:
        # Initialize database first
        from backend.email_service.database import init_db
        init_db()
        print("✅ Database initialized")
        
        conversation_manager = ConversationManager()
        lawyer_tracker = LawyerTracker()
        print("✅ Email services initialized")
        
        # Initialize email agent if API key is available
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if api_key:
            global email_agent
            email_agent = create_email_agent(api_key=api_key)
            print("✅ Email agent initialized")
    except Exception as e:
        print(f"Error initializing email services: {e}")
        import traceback
        traceback.print_exc()

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5

class SearchResult(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    state: Optional[str] = None
    citation: Optional[str] = None
    snippet: Optional[str] = None
    document: Optional[str] = None
    dense_score: float
    bm25_score: float
    combined_score: float

@app.post("/search-legal", response_model=List[SearchResult])
def search_legal(request: SearchRequest):
    """
    Search for legal cases using hybrid search (Vector + Keyword).
    Optional feature - requires hybrid search dependencies.
    """
    if not HYBRID_SEARCH_AVAILABLE or searcher is None:
        raise HTTPException(
            status_code=503, 
            detail="Hybrid search not available. Install dependencies (faiss-cpu, sentence-transformers, etc.) to enable this feature."
        )
    
    try:
        results = searcher.search(request.query, top_k=request.top_k)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    """
    Simple health check endpoint.
    """
    status = "healthy" if searcher is not None else "degraded"
    return {"status": status}


# ==================== Email/Conversation Endpoints ====================

@app.get("/api/conversations")
def get_all_conversations():
    """
    Get all email conversations.
    Returns conversations grouped by thread.
    """
    if conversation_manager is None:
        raise HTTPException(status_code=503, detail="Conversation manager not initialized")
    
    # Get all conversations from database
    all_conversations = conversation_manager.get_all_conversations()
    
    return {
        "conversations": all_conversations,
        "count": len(all_conversations)
    }


@app.get("/api/conversations/{lawyer_email}")
def get_lawyer_conversation(lawyer_email: str):
    """
    Get conversation thread for a specific lawyer email.
    """
    if conversation_manager is None:
        raise HTTPException(status_code=503, detail="Conversation manager not initialized")
    
    # Find conversations involving this lawyer (database has latest)
    all_conversations = conversation_manager.get_all_conversations()
    
    lawyer_email_lower = lawyer_email.lower().strip()
    matching_threads = []
    
    for thread_id, thread_data in all_conversations.items():
        # Check if lawyer is in participants
        participants = [p.lower() for p in thread_data.get('participants', [])]
        is_participant = lawyer_email_lower in participants
        
        # Also check if lawyer appears in any email's from or to field
        # But be more strict - only include if lawyer is directly involved
        emails = thread_data.get('emails', [])
        is_in_emails = False
        for email in emails:
            email_from = (email.get('from', '') or '').lower().strip()
            email_to = (email.get('to', '') or '').lower().strip()
            # Check exact match, not substring match
            if email_from == lawyer_email_lower or email_to == lawyer_email_lower:
                is_in_emails = True
                break
        
        if is_participant or is_in_emails:
            matching_threads.append({
                "thread_id": thread_id,
                **thread_data
            })
    
    return {
        "lawyer_email": lawyer_email,
        "threads": matching_threads,
        "count": len(matching_threads)
    }


@app.get("/api/lawyers")
def get_all_lawyers():
    """
    Get all tracked lawyers with their offers and conversation status.
    """
    if lawyer_tracker is None:
        raise HTTPException(status_code=503, detail="Lawyer tracker not initialized")
    
    lawyers = lawyer_tracker.get_all_lawyers()
    
    # Convert to dict format for JSON response
    lawyers_data = []
    for lawyer in lawyers:
        lawyer_dict = {
            "lawyer_name": lawyer.lawyer_name,
            "lawyer_email": lawyer.lawyer_email,
            "firm_name": lawyer.firm_name,
            "hourly_rate": lawyer.hourly_rate,
            "flat_fee": lawyer.flat_fee,
            "contingency_rate": lawyer.contingency_rate,
            "retainer_amount": lawyer.retainer_amount,
            "estimated_total": lawyer.estimated_total,
            "payment_plan": lawyer.payment_plan,
            "experience_years": lawyer.experience_years,
            "case_types": lawyer.case_types,
            "availability": lawyer.availability,
            "response_time": lawyer.response_time,
            "first_contact_date": lawyer.first_contact_date,
            "last_contact_date": lawyer.last_contact_date,
            "email_count": lawyer.email_count,
            "thread_id": lawyer.thread_id,
            "location": lawyer.location
        }
        lawyers_data.append(lawyer_dict)
    
    return {
        "lawyers": lawyers_data,
        "count": len(lawyers_data)
    }


@app.get("/api/lawyers/ranked")
def get_ranked_lawyers(
    case_type: Optional[str] = None,
    max_price: Optional[float] = None,
    user_location: Optional[str] = None
):
    """
    Get lawyers ranked by three metrics:
    1. Quote for service (pricing - lower is better)
    2. Years of experience (higher is better)
    3. Location-based (closer is better)
    
    Args:
        case_type: Optional case type filter (e.g., "personal injury")
        max_price: Optional maximum price filter
        user_location: Optional user location for location-based ranking (e.g., "New York, NY")
    
    Returns:
        List of ranked lawyers with scoring breakdown
    """
    if lawyer_tracker is None:
        raise HTTPException(status_code=503, detail="Lawyer tracker not initialized")
    
    # Get ranked lawyers
    ranked_lawyers = lawyer_tracker.rank_lawyers(
        case_type=case_type or "",
        max_price=max_price,
        user_location=user_location
    )
    
    # Calculate scores for each lawyer
    all_lawyers = lawyer_tracker.get_all_lawyers()
    lawyers_data = []
    for lawyer in ranked_lawyers:
        score_data = lawyer_tracker._calculate_ranking_score(lawyer, all_lawyers, user_location)
        lawyer_dict = {
            "lawyer_name": lawyer.lawyer_name,
            "lawyer_email": lawyer.lawyer_email,
            "firm_name": lawyer.firm_name,
            "hourly_rate": lawyer.hourly_rate,
            "flat_fee": lawyer.flat_fee,
            "contingency_rate": lawyer.contingency_rate,
            "retainer_amount": lawyer.retainer_amount,
            "estimated_total": lawyer.estimated_total,
            "payment_plan": lawyer.payment_plan,
            "experience_years": lawyer.experience_years,
            "case_types": lawyer.case_types,
            "availability": lawyer.availability,
            "response_time": lawyer.response_time,
            "first_contact_date": lawyer.first_contact_date,
            "last_contact_date": lawyer.last_contact_date,
            "email_count": lawyer.email_count,
            "thread_id": lawyer.thread_id,
            "location": lawyer.location,
            "ranking": {
                "total_score": round(score_data['total_score'], 3),
                "price_score": round(score_data['price_score'], 3),
                "experience_score": round(score_data['experience_score'], 3),
                "location_score": round(score_data['location_score'], 3)
            }
        }
        lawyers_data.append(lawyer_dict)
    
    return {
        "lawyers": lawyers_data,
        "count": len(lawyers_data),
        "ranking_metrics": {
            "price_weight": 0.40,
            "experience_weight": 0.35,
            "location_weight": 0.25
        }
    }


@app.get("/api/conversations/updated-since/{timestamp}")
def get_conversations_updated_since(timestamp: str):
    """
    Get conversations updated since a specific timestamp.
    Useful for polling - only returns new/updated conversations.
    
    Args:
        timestamp: ISO format timestamp (e.g., "2025-11-22T20:41:51.237844")
    """
    if conversation_manager is None:
        raise HTTPException(status_code=503, detail="Conversation manager not initialized")
    
    # Get updated conversations from database
    all_conversations = conversation_manager.get_all_conversations()
    
    updated_conversations = {}
    for thread_id, thread_data in all_conversations.items():
        updated_at = thread_data.get('updated_at', '')
        if updated_at > timestamp:
            updated_conversations[thread_id] = thread_data
    
    return {
        "conversations": updated_conversations,
        "count": len(updated_conversations),
        "since": timestamp
    }


@app.get("/api/stats")
def get_stats():
    """
    Get overall statistics about lawyer communications.
    Analyzes conversations to determine quotes and finalized deals.
    """
    if conversation_manager is None or lawyer_tracker is None:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    # Get latest data from database
    all_conversations = conversation_manager.get_all_conversations()
    lawyers = lawyer_tracker.get_all_lawyers()
    
    total_conversations = len(all_conversations)
    total_lawyers = len(lawyers)
    
    # Count lawyers by status
    lawyers_contacted = total_lawyers
    lawyers_responded = sum(1 for l in lawyers if l.email_count > 1)
    active_conversations = sum(1 for thread in all_conversations.values() 
                              if len(thread.get('emails', [])) > 1)
    
    # Count quotes received - lawyers who have provided pricing information
    quotes_received = 0
    for lawyer in lawyers:
        # Check if lawyer has any pricing information
        has_pricing = (
            lawyer.hourly_rate is not None or
            lawyer.flat_fee is not None or
            lawyer.contingency_rate is not None or
            lawyer.retainer_amount is not None or
            lawyer.estimated_total is not None
        )
        if has_pricing:
            quotes_received += 1
    
    # Count deals finalized - analyze conversation content
    deals_finalized = 0
    finalization_keywords = [
        'agreed', 'accept', 'accepted', 'signed', 'contract', 'retainer paid',
        'retainer sent', 'moving forward', 'proceed', 'hired', 'retained',
        'deal', 'finalized', 'confirmed', 'agreement', 'terms agreed',
        'ready to start', 'begin work', 'engagement letter'
    ]
    
    for thread_id, thread_data in all_conversations.items():
        emails = thread_data.get('emails', [])
        if len(emails) < 2:  # Need at least initial + response
            continue
        
        # Check all emails in the thread for finalization indicators
        thread_text = ' '.join([email.get('body', '').lower() for email in emails])
        
        # Check if any finalization keywords appear
        if any(keyword in thread_text for keyword in finalization_keywords):
            # Additional check: make sure it's not just mentioning these words
            # Look for stronger indicators like "we agree" or "I accept"
            strong_indicators = [
                'we agree', 'i accept', 'i\'ll proceed', 'let\'s move forward',
                'retainer sent', 'payment sent', 'signed the', 'contract signed'
            ]
            if any(indicator in thread_text for indicator in strong_indicators):
                deals_finalized += 1
    
    return {
        "lawyers_contacted": lawyers_contacted,
        "lawyers_responded": lawyers_responded,
        "total_conversations": total_conversations,
        "active_conversations": active_conversations,
        "quotes_received": quotes_received,  # Based on actual pricing data
        "deals_finalized": deals_finalized  # Based on conversation analysis
    }


@app.get("/api/phone-call-requests")
def get_phone_call_requests():
    """
    Get all threads where lawyers have requested phone calls.
    """
    if conversation_manager is None:
        raise HTTPException(status_code=503, detail="Conversation manager not initialized")
    
    all_conversations = conversation_manager.get_all_conversations()
    phone_call_threads = []
    
    for thread_id, thread_data in all_conversations.items():
        if thread_data.get('phone_call_requested', False):
            # Get lawyer email from participants
            participants = thread_data.get('participants', [])
            lawyer_email = None
            sender_email = os.getenv("SENDER_EMAIL", "").lower()
            for p in participants:
                if p.lower() != sender_email:
                    lawyer_email = p
                    break
            
            phone_call_threads.append({
                "thread_id": thread_id,
                "lawyer_email": lawyer_email,
                "subject": thread_data.get('subject', ''),
                "updated_at": thread_data.get('updated_at', '')
            })
    
    return {
        "phone_call_requests": phone_call_threads,
        "count": len(phone_call_threads)
    }


class StartSearchRequest(BaseModel):
    situation: str
    lawyer_emails: Optional[List[str]] = None


@app.post("/api/search/start")
def start_lawyer_search(request: StartSearchRequest):
    """
    Start a lawyer search by sending initial emails to lawyers.
    Uses hardcoded lawyer emails from example_lawyer_communication.py
    """
    global email_agent, listener_thread
    
    if email_agent is None:
        raise HTTPException(
            status_code=503, 
            detail="Email agent not initialized. Check GEMINI_API_KEY environment variable."
        )
    
    # Hardcoded lawyer emails from example_lawyer_communication.py
    lawyer_emails = [
        "sohamkundu2704@gmail.com",
        "womovo6376@bablace.com",
        "arnavmohanty123@gmail.com"
    ]
    
    situation = request.situation or ""
    
    # Set up initial message based on situation
    initial_subject = "Legal Consultation Inquiry"
    initial_message = f"""Hello,

I hope this email finds you well. I am reaching out to inquire about your legal services and would appreciate the opportunity to discuss my legal needs with you.

Client Situation:
{situation if situation else "General legal consultation needed."}

Could you please provide information about:
- Your areas of practice
- Your fee structure (hourly rate, flat fee, or contingency)
- Your availability for a consultation
- Any initial retainer requirements

Thank you for your time and consideration. I look forward to hearing from you.

Best regards"""
    
    try:
        # Set lawyer emails and send initial messages
        email_agent.set_lawyer_emails(lawyer_emails)
        results = email_agent.send_initial_message_to_lawyers(
            subject=initial_subject,
            message_template=initial_message
        )
        
        # Track lawyers immediately after sending initial emails
        # This ensures they show up in the frontend even before they respond
        # Also save initial emails to conversation history
        for lawyer_email in lawyer_emails:
            lawyer_email_lower = lawyer_email.lower()
            
            # Check if email was sent successfully
            result = results.get(lawyer_email, "")
            if "successfully" in result.lower():
                # Save initial email to conversation history
                try:
                    initial_email_data = {
                        'from': os.getenv("SENDER_EMAIL", ""),
                        'to': lawyer_email,
                        'subject': initial_subject,
                        'body': initial_message,
                        'date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z'),
                        'uid': '',  # Sent emails don't have UIDs
                        'message_id': '',
                        'in_reply_to': '',
                        'references': ''
                    }
                    thread_id = conversation_manager.add_email(initial_email_data)
                    
                    # Create lawyer entry in database with thread_id
                    lawyer_tracker.create_lawyer(
                        lawyer_email=lawyer_email_lower,
                        lawyer_name="",  # Will be filled when they respond
                        thread_id=thread_id
                    )
                    print(f"✅ Tracked lawyer: {lawyer_email_lower} (thread: {thread_id})")
                except Exception as e:
                    print(f"⚠️  Warning: Failed to save initial email for {lawyer_email_lower}: {str(e)}")
                    # Still create lawyer entry even if saving email fails
                    lawyer_tracker.create_lawyer(
                        lawyer_email=lawyer_email_lower,
                        lawyer_name="",
                        thread_id=""
                    )
            else:
                # Email failed to send, still create lawyer entry
                lawyer_tracker.create_lawyer(
                    lawyer_email=lawyer_email_lower,
                    lawyer_name="",
                    thread_id=""
                )
                print(f"⚠️  Tracked lawyer (email send failed): {lawyer_email_lower}")
        
        # Start email listener in background thread if not already running
        if listener_thread is None or not listener_thread.is_alive():
            from backend.email_service.email_listener import listen_loop
            listener_thread = threading.Thread(
                target=listen_loop,
                args=(email_agent, conversation_manager, lawyer_tracker),
                kwargs={"check_interval": 15, "auto_reply": True},
                daemon=True
            )
            listener_thread.start()
            print("Email listener started in background thread")
        
        return {
            "success": True,
            "message": "Lawyer search initiated",
            "lawyers_contacted": len(lawyer_emails),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting search: {str(e)}")
