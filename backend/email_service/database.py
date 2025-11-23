"""
Database models and connection for email service.
Uses SQLite by default, can be switched to PostgreSQL.
"""

import os
from datetime import datetime
from typing import Optional, List
from sqlalchemy import create_engine, Column, String, Integer, Float, Text, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import json

Base = declarative_base()

# Database URL - defaults to SQLite, can use PostgreSQL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./backend/email_service/email_service.db"
)

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Database Models
class EmailThread(Base):
    """Email conversation thread."""
    __tablename__ = "email_threads"
    
    thread_id = Column(String, primary_key=True)
    subject = Column(String)
    participants = Column(JSON)  # List of email addresses
    manual_mode = Column(Integer, default=0)  # 0 = auto, 1 = manual (user controls replies)
    phone_call_requested = Column(Integer, default=0)  # 0 = no, 1 = yes (lawyer requested call)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmailMessage(Base):
    """Individual email message in a thread."""
    __tablename__ = "email_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(String, nullable=False, index=True)
    from_email = Column(String, nullable=False)
    to_email = Column(String, nullable=False)
    subject = Column(String)
    body = Column(Text)
    date = Column(String)  # Original email date string
    uid = Column(String)  # IMAP UID
    message_id = Column(String)
    in_reply_to = Column(String)
    references = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Index for faster lookups
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )


class Lawyer(Base):
    """Lawyer information and offers."""
    __tablename__ = "lawyers"
    
    lawyer_email = Column(String, primary_key=True)
    lawyer_name = Column(String)
    firm_name = Column(String)
    hourly_rate = Column(Float)
    flat_fee = Column(Float)
    contingency_rate = Column(Float)
    retainer_amount = Column(Float)
    estimated_total = Column(Float)
    payment_plan = Column(String)
    experience_years = Column(Integer)
    case_types = Column(JSON)  # List of strings
    availability = Column(String)
    response_time = Column(String)
    terms = Column(Text)
    notes = Column(Text)
    first_contact_date = Column(DateTime)
    last_contact_date = Column(DateTime)
    email_count = Column(Integer, default=0)
    thread_id = Column(String)
    location = Column(String)  # City, State or full address
    # Extracted facts from live email parsing (optional; we only fill these once)
    price_value = Column(Float)  # Normalized numeric representation for ranking
    price_text = Column(String)  # Raw snippet describing pricing
    years_experience = Column(Integer)  # Extracted years from emails (kept separate from experience_years)
    experience_text = Column(String)
    location_text = Column(String)
    rank_score = Column(Integer)  # 0-100 score computed from price_value + years_experience


class ProcessedEmail(Base):
    """Track processed emails to avoid duplicates."""
    __tablename__ = "processed_emails"
    
    uid = Column(String, primary_key=True)
    processed_at = Column(DateTime, default=datetime.utcnow)


# Initialize database
def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized")


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """Get a database session (for direct use)."""
    return SessionLocal()

