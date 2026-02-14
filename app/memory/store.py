import chromadb
import httpx
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import date, timedelta
from app.config import settings
from app.api.models import UserProfile, Feedback, Milestone, ChatMessage, Memory, MoodEntry, Habit, Decision, PersonalGoal, ActivityLog, CbtExercise, Entity, Relationship, Contact, SleepLog, Transaction
from sqlalchemy import select, create_engine, text as sa_text
from sqlalchemy.orm import Session as SQLSession
import numpy as np
import torch
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    import logging
    logging.warning("Could not import sentence_transformers. Using MockSentenceTransformer.")
    class SentenceTransformer:
        def __init__(self, model_name):
            self.get_sentence_embedding_dimension = lambda: 768
        def encode(self, text, *args, **kwargs):
            # Return zero vector of dimension 768
            return np.zeros(768, dtype=np.float32)

# Database setup
engine = create_engine(settings.database_url or f"sqlite:///{settings.db_path}")

def create_db_and_tables():
    from app.api.models import Base
    Base.metadata.create_all(engine)

class MemoryStore:
    _executor = ThreadPoolExecutor(max_workers=2)

    def __init__(self):
        create_db_and_tables()
        self.chroma_client = chromadb.PersistentClient(path=str(settings.chroma_path_abs))
        self.collection = self.chroma_client.get_or_create_collection(name=settings.chroma_collection)
    
        self.expected_dim = settings.embed_dim  # Set this FIRST
        self.ollama_host = settings.ollama_host
        self.router_timeout = settings.router_timeout  # 30s from config
    
        # Validate collection dimension on init
        coll_meta = self.collection.metadata
        stored_dim = int(coll_meta.get("embed_dim", 0))
        if stored_dim != self.expected_dim:
            raise ValueError(f"Collection dim {stored_dim} != expected {self.expected_dim}. Run reset_chroma.py")
    
        # Optional: Remove dummy if present
        try:
            self.collection.delete(ids=["dummy_init"])
        except:
            pass

        self.embedder = None  # Lazy-load for embeddings

    def embed_text(self, text: str) -> List[float]:
        if self.embedder is None:
            model_name = "sentence-transformers/all-mpnet-base-v2"  # 768-dim, quality; swap to "all-MiniLM-L6-v2" (384-dim, 2x faster) if perf lags
            if torch.cuda.is_available():
                device = 'cuda'
            elif torch.backends.mps.is_available():
                device = 'mps'
            else:
                device = 'cpu'
            print(f"Loading SentenceTransformer on device: {device}")
            self.embedder = SentenceTransformer(model_name, device=device)
        
        try:
            emb = self.embedder.encode(text, convert_to_tensor=False)
            if emb.ndim == 2:
                embedding = emb[0].tolist()
            elif emb.ndim == 1:
                embedding = emb.tolist()
            else:
                raise ValueError(f"Unexpected embedding shape: {emb.shape}")
            if len(embedding) != self.expected_dim:
                raise ValueError(f"Embedding dim {len(embedding)} != expected {self.expected_dim}")
            print("Embedding from SentenceTransformer")  # Log for debug
            return embedding
        except Exception as e:
            raise Exception(f"Local embedding failed: {str(e)}. Check torch/MPS setup.")

    async def embed_text_async(self, text: str) -> List[float]:
        """Non-blocking wrapper — offloads SentenceTransformer encode to thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.embed_text, text)

    async def add_memory_async(self, mem_type: str, text: str, tags: List[str]):
        """Non-blocking add_memory — offloads embedding + entity extraction to thread pool."""
        memory_type = "semantic" if mem_type in ["entity", "summary", "goal", "habit", "decision"] else "episodic"
        with SQLSession(engine) as session:
            tags_str = json.dumps(tags)
            memory = Memory(type=mem_type, text=text, tags=tags_str, memory_type=memory_type)
            session.add(memory)
            session.commit()
            session.refresh(memory)
            # Offload the heavy embedding to thread pool
            embedding = await self.embed_text_async(text)
            self.collection.add(
                documents=[text],
                embeddings=[embedding],
                metadatas=[{"type": mem_type, "tags": tags_str, "memory_type": memory_type}],
                ids=[str(memory.id)]
            )

        # Entity extraction (also heavy — offload)
        if mem_type == "user_input":
            loop = asyncio.get_event_loop()
            entities = await loop.run_in_executor(self._executor, self.extract_entities, text)
            if entities:
                self.infer_relationships(entities, text)

    def extract_entities(self, text: str) -> List[Dict[str, str]]:
        prompt = f"""
