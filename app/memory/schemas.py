from sqlmodel import SQLModel, Field, create_engine, Session
from datetime import datetime
from typing import List, Optional
from app.config import settings

class Memory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    type: str  # e.g., 'chat', 'summary', 'note'
    text: str
    tags: str  # JSON string for list of tags
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ChatSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ChatMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str
    role: str  # user, assistant
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

engine = create_engine(f"sqlite:///{settings.db_path_abs}")

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
