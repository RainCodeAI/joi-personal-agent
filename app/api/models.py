from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import BigInteger, Text, Float, DateTime, Integer, Boolean, ARRAY, String, Date, Column
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from sqlalchemy.ext.declarative import declarative_base  # Kept for compatibility if needed

# Legacy Base for any old-style models (if any)
legacy_base = declarative_base()

class Base(DeclarativeBase):
    pass

class OAuthStartResponse(BaseModel):
    auth_url: str
    # Add state if needed for CSRF
    state: str = ""

class OAuthCallbackResponse(BaseModel):
    code: str
    state: str = ""
    # Optional: error if auth fails
    error: str = None

class ChatRequest(BaseModel):
    text: str
    session_id: str

class ChatResponse(BaseModel):
    text: str
    session_id: str
    tool_calls: Optional[List[Dict[str, Any]]] = []

class MemoryItem(BaseModel):
    id: int
    kind: str
    text: str
    tags: List[str]
    priority: float
    last_accessed: datetime
    memory_type: str  # "semantic" or "episodic"

class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 5
    filter_type: Optional[str] = None

class MemorySearchResponse(BaseModel):
    items: List[MemoryItem]

class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]

class ToolResult(BaseModel):
    ok: bool

class ToolCall(BaseModel):
    tool_name: str
    args: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None

class UserProfile(Base):
    __tablename__ = "userprofile"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, default="default")
    name: Mapped[Optional[str]] = mapped_column(String)
    email: Mapped[Optional[str]] = mapped_column(String)
    birthday: Mapped[Optional[str]] = mapped_column(String)
    hobbies: Mapped[Optional[str]] = mapped_column(String)
    relationships: Mapped[Optional[str]] = mapped_column(String)
    notes: Mapped[Optional[str]] = mapped_column(String)
    therapeutic_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    personality: Mapped[Optional[str]] = mapped_column(String)
    humor_level: Mapped[int] = mapped_column(Integer, default=5)

class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, default="default")
    message_id: Mapped[str] = mapped_column(String)
    rating: Mapped[int] = mapped_column(Integer)  # 1 thumbs up, -1 thumbs down

class Milestone(Base):
    __tablename__ = "milestone"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, default="default")
    event: Mapped[str] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)

class MoodEntry(Base):
    __tablename__ = "moodentry"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, default="default")
    date: Mapped[datetime] = mapped_column(DateTime)
    mood: Mapped[int] = mapped_column(Integer)  # 1-10

class ChatMessage(Base):
    __tablename__ = "chatmessage"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Habit(Base):
    __tablename__ = "habit"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, default="default")
    name: Mapped[str] = mapped_column(String)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    last_done: Mapped[Optional[datetime]] = mapped_column(DateTime)

class Decision(Base):
    __tablename__ = "decision"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, default="default")
    question: Mapped[str] = mapped_column(String)
    pros: Mapped[Optional[str]] = mapped_column(Text)
    cons: Mapped[Optional[str]] = mapped_column(Text)
    outcome: Mapped[Optional[str]] = mapped_column(Text)

class PersonalGoal(Base):
    __tablename__ = "personalgoal"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, default="default")
    name: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text)
    linked_habit_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    linked_decision_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String, default="active")

class ActivityLog(Base):
    __tablename__ = "activitylog"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, default="default")
    app: Mapped[str] = mapped_column(String)
    duration: Mapped[int] = mapped_column(Integer)  # seconds
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class CbtExercise(Base):
    __tablename__ = "cbtexercise"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, default="default")
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    completed_count: Mapped[int] = mapped_column(Integer, default=0)

class Memory(Base):
    __tablename__ = "memory"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)
    tags: Mapped[str] = mapped_column(String)  # JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(1536))  # Was 768
    memory_type: Mapped[str] = mapped_column(String, default="episodic")  # "semantic" or "episodic"

class Entity(Base):
    __tablename__ = "entity"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)  # person, place, concept, etc.
    description: Mapped[Optional[str]] = mapped_column(Text)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Relationship(Base):
    __tablename__ = "relationship"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    from_entity_id: Mapped[int] = mapped_column(BigInteger)
    to_entity_id: Mapped[int] = mapped_column(BigInteger)
    relation_type: Mapped[str] = mapped_column(String)  # e.g., "knows", "visited"
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Contact(Base):
    __tablename__ = 'contacts'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), default="default", nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_contact: Mapped[date] = mapped_column(Date, default=date.today)
    strength: Mapped[int] = mapped_column(Integer, default=5)  # 1-10
    entity_id: Mapped[Optional[str]] = mapped_column(String(50))  # Link to PKG/KG
    
    def __repr__(self):
        return f"<Contact(name='{self.name}', last_contact={self.last_contact}, strength={self.strength})>"

class SleepLog(Base):
    __tablename__ = "sleep_log"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), default="default", nullable=False)
    date: Mapped[date] = mapped_column(Date, default=date.today)
    hours_slept: Mapped[float] = mapped_column(Float, nullable=False)  # e.g., 7.5
    quality: Mapped[int] = mapped_column(Integer, default=5)  # 1-10
    
    def __repr__(self):
        return f"<SleepLog(date={self.date}, hours={self.hours_slept}, quality={self.quality})>"

class Transaction(Base):
    __tablename__ = "transactions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), default="default", nullable=False)
    date: Mapped[date] = mapped_column(Date, default=date.today)
    amount: Mapped[float] = mapped_column(Float, nullable=False)  # e.g., -4.50 for spend
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "food", "transport"
    
    def __repr__(self):
        return f"<Transaction(date={self.date}, amount={self.amount}, category={self.category})>"