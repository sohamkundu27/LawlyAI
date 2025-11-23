# Data Flow and Storage Architecture

## Overview

The system uses **file-based JSON storage** for simplicity. All data is stored in JSON files in the `backend/email_service/` directory.

---

## Storage Files

### 1. `email_conversations.json`
**Purpose**: Stores all email conversation threads

**Structure**:
```json
{
  "thread_id": {
    "thread_id": "...",
    "subject": "Legal Consultation Inquiry",
    "participants": ["lawyer@example.com"],
    "emails": [
      {
        "from": "lawyer@example.com",
        "to": "your-email@gmail.com",
        "subject": "Re: Legal Consultation Inquiry",
        "body": "Email content...",
        "date": "Sat, 22 Nov 2025 20:41:10 -0600",
        "uid": "6",
        "timestamp": "2025-11-22T20:41:51.237844"
      }
    ],
    "created_at": "2025-11-22T20:41:51.237844",
    "updated_at": "2025-11-22T20:41:51.237844"
  }
}
```

**Managed by**: `ConversationManager` class

### 2. `lawyers_data.json`
**Purpose**: Stores lawyer information and offers

**Structure**:
```json
{
  "lawyer@example.com": {
    "lawyer_name": "John Doe",
    "lawyer_email": "lawyer@example.com",
    "firm_name": "Doe Law Firm",
    "hourly_rate": 350.0,
    "flat_fee": null,
    "contingency_rate": null,
    "experience_years": 15,
    "case_types": ["personal injury"],
    "first_contact_date": "2025-11-22T20:00:00",
    "last_contact_date": "2025-11-22T20:41:51",
    "email_count": 3,
    "thread_id": "..."
  }
}
```

**Managed by**: `LawyerTracker` class

### 3. `processed_emails.json`
**Purpose**: Tracks which emails have been processed (prevents duplicates)

**Structure**:
```json
{
  "processed_uids": ["1", "2", "3", ...]
}
```

**Managed by**: `email_listener.py`

---

## Data Flow

### 1. **Initial Email Send** (User starts search)

```
Frontend (Search Page)
  ↓ POST /api/search/start
Backend API (api_service.py)
  ↓ email_agent.send_initial_message_to_lawyers()
Email Agent (email_agent.py)
  ↓ send_email_tool.invoke()
SMTP Server (Gmail)
  ↓ Email sent
Email Agent
  ↓ Track in lawyer_conversations (in-memory)
Backend API
  ↓ Create LawyerOffer entry
Lawyer Tracker
  ↓ Save to lawyers_data.json ✅
```

### 2. **Email Listener** (Background process)

```
Email Listener (runs every 60 seconds)
  ↓ Check inbox via IMAP
Gmail Inbox
  ↓ Fetch new emails
Email Listener
  ↓ Process each email
Conversation Manager
  ↓ Add email to thread
  ↓ Save to email_conversations.json ✅
Lawyer Tracker
  ↓ Extract lawyer info
  ↓ Update lawyers_data.json ✅
Email Agent
  ↓ Generate reply (if auto_reply enabled)
  ↓ Send reply via SMTP
```

### 3. **Frontend Polling** (Real-time updates)

```
Frontend (usePolling hook)
  ↓ Every 10 seconds
  ↓ GET /api/lawyers
Backend API
  ↓ lawyer_tracker.get_all_lawyers()
  ↓ Reload from lawyers_data.json
  ↓ Return JSON response
Frontend
  ↓ Update UI with new data
```

```
Frontend (usePolling hook)
  ↓ Every 10 seconds
  ↓ GET /api/stats
Backend API
  ↓ Read lawyers_data.json
  ↓ Read email_conversations.json
  ↓ Calculate statistics
  ↓ Return JSON response
Frontend
  ↓ Update stats dashboard
```

