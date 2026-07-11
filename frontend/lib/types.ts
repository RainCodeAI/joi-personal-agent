export type Session = {
  id: string;
  user_id: string;
  title?: string | null;
  created_at: string;
  updated_at: string;
};

export type Message = {
  id: number;
  session_id: string;
  role: string;
  content: string;
  timestamp: string;
};

export type ToolCall = {
  tool_name: string;
  args: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  status: string;
};

export type DesktopActionName = "open_url" | "show_notification";

export type DesktopActionRequest = {
  session_id?: string | null;
  action: DesktopActionName;
  args: Record<string, unknown>;
  confirmed: boolean;
  source: "web" | "native" | "api";
};

export type DesktopActionResult = {
  action_id: string;
  action: string;
  status: "success" | "blocked" | "error";
  summary: string;
  result: Record<string, unknown>;
  audit_record: Record<string, unknown>;
};

export type DesktopActionResponse = {
  api_version: "v2";
  desktop_action: DesktopActionResult;
};

export type ChatAttachment = {
  id: string;
  kind: "image" | "text" | "file";
  name: string;
  media_type: string;
  size_bytes: number;
  preview_text?: string | null;
  source?: "user_upload" | "screen_capture" | "camera_snapshot";
  capture_metadata?: Record<string, string>;
  ocr_status?: "complete" | "unavailable" | "not_requested" | null;
};

export type ChatAttachmentInput = {
  id?: string;
  kind: "image" | "text" | "file";
  name: string;
  media_type: string;
  data_url: string;
  size_bytes?: number;
  preview_url?: string;
  source?: "user_upload" | "screen_capture" | "camera_snapshot";
  capture_metadata?: Record<string, string>;
};

export type Approval = {
  id: string;
  proposal_id: string;
  session_id?: string | null;
  tool_name: string;
  operation: string;
  args: Record<string, unknown>;
  preview: Record<string, unknown>;
  redacted_preview: Record<string, unknown>;
  args_fingerprint: string;
  local_only: boolean;
  status: string;
  created_at: string;
  expires_at: string;
  resolved_at?: string | null;
  consumed_at?: string | null;
};

export type Connector = {
  id: "gmail" | "calendar";
  label: string;
  connected: boolean;
  capabilities: string[];
  scopes: string[];
};

export type ProviderInfo = {
  selected: string;
  route: string[];
  errors: Array<Record<string, unknown>>;
};

export type ReadinessState = {
  state: "ready" | "degraded" | "disabled";
  summary: string;
};

export type ReadinessMap = Record<string, ReadinessState>;

export type BackendHealth = {
  status: "ok" | "degraded";
  database: {
    available: boolean;
  };
  storage?: {
    available?: boolean;
    database_mode?: string;
    vector_mode?: string;
  };
  media?: {
    available?: boolean;
    tts_available?: boolean;
    stt_available?: boolean;
  };
  realtime?: {
    available?: boolean;
    transport?: string;
    subscriber_count?: number;
  };
  hardware_bridge?: {
    enabled?: boolean;
    available?: boolean;
    note?: string;
  };
  readiness?: ReadinessMap;
  providers: Record<
    string,
    {
      available: boolean;
      note?: string;
      error?: string;
    }
  >;
};

export type AvatarCue = {
  expression: string;
  voice_hint: string;
  should_speak: boolean;
};

export type ChatResponse = {
  api_version: "v2";
  session: Session;
  user_message: Message;
  assistant_message: Message;
  attachments: ChatAttachment[];
  tool_calls: ToolCall[];
  pending_approvals: Approval[];
  emotion: {
    craving_score: number;
    is_dramatic_return: boolean;
  };
  provider: ProviderInfo;
  avatar: AvatarCue;
};

export type AvatarSyncPayload = {
  api_version: "v2";
  session_id: string;
  audio_url: string;
  phoneme_timeline: Array<[number, string]>;
  sentiment: string;
  delivery_style: string;
};

