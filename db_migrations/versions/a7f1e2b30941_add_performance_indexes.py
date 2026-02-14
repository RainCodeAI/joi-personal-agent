"""add performance indexes

Revision ID: a7f1e2b30941
Revises: c3a28d049282
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7f1e2b30941'
down_revision: Union[str, Sequence[str], None] = 'c3a28d049282'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance indexes for graph RAG, chat history, and analytics queries."""

    # Entity table: name+type lookups for graph_rag_search
    op.create_index('ix_entity_name_type', 'entity', ['name', 'type'])

    # Entity table: pgvector IVFFlat index for embedding similarity search
    # Uses ivfflat with cosine distance; nlists=100 is suitable for <100k rows
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_entity_embedding_ivfflat "
        "ON entity USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    # Relationship table: graph traversal joins
    op.create_index('ix_rel_from_to', 'relationship', ['from_entity_id', 'to_entity_id'])
    op.create_index('ix_rel_type', 'relationship', ['relation_type'])

    # ChatMessage table: session_id + timestamp for ordered chat history
    op.create_index('ix_chat_session_ts', 'chatmessage', ['session_id', 'timestamp'])

    # MoodEntry table: user_id + date for mood trend queries
    op.create_index('ix_mood_user_date', 'moodentry', ['user_id', 'date'])

    # Memory table: type + created_at for filtered memory queries
    op.create_index('ix_memory_type_created', 'memory', ['type', 'created_at'])


def downgrade() -> None:
    """Remove performance indexes."""
    op.drop_index('ix_memory_type_created', table_name='memory')
    op.drop_index('ix_mood_user_date', table_name='moodentry')
    op.drop_index('ix_chat_session_ts', table_name='chatmessage')
    op.drop_index('ix_rel_type', table_name='relationship')
    op.drop_index('ix_rel_from_to', table_name='relationship')
    op.execute("DROP INDEX IF EXISTS ix_entity_embedding_ivfflat")
    op.drop_index('ix_entity_name_type', table_name='entity')
