from app.api.realtime import RealtimeEventBus
from app.api.runtime_settings import RuntimeSettingsStore
from app.memory.store import MemoryStore
from app.orchestrator.agent import Agent
from app.orchestrator.security.approval import ToolApprovalManager


memory_store = MemoryStore()
agent = Agent(memory_store=memory_store)
approval_manager = ToolApprovalManager()
runtime_settings = RuntimeSettingsStore()
event_bus = RealtimeEventBus()
