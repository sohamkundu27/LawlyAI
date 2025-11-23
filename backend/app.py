"""
Unified FastAPI application for LawlyAI.
Merges search, lawyer extraction, and email outreach capabilities.

Run with:
    uvicorn backend.app:app --reload
"""

import sys
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add project root to sys.path so imports work regardless of where script is run
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Imports from Search System ---
try:
    from backend.hybrid_search import HybridSearcher
    from backend.lawyer_extractor import extract_lawyers_from_search_results
    from backend.lawyer_enrichment import enrich_lawyers_with_emails
    HYBRID_SEARCH_AVAILABLE = True
except ImportError:
    HYBRID_SEARCH_AVAILABLE = False
    HybridSearcher = None
    print("WARNING: Hybrid search dependencies missing.")

# --- Imports from Email System ---
from backend.email_service.database import init_db
from backend.email_service.conversation_manager_db import ConversationManagerDB
from backend.email_service.lawyer_tracker_db import LawyerTrackerDB
from backend.email_service.email_agent import create_email_agent
from backend.email_service.email_listener import listen_loop

# --- Global Instances ---
searcher: Optional[HybridSearcher] = None
conversation_manager: Optional[ConversationManagerDB] = None
lawyer_tracker: Optional[LawyerTrackerDB] = None
email_agent = None
listener_thread = None

