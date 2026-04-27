from app.hardware.bridge import HardwareBridgeStore
from app.hardware.mqtt_bridge import MqttBridge
from app.api.media_session import MediaSessionStore
from app.api.perception_policy import PerceptionPolicyStore
from app.api.realtime import RealtimeEventBus
from app.api.runtime_settings import RuntimeSettingsStore
from app.avatar.life_state import LifeStateEngine
from app.initiative.service import InitiativeService
from app.initiative.scheduler import InitiativeScheduler
from app.memory.store import MemoryStore
from app.orchestrator.agent import Agent
from app.orchestrator.security.approval import ToolApprovalManager
from app.user_model.store import UserModelCorrectionStore


memory_store = MemoryStore()
agent = Agent(memory_store=memory_store)
approval_manager = ToolApprovalManager()
runtime_settings = RuntimeSettingsStore()
perception_policy = PerceptionPolicyStore()
event_bus = RealtimeEventBus()
media_sessions = MediaSessionStore()
hardware_bridge = HardwareBridgeStore()
mqtt_bridge = MqttBridge(hardware_bridge, event_bus)
initiative_service = InitiativeService()
initiative_scheduler = InitiativeScheduler(initiative_service, event_bus, memory_store, media_sessions)
life_state_engine = LifeStateEngine()
user_model_corrections = UserModelCorrectionStore()
