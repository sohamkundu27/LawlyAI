# Startup Guide - LawlyAI Email Service Integration

## What You Need to Start

To get the email service working with real-time updates, you need to run **2 servers**:

### 1. Backend FastAPI Server (Port 8000)
This handles:
- Email agent initialization
- Sending emails to lawyers
- Email listener (checks for new emails)
- API endpoints for frontend

### 2. Frontend Next.js Server (Port 3000)
This handles:
- User interface
- Polling for updates
- Displaying email threads

---

## Step-by-Step Setup

### Prerequisites

Make sure you have a `.env` file in the root directory with:

```env
# Gemini AI API Key (required for email agent)
GEMINI_API_KEY=your_gemini_api_key_here

# Email Configuration (required for sending emails)
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-specific-password

# Optional: MongoDB (if using)
MONGO_URL=your_mongodb_url
DB_NAME=your_database_name
```

**Note:** For Gmail, you need an [App-Specific Password](https://myaccount.google.com/apppasswords), not your regular password.

---

## Starting the Servers

### Terminal 1: Backend Server

```bash
# Navigate to project root
cd C:\Users\jayba\Documents\lawlyAI\Sentinel

# Activate your Python virtual environment (if using one)
# venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# Install dependencies (if not already done)
pip install -r requirements.txt

# Start the FastAPI server
uvicorn backend.api_service:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
Email agent initialized
```

### Terminal 2: Frontend Server

```bash
# Navigate to project root (if not already there)
cd C:\Users\jayba\Documents\lawlyAI\Sentinel

# Start the Next.js dev server
npm run dev
```

You should see:
```
✓ Ready in X seconds
○ Local:        http://localhost:3000
```

---

## Testing the Integration

1. **Open the frontend**: Go to `http://localhost:3000`
2. **Navigate to search**: Click "Try Now" or go to `/search`
3. **Enter a legal situation**: Type something like "I was in a car accident..."
4. **Click "Find My Lawyer"**: This will:
   - Call the backend API
   - Send emails to the 3 hardcoded lawyers:
     - sohamkundu2704@gmail.com
     - womovo6376@bablace.com
     - arnavmohanty123@gmail.com
   - Start the email listener in the background
5. **Watch for updates**: The page will automatically poll every 5 seconds for:
   - New lawyer responses
   - Updated email threads
   - Statistics

---

## How It Works

### Email Flow:
1. User submits situation → Frontend calls `/api/search/start`
2. Backend sends initial emails → 3 lawyers receive inquiry
3. Email listener starts → Checks inbox every 60 seconds
4. When lawyer replies → Email is processed and stored
5. Frontend polls → Fetches updates every 5 seconds
6. UI updates → New emails appear automatically

### Polling Intervals:
- **Lawyer list**: Every 5 seconds (when search is active)
- **Statistics**: Every 5 seconds (when search is active)
- **Email threads**: Every 3 seconds (when thread is expanded)
- **Email listener**: Checks inbox every 60 seconds

---

## Troubleshooting

### Backend won't start:
- ✅ Check that `GEMINI_API_KEY` is set in `.env`
- ✅ Check that all Python dependencies are installed: `pip install -r requirements.txt`
- ✅ Make sure port 8000 is not in use

### Frontend can't connect to backend:
- ✅ Check that backend is running on port 8000
- ✅ Check browser console for CORS errors
- ✅ Verify `NEXT_PUBLIC_API_URL` in `.env` (defaults to `http://localhost:8000`)

### Emails not sending:
- ✅ Check `SENDER_EMAIL` and `SENDER_PASSWORD` in `.env`
- ✅ For Gmail, use App-Specific Password (not regular password)
- ✅ Check backend logs for email errors

### No updates appearing:
- ✅ Check that email listener thread started (backend logs)
- ✅ Verify lawyers are receiving emails (check their inboxes)
- ✅ Check browser console for API errors
- ✅ Verify polling is enabled (check Network tab in DevTools)

### Email agent not initialized:
- ✅ Check that `GEMINI_API_KEY` is set correctly
- ✅ Check backend startup logs for "Email agent initialized"
- ✅ If missing, the `/api/search/start` endpoint will return a 503 error

---

## API Endpoints

The backend exposes these endpoints:

- `GET /api/lawyers` - Get all tracked lawyers
- `GET /api/conversations` - Get all email conversations
- `GET /api/conversations/{lawyer_email}` - Get specific lawyer's threads
- `GET /api/stats` - Get statistics
- `POST /api/search/start` - Start lawyer search (sends initial emails)
- `GET /health` - Health check

---

## Quick Start Commands

**Windows PowerShell:**
```powershell
# Terminal 1 - Backend
cd C:\Users\jayba\Documents\lawlyAI\Sentinel
uvicorn backend.api_service:app --reload --port 8000

# Terminal 2 - Frontend
cd C:\Users\jayba\Documents\lawlyAI\Sentinel
npm run dev
```

**Mac/Linux:**
```bash
# Terminal 1 - Backend
cd ~/path/to/Sentinel
uvicorn backend.api_service:app --reload --port 8000

# Terminal 2 - Frontend
cd ~/path/to/Sentinel
npm run dev
```

---

## What Happens When You Start a Search

1. ✅ Frontend sends POST to `/api/search/start` with situation
2. ✅ Backend initializes email agent (if not already done)
3. ✅ Backend sends emails to 3 hardcoded lawyers
4. ✅ Backend starts email listener in background thread
5. ✅ Frontend starts polling for updates
6. ✅ When lawyers reply, emails are processed automatically
7. ✅ Frontend displays new emails in real-time

---

## Notes

- The email listener runs in a **background thread** - it won't block the API
- Emails are stored in `backend/email_service/email_conversations.json`
- Lawyer data is stored in `backend/email_service/lawyers_data.json`
- The frontend polls automatically - no manual refresh needed
- Email listener checks every 60 seconds (configurable in code)