export type MediaSession = {
  session_id: string;
  assistant_turn_id?: string | null;
  voice_mode: "push_to_talk" | "conversation" | "ambient";
  turn_state:
    | "idle"
    | "listening"
    | "speech_detected"
    | "transcribing"
    | "thinking"
    | "speaking"
    | "interrupted"
    | "error";
  mic_state: "idle" | "requesting" | "recording" | "processing" | "error";
  speaking_state: "idle" | "queued" | "playing" | "interrupted" | "error";
  capture_source: string;
  last_transcript: string;
  recognition_latency_ms?: number | null;
  end_of_speech_to_transcript_ms?: number | null;
  speech_duration_ms?: number | null;
  speech_detected: boolean;
  model_latency_ms?: number | null;
  tts_generation_latency_ms?: number | null;
  first_audio_latency_ms?: number | null;
  end_to_end_latency_ms?: number | null;
  playback_latency_ms?: number | null;
  interruption_count: number;
  last_error?: string | null;
  updated_at: string;
};

export type MediaTranscriptionResponse = {
  api_version: "v2";
  media_session: MediaSession;
  transcript: string;
  media_type: string;
  duration_ms?: number | null;
  latency_ms: number;
};

export type RealtimeEvent = {
  api_version: "v2";
  event_id: string;
  event: string;
  source: string;
  session_id?: string | null;
  timestamp: string;
  payload: Record<string, unknown>;
};

export type MemoryItem = {
  id: number;
  type: string;
  text: string;
  tags: string[];
  created_at: string;
  memory_type: string;
};

export type MemorySearchItem = {
  text: string;
  metadata: Record<string, unknown>;
  distance: number;
  source: string;
  matched_entity?: string | null;
};

export type ProfileBundle = {
  api_version: "v2";
  profile: {
    user_id: string;
    name?: string | null;
    email?: string | null;
    birthday?: string | null;
    hobbies?: string | null;
    relationships?: string | null;
    notes?: string | null;
    therapeutic_mode: boolean;
    personality?: string | null;
    humor_level: number;
  };
  moods: Array<{ id: number; user_id: string; date: string; mood: number }>;
  habits: Array<{ id: number; user_id: string; name: string; streak: number; last_done?: string | null }>;
  goals: Array<{ id: number; user_id: string; name: string; description?: string | null; status: string }>;
  decisions: Array<{ id: number; user_id: string; question: string; pros?: string | null; cons?: string | null; outcome?: string | null }>;
  exercises: Array<{ id: number; user_id: string; name: string; description: string; completed_count: number }>;
  activities: Array<{ id: number; user_id: string; app: string; duration: number; timestamp: string }>;
  sleeps: Array<{ id: number; user_id: string; date: string; hours_slept: number; quality: number }>;
  transactions: Array<{ id: number; user_id: string; date: string; amount: number; category: string }>;
  contacts: Array<{ id: number; user_id: string; name: string; last_contact: string; strength: number; entity_id?: string | null }>;
};

export type PlannerSnapshot = {
  user_id: string;
  latest_mood: number;
  mood_trend: Record<string, unknown>;
  health_correlation: Record<string, unknown>;
  overdue_contacts: Array<Record<string, unknown>>;
  active_goals: string[];
  habits: string[];
};

export type PlannerResponse = {
  api_version: "v2";
  provider: string;
  model: string;
  blocks: Array<{ time: string; activity: string }>;
  snapshot: PlannerSnapshot;
};

export type InitiativeDiagnostics = {
  enabled: boolean;
  daily_limit: number;
  daily_count: number;
  remaining_today: number;
  timezone: string;
  daily_greeting: { start: string; end: string; active: boolean };
  quiet_hours: { start: string; end: string; active: boolean };
  late_night: { start: string; end: string; active: boolean };
  focus_mode: boolean;
  do_not_disturb: boolean;
  allowed_types: string[];
  silence_threshold_minutes: number;
  last_emitted_at: string | null;
  last_suppressed: { type: string; reason: string; checked_at: string } | null;
  scheduler: { running: boolean; jobs: Array<{ id: string; name: string; next_run_time: string | null }> };
};

export type DiagnosticsResponse = {
  status: string;
  readiness: ReadinessMap;
  providers: Record<string, Record<string, unknown>>;
  storage: Record<string, unknown>;
  media: Record<string, Record<string, unknown>>;
  realtime: Record<string, unknown>;
  hardware_bridge: Record<string, unknown>;
  initiative?: InitiativeDiagnostics;
  context_events?: Record<string, unknown>;
};

export type LifeStateName = "calm" | "observant" | "resting" | "engaged" | "curious";