Extract named entities from the following text. Return a JSON array of objects, each with "name" and "type". Types: person, place, organization, concept. If no entities, return [].

Text: {text}

JSON:
"""
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.ollama_host}/api/chat",
                    json={
                        "model": settings.model_chat,
                        "messages": [{"role": "user", "content": prompt}],
                        "format": "json",
                        "stream": False
                    }
                )
                response.raise_for_status()
                data = response.json()
                entities = json.loads(data["message"]["content"])
                return entities if isinstance(entities, list) else []
        except Exception as e:
            print(f"NER failed: {e}")
            return []

    def add_entity(self, name: str, entity_type: str, description: str = ""):
        with SQLSession(engine) as session:
            # Check if exists
            existing = session.execute(select(Entity).where(Entity.name == name, Entity.type == entity_type)).scalar_one_or_none()
            if existing:
                return existing.id
            embedding = self.embed_text(f"{entity_type}: {name} - {description}")
            entity = Entity(name=name, type=entity_type, description=description, embedding=embedding)
            session.add(entity)
            session.commit()
            session.refresh(entity)
            return entity.id

    def add_relationship(self, from_id: int, to_id: int, relation_type: str, weight: float = 1.0):
        with SQLSession(engine) as session:
            # Check if exists, update weight
            existing = session.execute(
                select(Relationship).where(
                    Relationship.from_entity_id == from_id,
                    Relationship.to_entity_id == to_id,
                    Relationship.relation_type == relation_type
                )
            ).scalar_one_or_none()
            if existing:
                existing.weight += weight
                session.commit()
                return
            relationship = Relationship(from_entity_id=from_id, to_entity_id=to_id, relation_type=relation_type, weight=weight)
            session.add(relationship)
            session.commit()

    def get_related_entities(self, entity_id: int, relation_type: str = None, depth: int = 1) -> List[int]:
        # Simple traversal for related entities
        with SQLSession(engine) as session:
            if relation_type:
                rels = session.execute(
                    select(Relationship).where(
                        (Relationship.from_entity_id == entity_id) | (Relationship.to_entity_id == entity_id),
                        Relationship.relation_type == relation_type
                    )
                ).scalars().all()
            else:
                rels = session.execute(
                    select(Relationship).where(
                        (Relationship.from_entity_id == entity_id) | (Relationship.to_entity_id == entity_id)
                    )
                ).scalars().all()
            related = set()
            for rel in rels:
                if rel.from_entity_id == entity_id:
                    related.add(rel.to_entity_id)
                else:
                    related.add(rel.from_entity_id)
            return list(related)

    def graph_rag_search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """3-stage Graph RAG: vector search + entity graph expansion + merge/re-rank."""
        # Stage 1: Baseline vector search (always runs)
        vector_results = self.search_embeddings(query, k * 2)
        for r in vector_results:
            r["source"] = "vector"

        # Stage 2: Entity-aware graph expansion
        query_embedding = self.embed_text(query)
        graph_results = []
        try:
            with SQLSession(engine) as session:
                # Find similar entities via pgvector cosine distance
                similar_entities = session.execute(
                    sa_text("""
                        SELECT id, name, type, description,
                               embedding <=> cast(:qe AS vector) AS distance
                        FROM entity
                        WHERE embedding IS NOT NULL
                        ORDER BY embedding <=> cast(:qe AS vector)
                        LIMIT 5
                    """),
                    {"qe": str(query_embedding)}
                ).fetchall()

                # Collect entity IDs + expand via graph traversal
                entity_ids = {row.id for row in similar_entities}
                expanded_ids = set(entity_ids)
                for eid in entity_ids:
                    expanded_ids.update(self.get_related_entities(eid, depth=1))

                # Fetch entity names for memory search
                if expanded_ids:
                    entity_names = [row.name for row in similar_entities]
                    # Also get names of expanded entities not in the initial set
                    extra_ids = expanded_ids - entity_ids
                    if extra_ids:
                        extra_entities = session.execute(
                            select(Entity).where(Entity.id.in_(extra_ids))
                        ).scalars().all()
                        entity_names.extend([e.name for e in extra_entities])

                    # Search memories related to discovered entities
                    seen_texts = set()
                    for name in entity_names[:8]:  # Cap to avoid excessive queries
                        matches = self.search_embeddings(name, k=3)
                        for m in matches:
                            if m["text"][:100] not in seen_texts:
                                seen_texts.add(m["text"][:100])
                                m["source"] = "graph"
                                m["matched_entity"] = name
                                graph_results.append(m)
        except Exception as e:
            print(f"Graph expansion failed (falling back to vector): {e}")

        # Stage 3: Merge, deduplicate, re-rank
        seen = set()
        merged = []
        # Graph results first (they get a distance boost)
        for r in graph_results:
            key = r["text"][:100]
            if key not in seen:
                seen.add(key)
                r["distance"] = r.get("distance", 1.0) * 0.8  # 20% boost
                merged.append(r)
        for r in vector_results:
            key = r["text"][:100]
            if key not in seen:
                seen.add(key)
                merged.append(r)
        merged.sort(key=lambda x: x.get("distance", 999))
        return merged[:k]

    def infer_relationships(self, entities: List[Dict[str, str]], text: str):
        # Simple co-occurrence: link all pairs with "co_occurrence"
        entity_ids = []
        for ent in entities:
            eid = self.add_entity(ent["name"], ent["type"], f"From text: {text[:100]}")
            entity_ids.append(eid)
        for i in range(len(entity_ids)):
            for j in range(i+1, len(entity_ids)):
                self.add_relationship(entity_ids[i], entity_ids[j], "co_occurrence")
                self.add_relationship(entity_ids[j], entity_ids[i], "co_occurrence")  # bidirectional

    def add_memory(self, mem_type: str, text: str, tags: List[str]):
        # Determine memory_type: semantic for facts/entities, episodic for events/conversations
        memory_type = "semantic" if mem_type in ["entity", "summary", "goal", "habit", "decision"] else "episodic"
        with SQLSession(engine) as session:
            tags_str = json.dumps(tags)
            memory = Memory(type=mem_type, text=text, tags=tags_str, memory_type=memory_type)
            session.add(memory)
            session.commit()
            session.refresh(memory)
            # Embed and add to Chroma
            embedding = self.embed_text(text)  # synchronous for simplicity, but should be async
            self.collection.add(
                documents=[text],
                embeddings=[embedding],  # PASS THE EMBEDDING HERE!
                metadatas=[{"type": mem_type, "tags": tags_str, "memory_type": memory_type}],
                ids=[str(memory.id)]
            )

        # Extract entities for user inputs
        if mem_type == "user_input":
            entities = self.extract_entities(text)
            if entities:
                self.infer_relationships(entities, text)

    def add_summary(self, context_id: str, summary: str):
        self.add_memory("summary", summary, ["summary", context_id])

    def recent(self, context_id: str, limit: int = 10) -> List[Memory]:
        with SQLSession(engine) as session:
            statement = select(Memory).where(Memory.tags.contains(f'"{context_id}"')).order_by(Memory.created_at.desc()).limit(limit)
            return session.execute(statement).scalars().all()

    def search_embeddings(self, query: str, k: int = 5, filter_type: str = None, memory_type: str = None) -> List[Dict[str, Any]]:
        query_embedding = self.embed_text(query)  # sync for now
        # For pgvector, do async search
        # But for now, keep Chroma
        where_clause = {}
        if filter_type:
            where_clause["type"] = filter_type
        if memory_type:
            where_clause["memory_type"] = memory_type
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=where_clause if where_clause else None
        )
        memories = []
        for doc, meta, dist in zip(results['documents'][0], results['metadatas'][0], results['distances'][0]):
            memories.append({
                "text": doc,
                "metadata": meta,
                "distance": dist
            })
        return memories

    def get_chat_history(self, session_id: str) -> List[ChatMessage]:
        with SQLSession(engine) as session:
            statement = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp)
            return session.execute(statement).scalars().all()

    def add_chat_message(self, session_id: str, role: str, content: str):
        with SQLSession(engine) as session:
            message = ChatMessage(session_id=session_id, role=role, content=content)
            session.add(message)
            session.commit()

    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        with SQLSession(engine) as session:
            statement = select(UserProfile).where(UserProfile.user_id == user_id)
            return session.execute(statement).scalar_one_or_none()

    def save_user_profile(self, profile: UserProfile):
        with SQLSession(engine) as session:
            session.merge(profile)
            session.commit()

    def add_feedback(self, feedback: Feedback):
        with SQLSession(engine) as session:
            session.add(feedback)
            session.commit()

    def get_positive_examples(self, user_id: str = "default", limit: int = 3) -> List[Feedback]:
        """Retrieve recent positively-rated interactions for few-shot learning."""
        with SQLSession(engine) as session:
            from sqlalchemy import select
            stmt = (
                select(Feedback)
                .where(Feedback.user_id == user_id, Feedback.rating > 0)
                .where(Feedback.user_message.isnot(None))
                .order_by(Feedback.created_at.desc())
                .limit(limit)
            )
            return session.execute(stmt).scalars().all()

    def get_milestones(self, user_id: str) -> List[Milestone]:
        with SQLSession(engine) as session:
            statement = select(Milestone).where(Milestone.user_id == user_id)
            return session.execute(statement).scalars().all()

    def add_milestone(self, milestone: Milestone):
        with SQLSession(engine) as session:
            session.add(milestone)
            session.commit()

    def add_mood_entry(self, mood_entry: MoodEntry):
        with SQLSession(engine) as session:
            session.add(mood_entry)
            session.commit()

    def get_recent_moods(self, user_id: str, limit: int = 7) -> List[MoodEntry]:
        with SQLSession(engine) as session:
            statement = select(MoodEntry).where(MoodEntry.user_id == user_id).order_by(MoodEntry.date.desc()).limit(limit)
            return session.execute(statement).scalars().all()

    def add_habit(self, habit: Habit):
        with SQLSession(engine) as session:
            session.add(habit)
            session.commit()

    def get_habits(self, user_id: str) -> List[Habit]:
        with SQLSession(engine) as session:
            statement = select(Habit).where(Habit.user_id == user_id)
            return session.execute(statement).scalars().all()

    def update_habit_streak(self, habit_id: int, streak: int, last_done):
        with SQLSession(engine) as session:
            habit = session.get(Habit, habit_id)
            if habit:
                habit.streak = streak
                habit.last_done = last_done
                session.commit()

    def add_decision(self, decision: Decision):
        with SQLSession(engine) as session:
            session.add(decision)
            session.commit()

    def get_decisions(self, user_id: str) -> List[Decision]:
        with SQLSession(engine) as session:
            statement = select(Decision).where(Decision.user_id == user_id)
            return session.execute(statement).scalars().all()

    def add_personal_goal(self, goal: PersonalGoal):
        with SQLSession(engine) as session:
            session.add(goal)
            session.commit()

    def get_personal_goals(self, user_id: str) -> List[PersonalGoal]:
        with SQLSession(engine) as session:
            statement = select(PersonalGoal).where(PersonalGoal.user_id == user_id)
            return session.execute(statement).scalars().all()

    def update_goal_status(self, goal_id: int, status: str):
        with SQLSession(engine) as session:
            goal = session.get(PersonalGoal, goal_id)
            if goal:
                goal.status = status
                session.commit()

    def add_activity_log(self, activity: ActivityLog):
        with SQLSession(engine) as session:
            session.add(activity)
            session.commit()

    def get_recent_activities(self, user_id: str, limit: int = 10) -> List[ActivityLog]:
        with SQLSession(engine) as session:
            statement = select(ActivityLog).where(ActivityLog.user_id == user_id).order_by(ActivityLog.timestamp.desc()).limit(limit)
            return session.execute(statement).scalars().all()

    def causal_analysis_mood_habit(self, user_id: str) -> Dict[str, Any]:
        # Simple correlation: avg mood after habit done vs missed
        with SQLSession(engine) as session:
            habits = session.execute(select(Habit).where(Habit.user_id == user_id)).scalars().all()
            analysis = {}
            for h in habits:
                # Moods after last_done
                if h.last_done:
                    moods_after = session.execute(
                        select(MoodEntry).where(MoodEntry.user_id == user_id, MoodEntry.date >= h.last_done.date())
                    ).scalars().all()
                    avg_mood_done = sum(m.mood for m in moods_after) / len(moods_after) if moods_after else 0
                else:
                    avg_mood_done = 0
                # Recent moods overall
                recent_moods = session.execute(
                    select(MoodEntry).where(MoodEntry.user_id == user_id).order_by(MoodEntry.date.desc()).limit(7)
                ).scalars().all()
                avg_mood_recent = sum(m.mood for m in recent_moods) / len(recent_moods) if recent_moods else 0
                analysis[h.name] = {"avg_after_done": avg_mood_done, "recent_avg": avg_mood_recent}
            return analysis

    def populate_knowledge_graph(self, user_id: str):
        # Populate Chroma with entities from goals/habits/decisions
        goals = self.get_personal_goals(user_id)
        habits = self.get_habits(user_id)
        decisions = self.get_decisions(user_id)
        entities = []
        for g in goals:
            entities.append(f"Goal: {g.name} - {g.description}")
        for h in habits:
            entities.append(f"Habit: {h.name} - Streak: {h.streak}")
        for d in decisions:
            entities.append(f"Decision: {d.question} - Outcome: {d.outcome}")
        for ent in entities:
            self.add_memory("entity", ent, ["graph", user_id])  # Tag for graph queries

    def add_cbt_exercise(self, exercise: CbtExercise):
        with SQLSession(engine) as session:
            session.add(exercise)
            session.commit()

    def get_cbt_exercises(self, user_id: str) -> List[CbtExercise]:
        with SQLSession(engine) as session:
            statement = select(CbtExercise).where(CbtExercise.user_id == user_id)
            return session.execute(statement).scalars().all()

    def complete_cbt_exercise(self, exercise_id: int):
        with SQLSession(engine) as session:
            exercise = session.get(CbtExercise, exercise_id)
            if exercise:
                exercise.completed_count += 1
                session.commit()

    def suggest_cbt_exercise(self, user_id: str, mood_level: int) -> Optional[CbtExercise]:
        exercises = self.get_cbt_exercises(user_id)
        if not exercises:
            return None
        # Simple suggestion: for low mood, suggest positive ones
        if mood_level < 5:
            positive = [e for e in exercises if "gratitude" in e.name.lower() or "positive" in e.description.lower()]
            return positive[0] if positive else exercises[0]
        return exercises[0]

    def mood_trend_analysis(self, session_id: str) -> Dict[str, Any]:
        # Simple trend: average mood over last 7 entries for user (assuming session_id = user_id)
        user_id = session_id  # Adjust if session_id != user_id
        recent_moods = self.get_recent_moods(user_id, limit=7)
        if not recent_moods:
            return {"trend": "no_data", "avg_mood": 0, "moods": []}
        avg_mood = sum(m.mood for m in recent_moods) / len(recent_moods)
        trend = "up" if avg_mood > 5 else "down"  # Basic threshold
        return {
            "trend": trend,
            "avg_mood": avg_mood,
            "moods": [m.mood for m in recent_moods],
            "num_entries": len(recent_moods)
        }

    def add_sleep_log(self, hours_slept: float, quality: int = 5, log_date: date = None, user_id: str = "default"):
        if log_date is None:
            log_date = date.today()
        with SQLSession(engine) as session:
            sleep = SleepLog(user_id=user_id, date=log_date, hours_slept=hours_slept, quality=quality)
            session.add(sleep)
            session.commit()
            return sleep

    def add_transaction(self, amount: float, category: str, log_date: date = None, user_id: str = "default"):
        if log_date is None:
            log_date = date.today()
        with SQLSession(engine) as session:
            trans = Transaction(user_id=user_id, date=log_date, amount=amount, category=category)
            session.add(trans)
            session.commit()
            return trans

    def correlate_health_mood(self, user_id: str = "default", days_back: int = 14) -> Dict[str, Any]:
        cutoff = date.today() - timedelta(days=days_back)
        with SQLSession(engine) as session:
            # Recent moods
            moods = session.execute(
                select(MoodEntry).where(
                    MoodEntry.user_id == user_id,
                    MoodEntry.date >= cutoff
                ).order_by(MoodEntry.date)
            ).scalars().all()
            if not moods:
                return {"error": "No recent mood data for correlations.", "sleep_delta": 0, "spend_delta": 0}
            
            # Sleep correlations
            sleeps = session.execute(
                select(SleepLog).where(
                    SleepLog.user_id == user_id,
                    SleepLog.date >= cutoff
                )
            ).scalars().all()
            poor_sleep_moods = []
            good_sleep_moods = []
            for sleep in sleeps:
                next_day = sleep.date + timedelta(days=1)
                day_after = sleep.date + timedelta(days=2)  # Mood might lag 1-2 days
                post_moods = [m for m in moods if m.date.date() >= next_day and m.date.date() <= day_after]
                if post_moods:
                    avg_post = sum(m.mood for m in post_moods) / len(post_moods)
                    if sleep.hours_slept < 6 or sleep.quality < 5:
                        poor_sleep_moods.append(avg_post)
                    else:
                        good_sleep_moods.append(avg_post)
            
            sleep_delta = (
                sum(poor_sleep_moods) / len(poor_sleep_moods) - sum(good_sleep_moods) / len(good_sleep_moods)
                if poor_sleep_moods and good_sleep_moods else 0
            )
            
            # Spend correlations (daily totals)
            daily_spends = {}  # date: total spend (abs(amount) for negatives)
            transes = session.execute(
                select(Transaction).where(
                    Transaction.user_id == user_id,
                    Transaction.date >= cutoff
                )
            ).scalars().all()
            for t in transes:
                d = t.date
                if d not in daily_spends:
                    daily_spends[d] = 0
                daily_spends[d] += abs(t.amount)  # Assume spends are positive for simplicity
            
            low_spend_moods = []
            norm_spend_moods = []
            low_threshold = 20.0  # $20/day
            for d in daily_spends:
                next_day = d + timedelta(days=1)
                post_moods = [m for m in moods if m.date.date() >= next_day and m.date.date() <= next_day + timedelta(days=1)]
                if post_moods:
                    avg_post = sum(m.mood for m in post_moods) / len(post_moods)
                    spend = daily_spends[d]
                    if spend < low_threshold:
                        low_spend_moods.append(avg_post)
                    else:
                        norm_spend_moods.append(avg_post)
            
            spend_delta = (
                sum(low_spend_moods) / len(low_spend_moods) - sum(norm_spend_moods) / len(norm_spend_moods)
                if low_spend_moods and norm_spend_moods else 0
            )
            
            return {
                "sleep_delta": sleep_delta,  # Negative = poor sleep hurts mood
                "spend_delta": spend_delta,  # Positive = low spend helps mood?
                "insights": [
                    f"Sleep impact: {sleep_delta:.1f} mood pts" if abs(sleep_delta) > 1 else None,
                    f"Spend impact: {spend_delta:.1f} mood pts" if abs(spend_delta) > 1 else None
                ]
            }

    def get_recent_sleeps(self, user_id: str = "default", limit: int = 5) -> List[SleepLog]:
        with SQLSession(engine) as session:
            statement = select(SleepLog).where(SleepLog.user_id == user_id).order_by(SleepLog.date.desc()).limit(limit)
            return session.execute(statement).scalars().all()

    def get_recent_transactions(self, user_id: str = "default", limit: int = 5) -> List[Transaction]:
        with SQLSession(engine) as session:
            statement = select(Transaction).where(Transaction.user_id == user_id).order_by(Transaction.date.desc()).limit(limit)
            return session.execute(statement).scalars().all()

    def add_contact(self, name: str, last_contact: date = None, strength: int = 5, entity_id: str = None, user_id: str = "default"):
        if last_contact is None:
            last_contact = date.today()
        with SQLSession(engine) as session:
            contact = Contact(name=name, last_contact=last_contact, strength=strength, entity_id=entity_id, user_id=user_id)
            session.add(contact)
            session.commit()
            session.refresh(contact)
            return contact

    def get_overdue_contacts(self, days: int = 14, user_id: str = "default", min_mood: int = None):
        overdue_date = date.today() - timedelta(days=days)
        with SQLSession(engine) as session:
            query = session.query(Contact).filter(
                Contact.last_contact < overdue_date,
                Contact.user_id == user_id
            )
            # Optional mood tie-in: e.g., if min_mood, join with recent MoodEntry and filter low mood days
            # For MVP, skipping join; expand later if needed
            if min_mood:
                # Placeholder: Could add query = query.outerjoin(MoodEntry).filter(MoodEntry.mood < min_mood)
                pass
            contacts = query.order_by(Contact.strength.desc()).limit(3).all()
            return [
                {
                    "name": c.name,
                    "days_overdue": (date.today() - c.last_contact).days,
                    "strength": c.strength
                }
                for c in contacts
            ]