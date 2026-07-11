from app.hardware.bridge import HardwareBridgeStore
from app.hardware.mqtt_bridge import MqttBridge
from app.api.media_session import MediaSessionStore
from app.api.perception_policy import PerceptionPolicyStore
from app.api.realtime import RealtimeEventBus
from app.api.runtime_settings import RuntimeSettingsStore
from app.avatar.life_state import LifeStateEngine
from app.desktop_actions import DesktopActionBroker
from app.context_events.service import ContextEventService
from app.context_events.store import ContextEventStore
from app.context_events.feedback import ContextFeedbackStore
from app.initiative.service import InitiativeService
from app.initiative.scheduler import InitiativeScheduler
from app.integrations.outbox import TelegramOutbox
from app.memory.store import MemoryStore
from app.orchestrator.agent import Agent
from app.orchestrator.security.approval import ToolApprovalManager
from app.user_model.store import UserModelCorrectionStore, UserModelSynthesisRecordStore
from app.persistence import runtime_data_dir


_runtime_data = runtime_data_dir()
memory_store = MemoryStore()
agent = Agent(memory_store=memory_store)
approval_manager = ToolApprovalManager(_runtime_data / "pending_approvals.json")
runtime_settings = RuntimeSettingsStore()
desktop_action_broker = DesktopActionBroker()
perception_policy = PerceptionPolicyStore()
event_bus = RealtimeEventBus()
media_sessions = MediaSessionStore(_runtime_data / "media_sessions.json")
hardware_bridge = HardwareBridgeStore()
mqtt_bridge = MqttBridge(hardware_bridge, event_bus)
telegram_outbox = TelegramOutbox(_runtime_data / "telegram_outbox.json")
initiative_service = InitiativeService(outbox=telegram_outbox)
context_events = ContextEventService(
    ContextEventStore(_runtime_data / "context_events.json"),
    ContextFeedbackStore(_runtime_data / "context_feedback.json"),
)
life_state_engine = LifeStateEngine()
initiative_scheduler = InitiativeScheduler(
    initiative_service,
    event_bus,
    memory_store,
    media_sessions,
    context_events=context_events,
    life_state_engine=life_state_engine,
)
user_model_corrections = UserModelCorrectionStore()
user_model_synthesis_records = UserModelSynthesisRecordStore()