DEMO_LAWYERS = [
    {
        "name": "Soham Kundu (Demo)",
        "email": "sohamkundu2704@gmail.com",
        "firm": "Demo Law Group",
    },
    {
        "name": "Jayanth Balu (Demo)",
        "email": "jaybalu06@gmail.com",
        "firm": "Demo Law Group",
    },
    {
        "name": "Arnav Mohanty (Demo)",
        "email": "arnavmohanty123@gmail.com",
        "firm": "Demo Law Group",
    },
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager to handle startup and shutdown events.
    Initializes Search, Database, Email Agent, and Background Listener.
    """
    global searcher, conversation_manager, lawyer_tracker, email_agent, listener_thread
    
    print("--- Starting LawlyAI Backend ---")

    # 1. Initialize Hybrid Searcher
    if HYBRID_SEARCH_AVAILABLE:
        dataset_path = "./vectorized_dataset"
        if not os.path.exists(dataset_path):
            # Try finding it relative to this file if not in cwd
            current_dir = os.path.dirname(os.path.abspath(__file__))
            alt_path = os.path.join(current_dir, "vectorized_dataset")
            if os.path.exists(alt_path):
                dataset_path = alt_path
            else:
                print(f"WARNING: Dataset path '{dataset_path}' not found. Search functionality may fail.")
        
        try:
            if os.path.exists(dataset_path):
                searcher = HybridSearcher(dataset_path=dataset_path)
                print("✅ Hybrid search initialized")
            else:
                print("❌ Dataset not found, skipping hybrid search init.")
        except Exception as e:
            print(f"❌ Error initializing searcher: {e}")
    else:
        print("INFO: Hybrid search not available.")

    # 2. Initialize Email Services (DB, Managers, Agent)
    try:
        init_db()
        print("✅ Database initialized")
        
        conversation_manager = ConversationManagerDB()
        lawyer_tracker = LawyerTrackerDB()
        
        # Initialize email agent
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if api_key:
            email_agent = create_email_agent(api_key=api_key)
            print("✅ Email agent initialized")
        else:
            print("⚠️  WARNING: GEMINI_API_KEY not found. Email agent will not work.")

    except Exception as e:
        print(f"❌ Error initializing email services: {e}")

    # 3. Start Email Listener Background Thread
    if email_agent and conversation_manager and lawyer_tracker:
        try:
            listener_thread = threading.Thread(
                target=listen_loop,
                args=(email_agent, conversation_manager, lawyer_tracker),
                kwargs={"check_interval": 15, "auto_reply": True},
                daemon=True
            )
            listener_thread.start()
            print("✅ Email listener started in background thread")
        except Exception as e:
            print(f"❌ Error starting email listener: {e}")

    yield
    
    # Shutdown logic if needed
    print("--- Shutting down LawlyAI Backend ---")
    searcher = None

app = FastAPI(title="LawlyAI Unified API", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---

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
    # Extracted lawyers attached directly
    extracted_lawyers: Optional[List[Dict[str, Any]]] = []

class ContactRequest(BaseModel):
    situation: str
    lawyer_emails: List[str]

# --- Helper Functions ---

def build_initial_email_content(situation: str) -> Tuple[str, str]:
    """Return the standard initial outreach subject/body."""
    subject = "Legal Consultation Inquiry"
    body = f"""Hello,

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
    return subject, body


def send_initial_outreach(lawyer_emails: List[str], situation: str) -> Dict[str, Any]:
    """
    Helper to send initial emails to a list of lawyers using the global email agent.
    Handles database tracking for the new threads.
    """
    global email_agent, conversation_manager, lawyer_tracker
    
    if not email_agent:
        raise ValueError("Email agent not initialized")
    if not conversation_manager or not lawyer_tracker:
        raise ValueError("Database services not initialized")

    initial_subject, initial_message = build_initial_email_content(situation)

    # Configure Agent
    email_agent.set_lawyer_emails(lawyer_emails)
    
    # Send Emails
    results = email_agent.send_initial_message_to_lawyers(
        subject=initial_subject,
        message_template=initial_message
    )
    
    # Track Results in DB
    processed_results = []
    sender_email = os.getenv("SENDER_EMAIL", "")
    
    for lawyer_email in lawyer_emails:
        lawyer_email_lower = lawyer_email.lower()
        result_text = results.get(lawyer_email, "")
        success = "successfully" in result_text.lower()
        
        if success:
            # 1. Save to Conversation History
            try:
                initial_email_data = {
                    'from': sender_email,
                    'to': lawyer_email,
                    'subject': initial_subject,
                    'body': initial_message,
                    'date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z'),
                    'uid': '',
                    'message_id': '',
                    'in_reply_to': '',
                    'references': ''
                }
                thread_id = conversation_manager.add_email(initial_email_data)
                
                # 2. Create/Update Lawyer Entry
                lawyer_tracker.create_lawyer(
                    lawyer_email=lawyer_email_lower,
                    lawyer_name="",  # Will be updated when they reply
                    thread_id=thread_id
                )
                print(f"✅ Tracked lawyer: {lawyer_email_lower} (thread: {thread_id})")
            except Exception as e:
                print(f"⚠️ Error tracking lawyer {lawyer_email_lower}: {e}")
        else:
            # Even if failed, track them so we know we tried
            lawyer_tracker.create_lawyer(
                lawyer_email=lawyer_email_lower,
                lawyer_name="",
                thread_id=""
            )
            print(f"⚠️ Outrech failed for {lawyer_email_lower}: {result_text}")

    return {
        "status": "Emails processed",
        "sent_to": [e for e in lawyer_emails if "successfully" in results.get(e, "").lower()],
        "results": results
    }


