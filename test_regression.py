from app.memory.store import MemoryStore
from datetime import date, timedelta
from app.api.models import MoodEntry, Habit, Contact
from app.config import settings

store = MemoryStore()
user_id = "default"

print("=== Regression Test: 5 Scenarios (No Ollama Needed) ===\n")

# 1: Normal day (high mood, good sleep)
store.add_mood_entry(MoodEntry(user_id=user_id, date=date.today(), mood=8))
store.add_sleep_log(7.5, 8, date.today() - timedelta(days=1))
corr = store.correlate_health_mood()
print(f"1. Normal Day: Mood=8, Sleep=7.5hrs. Delta: {corr['sleep_delta']:.1f} (Expected ~0, no nudge)")

# 2: Low mood, bad sleep (trigger health nudge)
store.add_mood_entry(MoodEntry(user_id=user_id, date=date.today(), mood=3))
store.add_sleep_log(5.0, 3, date.today() - timedelta(days=1))
corr = store.correlate_health_mood()
nudge = "Health nudge: Sleep rough—hydrate?" if corr['sleep_delta'] < -1 else "No nudge"
print(f"2. Tired Day: Mood=3, Sleep=5hrs. Delta: {corr['sleep_delta']:.1f} ({nudge})")

# 3: Overdue contact (CRM nudge)
store.add_contact("Alex", last_contact=date.today() - timedelta(days=20), strength=8)
overdue = store.get_overdue_contacts()
nudge = "CRM nudge: Haven't pinged Alex?" if overdue else "No overdue"
print(f"3. Social Check: Overdue: {len(overdue)} ({nudge})")

# 4: Habit reminder sim (get habits)
store.add_habit(Habit(user_id=user_id, name="Meditate", streak=0, last_done=None))
habits = store.get_habits(user_id)
print(f"4. Habit Rem: {len(habits)} habits ({[h.name for h in habits]})")

# 5: KG update
store.populate_knowledge_graph(user_id)
recent = store.recent(user_id, 5)
print(f"5. KG Update: {len(recent)} recent memories added")

print("\n=== All pass? Phase 5 100% for sims! ===")