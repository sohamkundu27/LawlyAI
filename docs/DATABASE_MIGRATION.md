# Database Migration Guide

## Overview

The email service has been migrated from JSON file storage to **SQLite database** storage. This provides:
- ✅ Better performance
- ✅ Proper data relationships
- ✅ Query capabilities
- ✅ Concurrent access support
- ✅ Easy migration to PostgreSQL later

## Database Setup

### Default: SQLite (No Setup Required)

The system uses SQLite by default. The database file will be created automatically at:
```
backend/email_service/email_service.db
```

### Optional: PostgreSQL

To use PostgreSQL instead, set the `DATABASE_URL` environment variable:

```env
DATABASE_URL=postgresql://user:password@localhost/dbname
```

## Installation

Install SQLAlchemy (already added to requirements.txt):

```bash
pip install sqlalchemy
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

## Database Schema

### Tables

1. **email_threads** - Conversation threads
   - `thread_id` (primary key)
   - `subject`
   - `participants` (JSON array)
   - `created_at`, `updated_at`

2. **email_messages** - Individual emails
   - `id` (auto-increment)
   - `thread_id` (foreign key)
   - `from_email`, `to_email`
   - `subject`, `body`
   - `timestamp`, `date`, `uid`

3. **lawyers** - Lawyer information
   - `lawyer_email` (primary key)
   - `lawyer_name`, `firm_name`
   - `hourly_rate`, `flat_fee`, `contingency_rate`
   - `case_types` (JSON array)
   - `email_count`, `first_contact_date`, `last_contact_date`

4. **processed_emails** - Track processed emails
   - `uid` (primary key)
   - `processed_at`

## Migration from JSON Files

If you have existing JSON files, you can migrate them:

```bash
python backend/email_service/migrate_to_db.py
```

This will:
- Read existing JSON files
- Import data into database
- Keep JSON files as backup

## What Changed

### Backend Files Updated

1. **`backend/api_service.py`**
   - Now uses `ConversationManagerDB` and `LawyerTrackerDB`
   - Database initialized on startup

2. **`backend/email_service/email_listener.py`**
   - Uses database for processed emails tracking

3. **New Files Created:**
   - `backend/email_service/database.py` - Database models
   - `backend/email_service/conversation_manager_db.py` - DB-backed conversation manager
   - `backend/email_service/lawyer_tracker_db.py` - DB-backed lawyer tracker
   - `backend/email_service/migrate_to_db.py` - Migration script

### API Endpoints (No Changes)

All API endpoints work the same way:
- `GET /api/conversations` - Returns all conversations
- `GET /api/lawyers` - Returns all lawyers
- `GET /api/stats` - Returns statistics

The frontend doesn't need any changes!

## Benefits

1. **Performance**: Database queries are faster than reading JSON files
2. **Scalability**: Can handle thousands of conversations
3. **Reliability**: ACID transactions, data integrity
4. **Querying**: Can filter, search, sort easily
5. **Concurrent Access**: Multiple processes can read/write safely

## Database Location

- **SQLite**: `backend/email_service/email_service.db`
- **PostgreSQL**: Configured via `DATABASE_URL` env var

## Backup

To backup SQLite database:
```bash
cp backend/email_service/email_service.db backend/email_service/email_service.db.backup
```

## Clearing Data

To start fresh, delete the database file:
```bash
rm backend/email_service/email_service.db
```

The database will be recreated on next server start.

## Next Steps

1. **Install SQLAlchemy**: `pip install sqlalchemy`
2. **Restart backend server** - Database will be initialized automatically
3. **Start using** - Everything works the same, but now with database storage!