def _start_initial_emails_for_lawyers_async(lawyers: List[Dict[str, Any]], user_situation: str) -> None:
    """
    Fire-and-forget helper to send initial outreach emails to a list of enriched lawyers.
    Uses the existing send_initial_outreach + ConversationManagerDB / LawyerTrackerDB path.
    
    This runs in a background thread so /search-legal can return quickly.
    """
    def _worker():
        global email_agent, conversation_manager, lawyer_tracker
        try:
            if not email_agent or not conversation_manager or not lawyer_tracker:
                print("⚠️  Initial email outreach skipped (services not initialized).")
                return
            
            valid_emails = []
            seen = set()
            for lawyer in lawyers:
                email = (lawyer.get("email") or "").strip().lower()
                if not email:
                    continue
                if "@" not in email:
                    continue
                local, _, domain = email.partition("@")
                if not local or not domain or "." not in domain:
                    continue
                if email in seen:
                    continue
                seen.add(email)
                valid_emails.append(email)
            
            if not valid_emails:
                print("INFO: No valid lawyer emails found for initial outreach.")
                return
            
            print(f"Skipping real email sending for {len(valid_emails)} lawyer(s); UI-only seeding is active.")
            # Placeholder for future: send_initial_outreach(valid_emails, user_situation)
        except Exception as e:
            print(f"❌ Error in background initial outreach: {e}")
    
    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def seed_initial_conversations_for_lawyers(lawyers: List[Dict[str, Any]], user_situation: str) -> None:
    """
    Create an initial EmailThread + EmailMessage for each enriched lawyer
    without actually sending an email.
    """
    global conversation_manager, lawyer_tracker
    if not conversation_manager or not lawyer_tracker:
        print("⚠️  Conversation or lawyer tracker not initialized; cannot seed initial emails.")
        return
    
    subject, message = build_initial_email_content(user_situation)
    sender_email = os.getenv("SENDER_EMAIL", "").strip() or "client@lawlyai.com"
    
    seen = set()
    for lawyer in lawyers:
        email = (lawyer.get("email") or "").strip().lower()
        if not email or "@" not in email:
            continue
        local, _, domain = email.partition("@")
        if not local or not domain or "." not in domain:
            continue
        if email in seen:
            continue
        seen.add(email)
        
        email_data = {
            'from': sender_email,
            'to': email,
            'subject': subject,
            'body': message,
            'date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z'),
            'uid': '',
            'message_id': '',
            'in_reply_to': '',
            'references': ''
        }
        
        try:
            thread_id = conversation_manager.add_email(email_data)
            lawyer_tracker.create_lawyer(
                lawyer_email=email,
                lawyer_name=lawyer.get("name", "") or lawyer.get("lawyer_name", ""),
                    thread_id=thread_id,
                    firm_name=lawyer.get("firm_name", "") or lawyer.get("firm", "")
            )
        except Exception as e:
            print(f"⚠️  Failed to seed initial conversation for {email}: {e}")


def start_demo_lawyer_conversations(user_situation: str) -> None:
    """
    Ensure demo lawyers exist in the database and send initial outreach emails.
    """
    global email_agent, conversation_manager, lawyer_tracker
    
    if not email_agent or not conversation_manager or not lawyer_tracker:
        print("⚠️  Demo lawyer outreach skipped (services not initialized).")
        return
    
    demo_emails = [
        demo["email"] for demo in DEMO_LAWYERS
        if demo.get("email")
    ]
    
    if not demo_emails:
        return
    
    try:
        send_initial_outreach(demo_emails, user_situation)
    except Exception as outreach_error:
        print(f"⚠️  Failed to send demo lawyer outreach: {outreach_error}")
    
    for demo in DEMO_LAWYERS:
        email_value = (demo.get("email") or "").strip().lower()
        if not email_value:
            continue
        try:
            lawyer_tracker.create_lawyer(
                lawyer_email=email_value,
                lawyer_name=demo.get("name", ""),
                thread_id="",
                firm_name=demo.get("firm", "")
            )
        except Exception as ensure_error:
            print(f"⚠️  Failed to ensure demo lawyer {email_value}: {ensure_error}")

# --- Endpoints ---

@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    status = {
        "search": "healthy" if searcher is not None else "unavailable",
        "email_agent": "healthy" if email_agent is not None else "unavailable",
        "database": "healthy" if conversation_manager is not None else "unavailable"
    }
    return {"status": "online", "components": status}