export type PerceptionSignalType =
  | "user_present"
  | "face_visible"
  | "looked_away"
  | "returned_to_frame"
  | "leaned_in"
  | "leaned_back"
  | "expression_smile"
  | "expression_possible_tension"
  | "expression_surprise"
  | "expression_neutral"
  | "snapshot_captured"
  | "snapshot_analyzed";

export type PerceptionSignal = {
  signal: PerceptionSignalType;
  timestamp: number;
  confidence?: number;
  payload?: Record<string, unknown>;
};

export type PerceptionPolicy = {
  camera_enabled: boolean;
  screen_access: "disabled" | "manual_only";
  retain_expressions: boolean;
  retain_snapshots: boolean;
  retention_days: number;
  last_updated?: string | null;
};

export type SnapshotAnalysis = {
  description: string;
  tags: string[];
  capturedAt: string;
  previewDataUrl: string;
};

export type PerceptionState = {
  userPresent: boolean;
  faceVisible: boolean;
  leanedIn: boolean;
  currentExpression: "smile" | "possible_tension" | "surprise" | "neutral" | null;
  lastSignal: PerceptionSignal | null;
  updatedAt: number;
};

export type UserModelEvidence = {
  source_type: string;
  source_id?: string | null;
  summary: string;
  observed_at?: string | null;
};

export type UserModelItem = {
  id: string;
  label: string;
  value: string;
  category: string;
  confidence: number;
  evidence_count: number;
  first_seen?: string | null;
  last_seen?: string | null;
  lifecycle: "fresh" | "active" | "archive" | "pinned";
  user_confirmed: boolean;
  hidden: boolean;
  source_summary: string;
  evidence: UserModelEvidence[];
};

export type UserModelSection = {
  key: string;
  title: string;
  description: string;
  items: UserModelItem[];
};

export type UserModelPolicy = {
  inference_enabled: boolean;
  correction_supported: boolean;
  initiative_surface_enabled: boolean;
  min_confidence_to_surface: number;
  stores_raw_files: boolean;
  stores_raw_presence_streams: boolean;
};

export type UserModelResponse = {
  api_version: "v2";
  user_id: string;
  status: "contract_only" | "active";
  generated_at: string;
  policy: UserModelPolicy;
  readable_summary: string;
  sections: UserModelSection[];
};

export type UserModelCorrectionAction = "confirm" | "edit" | "hide" | "delete" | "add";

export type UserModelCorrectionRequest = {
  section_key: string;
  action: UserModelCorrectionAction;
  item_id?: string;
  label?: string;
  value?: string;
  note?: string;
};

export type UserModelCorrectionResponse = {
  api_version: "v2";
  user_id: string;
  correction: {
    id: string;
    user_id: string;
    section_key: string;
    action: UserModelCorrectionAction;
    item_id?: string | null;
    label?: string | null;
    value?: string | null;
    note?: string | null;
    created_at: string;
  };
  user_model: UserModelResponse;
};

export type UserModelPromptPreview = {
  api_version: "v2";
  user_id: string;
  prompt_block: string;
  line_count: number;
};

export type SynthesisMethod = "pattern" | "llm";

export type SynthesisCandidate = {
  candidate_id: string;
  section_key: string;
  label: string;
  value: string;
  confidence: number;
  inference_method: SynthesisMethod | string;
  trigger_phrase: string;
  source_excerpt: string;
  source_message_role: string;
  source_message_index: number;
  blocked_by_correction: boolean;
  duplicate_of_existing: boolean;
};

export type SynthesisRecord = {
  id: string;
  run_id: string;
  user_id: string;
  session_id: string;
  candidate_id: string;
  section_key: string;
  label: string;
  method: SynthesisMethod;
  evidence_excerpt: string;
  confidence: number;
  status: "dry_run" | "skipped" | "written";
  skipped: boolean;
  skipped_reason: string;
  written: boolean;
  dry_run: boolean;
  source_message_role: string;
  source_message_index: number;
  created_at: string;
};

export type SynthesisResponse = {
  api_version: "v2";
  session_id: string;
  user_id: string;
  method: SynthesisMethod;
  dry_run: boolean;
  writes_enabled: boolean;
  candidates: SynthesisCandidate[];
  audit_records: SynthesisRecord[];
  provider: ProviderInfo;
  written_count: number;
  skipped_count: number;
  message_count: number;
  analysed_at: string;
};

export type SynthesisRecordListResponse = {
  api_version: "v2";
  user_id?: string | null;
  session_id?: string | null;
  records: SynthesisRecord[];
};
