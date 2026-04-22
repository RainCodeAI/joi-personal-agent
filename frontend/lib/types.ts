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

export type ChatAttachment = {
  id: string;
  kind: "image" | "text" | "file";
  name: string;
  media_type: string;
  size_bytes: number;
  preview_text?: string | null;
};

export type ChatAttachmentInput = {
  id?: string;
  kind: "image" | "text" | "file";
  name: string;
  media_type: string;
  data_url: string;
  size_bytes?: number;
  preview_url?: string;
};

export type Approval = {
  id: string;
  session_id?: string | null;
  tool_name: string;
  args: Record<string, unknown>;
  status: string;
  created_at: string;
  resolved_at?: string | null;
};

export type ProviderInfo = {
  selected: string;
  route: string[];
  errors: Array<Record<string, unknown>>;
};

export type BackendHealth = {
  status: "ok" | "degraded";
  database: {
    available: boolean;
  };
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
  mic_state: "idle" | "requesting" | "recording" | "processing" | "error";
  speaking_state: "idle" | "queued" | "playing" | "interrupted" | "error";
  capture_source: string;
  last_transcript: string;
  recognition_latency_ms?: number | null;
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

export type DiagnosticsResponse = {
  status: string;
  providers: Record<string, Record<string, unknown>>;
  storage: Record<string, unknown>;
  media: Record<string, Record<string, unknown>>;
};

export type PerceptionSignalType =
  | "user_present"
  | "face_visible"
  | "looked_away"
  | "returned_to_frame"
  | "leaned_in"
  | "leaned_back"
  | "expression_smile"
  | "expression_stress"
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
  currentExpression: "smile" | "stress" | "surprise" | "neutral" | null;
  lastSignal: PerceptionSignal | null;
  updatedAt: number;
};