@app.post("/search-legal", response_model=List[SearchResult])
def search_legal(request: SearchRequest):
    """
    Search for legal cases using hybrid search AND automatically extract/enrich lawyers.
    """
    if not HYBRID_SEARCH_AVAILABLE or searcher is None:
        raise HTTPException(
            status_code=503, 
            detail="Hybrid search not available. Check backend logs."
        )
    
    try:
        # 1. Search
        results = searcher.search(request.query, top_k=request.top_k)
        
        # 2. Extract Lawyers (Gemini)
        all_extracted_lawyers = extract_lawyers_from_search_results(
            user_situation=request.query,
            search_results=results
        )
        
        # 3. Enrich Lawyers (Apollo/Heuristics)
        all_extracted_lawyers = enrich_lawyers_with_emails(all_extracted_lawyers)
        
        # 4. Attach to Results
        for res in results:
            res_id = res.get("id")
            res['extracted_lawyers'] = []
            
            if res_id:
                # Filter for lawyers belonging to this document
                res['extracted_lawyers'] = [
                    l for l in all_extracted_lawyers 
                    if l.get("document_id") == res_id
                ]
        
        # 5. Seed synthetic initial emails so conversations show the first message immediately
        try:
            threading.Thread(
                target=seed_initial_conversations_for_lawyers,
                args=(all_extracted_lawyers, request.query),
                daemon=True
            ).start()
        except Exception as outreach_error:
            # Do not fail search if outreach fails; just log
            print(f"⚠️  Failed to seed initial conversations from /search-legal: {outreach_error}")
        
        try:
            threading.Thread(
                target=start_demo_lawyer_conversations,
                args=(request.query,),
                daemon=True
            ).start()
        except Exception as demo_error:
            print(f"⚠️  Failed to start demo lawyer conversations: {demo_error}")
        
        return results
        
    except Exception as e:
        print(f"Error in search/extraction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/contact-lawyers")
def contact_lawyers(request: ContactRequest):
    """
    Send initial outreach emails to a provided list of lawyer emails.
    """
    if email_agent is None:
        raise HTTPException(
            status_code=503, 
            detail="Email agent not initialized. Check API keys."
        )
    
    try:
        response = send_initial_outreach(request.lawyer_emails, request.situation)
        return response
    except Exception as e:
        print(f"Error sending outreach: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Dashboard Endpoints (Migrated from api_service.py) ---

@app.get("/api/conversations")
def get_all_conversations():
    if conversation_manager is None:
        raise HTTPException(status_code=503, detail="Conversation manager not initialized")
    all_conversations = conversation_manager.get_all_conversations()
    return {"conversations": all_conversations, "count": len(all_conversations)}

@app.get("/api/conversations/{lawyer_email}")
def get_lawyer_conversation(lawyer_email: str):
    if conversation_manager is None:
        raise HTTPException(status_code=503, detail="Conversation manager not initialized")
    
    all_conversations = conversation_manager.get_all_conversations()
    lawyer_email_lower = lawyer_email.lower().strip()
    matching_threads = []
    
    for thread_id, thread_data in all_conversations.items():
        participants = [p.lower() for p in thread_data.get('participants', [])]
        is_participant = lawyer_email_lower in participants
        
        emails = thread_data.get('emails', [])
        is_in_emails = False
        for email in emails:
            email_from = (email.get('from', '') or '').lower().strip()
            email_to = (email.get('to', '') or '').lower().strip()
            if email_from == lawyer_email_lower or email_to == lawyer_email_lower:
                is_in_emails = True
                break
        
        if is_participant or is_in_emails:
            matching_threads.append({"thread_id": thread_id, **thread_data})
            
    return {
        "lawyer_email": lawyer_email,
        "threads": matching_threads,
        "count": len(matching_threads)
    }

@app.get("/api/lawyers")
def get_all_lawyers():
    if lawyer_tracker is None:
        raise HTTPException(status_code=503, detail="Lawyer tracker not initialized")
    
    lawyers = lawyer_tracker.get_all_lawyers()
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
            "location": lawyer.location,
            "price_value": lawyer.price_value,
            "price_text": lawyer.price_text or "N/A",
            "years_experience": lawyer.years_experience,
            "experience_text": lawyer.experience_text or "",
            "location_text": lawyer.location_text or "",
            "rank_score": lawyer.rank_score or 0
        }
        lawyers_data.append(lawyer_dict)
    
    return {"lawyers": lawyers_data, "count": len(lawyers_data)}