```
Frontend (when thread expanded)
  ↓ Every 10 seconds
  ↓ GET /api/conversations/{lawyer_email}
Backend API
  ↓ conversation_manager._load_conversations()
  ↓ Read email_conversations.json
  ↓ Filter by lawyer email
  ↓ Return JSON response
Frontend
  ↓ Display email thread
```

---

## How Data is Written

### Writing Email Conversations

**Location**: `backend/email_service/email_conversation_manager.py`

```python
def add_email(self, email_data: Dict) -> str:
    # Add email to thread
    self.conversations[thread_id]['emails'].append(email_entry)
    # Save to file
    self._save_conversations()  # Writes to email_conversations.json
```

**When it happens**:
- When email listener processes a new email
- When email agent sends a reply

### Writing Lawyer Data

**Location**: `backend/email_service/lawyer_tracker.py`

```python
def add_lawyer_email(self, email_data: Dict, thread_id: str = ""):
    lawyer = self.extract_lawyer_info(email_data, email_body)
    self.lawyers[lawyer.lawyer_email] = lawyer
    self._save_lawyers()  # Writes to lawyers_data.json
```

**When it happens**:
- When initial email is sent (creates basic entry)
- When lawyer responds (updates with extracted info)
- When email listener processes lawyer emails

---

## How Data is Read

### Reading Email Conversations

**Location**: `backend/api_service.py`

```python
@app.get("/api/conversations")
def get_all_conversations():
    # Reload from file (always fresh)
    conversation_manager.conversations = conversation_manager._load_conversations()
    return {"conversations": conversation_manager.conversations}
```

**Note**: The API **always reloads from file** on each request to ensure fresh data.

### Reading Lawyer Data

**Location**: `backend/api_service.py`

```python
@app.get("/api/lawyers")
def get_all_lawyers():
    lawyers = lawyer_tracker.get_all_lawyers()  # Reads from in-memory dict
    # Note: The dict is loaded on startup, but we could reload here too
    return {"lawyers": lawyers_data}
```

**Note**: Currently uses in-memory cache. Could be improved to reload on each request.

---

## Data Persistence

### File-Based Storage (Current)

✅ **Pros**:
- Simple, no database setup needed
- Easy to inspect/debug (just open JSON files)
- Works immediately
- Human-readable

❌ **Cons**:
- Not suitable for production at scale
- No concurrent write protection
- File locking issues if multiple processes write
- No query capabilities

### Future: Database Migration

Could migrate to:
- **SQLite** (simple, file-based, but proper DB)
- **PostgreSQL** (production-ready)
- **MongoDB** (if you want to keep JSON-like structure)

---

## Current Data Flow Summary

```
┌─────────────────┐
│  Email Listener │  (Background thread, checks every 60s)
│  (IMAP)         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Process Email   │
│ - Extract info  │
│ - Thread emails │
└────────┬────────┘
         │
         ├─────────────────┐
         ▼                 ▼
┌─────────────────┐  ┌─────────────────┐
│ email_conversa-  │  │ lawyers_data.   │
│ tions.json      │  │ json            │
│ (Threads)       │  │ (Lawyer Info)   │
└─────────────────┘  └─────────────────┘
         │                 │
         │                 │
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │  FastAPI         │
         │  /api/lawyers    │
         │  /api/stats      │
         │  /api/conversations│
         └────────┬────────┘
                  │
                  │ (Polling every 10s)
                  ▼
         ┌─────────────────┐
         │  Frontend       │
         │  React          │
         │  (Real-time UI) │
         └─────────────────┘
```

---

## Key Points

1. **Storage**: All data is in JSON files in `backend/email_service/`
2. **Updates**: Email listener writes to files, API reads from files
3. **Real-time**: Frontend polls API every 10 seconds
4. **Freshness**: API reloads from files on each request (for conversations)
5. **Persistence**: Data survives server restarts (stored in files)

---

## File Locations

- `backend/email_service/email_conversations.json` - Email threads
- `backend/email_service/lawyers_data.json` - Lawyer information
- `backend/email_service/processed_emails.json` - Processed email UIDs

All files are created automatically when first data is written.