@app.get("/api/lawyers/ranked")
def get_ranked_lawyers(
    case_type: Optional[str] = None,
    max_price: Optional[float] = None,
    user_location: Optional[str] = None
):
    if lawyer_tracker is None:
        raise HTTPException(status_code=503, detail="Lawyer tracker not initialized")
    
    ranked_lawyers = lawyer_tracker.rank_lawyers(
        case_type=case_type or "",
        max_price=max_price,
        user_location=user_location
    )
    
    lawyers_data = []
    for lawyer in ranked_lawyers:
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
            "price_value": lawyer.price_value,
            "price_text": lawyer.price_text or "N/A",
            "years_experience": lawyer.years_experience,
            "experience_text": lawyer.experience_text or "",
            "location_text": lawyer.location_text or "",
            "rank_score": lawyer.rank_score or 0
        }
        lawyers_data.append(lawyer_dict)
    
    return {
        "lawyers": lawyers_data,
        "count": len(lawyers_data),
        "ranking_method": "price_experience_rank_score_with_location_fallback"
    }

@app.get("/api/conversations/updated-since/{timestamp}")
def get_conversations_updated_since(timestamp: str):
    if conversation_manager is None:
        raise HTTPException(status_code=503, detail="Conversation manager not initialized")
    
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
    if conversation_manager is None or lawyer_tracker is None:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    all_conversations = conversation_manager.get_all_conversations()
    lawyers = lawyer_tracker.get_all_lawyers()
    
    total_conversations = len(all_conversations)
    total_lawyers = len(lawyers)
    
    lawyers_contacted = total_lawyers
    lawyers_responded = sum(1 for l in lawyers if l.email_count > 1)
    active_conversations = sum(1 for thread in all_conversations.values() 
                              if len(thread.get('emails', [])) > 1)
    
    quotes_received = 0
    for lawyer in lawyers:
        has_pricing = (
            lawyer.hourly_rate is not None or
            lawyer.flat_fee is not None or
            lawyer.contingency_rate is not None or
            lawyer.retainer_amount is not None or
            lawyer.estimated_total is not None
        )
        if has_pricing:
            quotes_received += 1
    
    deals_finalized = 0
    finalization_keywords = [
        'agreed', 'accept', 'accepted', 'signed', 'contract', 'retainer paid',
        'retainer sent', 'moving forward', 'proceed', 'hired', 'retained',
        'deal', 'finalized', 'confirmed', 'agreement', 'terms agreed',
        'ready to start', 'begin work', 'engagement letter'
    ]
    
    for thread_id, thread_data in all_conversations.items():
        emails = thread_data.get('emails', [])
        if len(emails) < 2:
            continue
        thread_text = ' '.join([email.get('body', '').lower() for email in emails])
        if any(keyword in thread_text for keyword in finalization_keywords):
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
        "quotes_received": quotes_received,
        "deals_finalized": deals_finalized
    }

@app.get("/api/phone-call-requests")
def get_phone_call_requests():
    if conversation_manager is None:
        raise HTTPException(status_code=503, detail="Conversation manager not initialized")
    
    all_conversations = conversation_manager.get_all_conversations()
    phone_call_threads = []
    sender_email = os.getenv("SENDER_EMAIL", "").lower()
    
    for thread_id, thread_data in all_conversations.items():
        if thread_data.get('phone_call_requested', False):
            participants = thread_data.get('participants', [])
            lawyer_email = None
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
