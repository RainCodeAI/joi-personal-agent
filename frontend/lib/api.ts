import {
  Approval,
  AvatarSyncPayload,
  BackendHealth,
  ChatAttachmentInput,
  ChatResponse,
  Connector,
  DesktopActionRequest,
  DesktopActionResponse,
  DiagnosticsResponse,
  MediaSession,
  MediaTranscriptionResponse,
  MemoryItem,
  MemorySearchItem,
  Message,
  PerceptionPolicy,
  PlannerResponse,
  ProfileBundle,
  RealtimeEvent,
  Session,
  SnapshotAnalysis,
  SynthesisMethod,
  SynthesisRecordListResponse,
  SynthesisResponse,
  UserModelCorrectionRequest,
  UserModelCorrectionResponse,
  UserModelPromptPreview,
  UserModelResponse,
} from "@/lib/types";

// When NEXT_PUBLIC_API_BASE_URL is set (desktop shell, Docker), call that backend
// directly. Otherwise default to the same-origin proxy at /api/backend, which
// injects the token server-side so it never ships in the browser bundle.
const CONFIGURED_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || process.env.API_BASE_URL || "";
const API_BASE_URL = CONFIGURED_BASE_URL || "/api/backend";
const IS_PROXY_MODE = CONFIGURED_BASE_URL === "";
// Only used in direct mode; in proxy mode the token stays server-side.
const API_TOKEN = IS_PROXY_MODE
  ? ""
  : process.env.NEXT_PUBLIC_JOI_API_TOKEN || process.env.JOI_API_TOKEN || "";

// Server-side rendering can't fetch the relative proxy path (Node fetch needs an
// absolute URL) and has no browser to hide the token from, so in proxy mode the
// server calls the backend directly with the server-only token.
const USE_SERVER_DIRECT = IS_PROXY_MODE && typeof window === "undefined";
const SERVER_BACKEND_URL =
  process.env.API_BASE_URL || process.env.BACKEND_API_BASE_URL || "http://127.0.0.1:8000";
const SERVER_API_TOKEN = process.env.JOI_API_TOKEN || "";

const REQUEST_TIMEOUT_MS = 35_000;
const RETRY_ATTEMPTS = 3;
const RETRY_BASE_DELAY_MS = 1_000;
const HEALTH_TIMEOUT_MS = 1_800;

function toUrl(path: string) {
  return `${USE_SERVER_DIRECT ? SERVER_BACKEND_URL : API_BASE_URL}${path}`;
}

function authHeaders(): Record<string, string> {
  if (USE_SERVER_DIRECT) {
    return SERVER_API_TOKEN ? { "X-Joi-Api-Token": SERVER_API_TOKEN } : {};
  }
  return API_TOKEN ? { "X-Joi-Api-Token": API_TOKEN } : {};
}

function isRetryable(status: number): boolean {
  return status === 429 || status >= 500;
}

async function apiFetch<T>(
  path: string,
  init?: RequestInit,
  opts?: { retryable?: boolean },
): Promise<T> {
  let lastError: Error | null = null;
  // Non-idempotent POSTs (chat, transcribe) must not be retried: a slow backend
  // turn would otherwise be re-sent and create duplicate messages.
  const maxAttempts = opts?.retryable === false ? 1 : RETRY_ATTEMPTS;

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const controller = new AbortController();
    let timedOut = false;
    const handleExternalAbort = () => controller.abort(init?.signal?.reason);
    if (init?.signal?.aborted) {
      throw new DOMException("Request aborted", "AbortError");
    }
    init?.signal?.addEventListener("abort", handleExternalAbort, { once: true });
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, REQUEST_TIMEOUT_MS);

    try {
      const response = await fetch(toUrl(path), {
        ...init,
        headers: {
          "Content-Type": "application/json",
          ...authHeaders(),
          ...(init?.headers ?? {}),
        },
        cache: "no-store",
        signal: controller.signal,
      });

      clearTimeout(timer);

      if (!response.ok) {
        if (isRetryable(response.status) && attempt < maxAttempts - 1) {
          const delay = RETRY_BASE_DELAY_MS * Math.pow(2, attempt);
          await new Promise((r) => setTimeout(r, delay));
          continue;
        }
        const detail = await response.text();
        throw new Error(detail || `API request failed: ${response.status}`);
      }

      return response.json() as Promise<T>;
    } catch (err) {
      clearTimeout(timer);
      const isAbort = err instanceof DOMException && err.name === "AbortError";
      if (isAbort && init?.signal?.aborted) {
        throw err;
      }
      lastError = isAbort
        ? new Error(
            timedOut
              ? `Request timed out after ${REQUEST_TIMEOUT_MS / 1000}s`
              : "Request aborted",
          )
        : (err as Error);

      const isNetworkError = !isAbort && !(err instanceof Error && err.message.startsWith("API request"));
      if ((isAbort || isNetworkError) && attempt < maxAttempts - 1) {
        const delay = RETRY_BASE_DELAY_MS * Math.pow(2, attempt);
        await new Promise((r) => setTimeout(r, delay));
        continue;
      }
      throw lastError;
    } finally {
      clearTimeout(timer);
      init?.signal?.removeEventListener("abort", handleExternalAbort);
    }
  }

  throw lastError ?? new Error("Request failed after retries");
}

export async function createSession(title?: string) {
  return apiFetch<{ api_version: "v2"; session: Session }>("/api/v2/sessions", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export async function fetchBackendHealth() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);

  try {
    const response = await fetch(toUrl("/health"), {
      cache: "no-store",
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Health check failed: ${response.status}`);
    }

    return response.json() as Promise<BackendHealth>;
  } finally {
    clearTimeout(timer);
  }
}

export async function sendChatMessage(sessionId: string, text: string) {
  return apiFetch<ChatResponse>(
    "/api/v2/chat",
    {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, text }),
    },
    { retryable: false },
  );
}

export type PerceptionContextPayload = {
  camera_active: boolean;
  user_present?: boolean | null;
  expression?: string | null;
  leaned_in?: boolean | null;
};

export async function sendChatMessageWithAttachments(
  sessionId: string,
  text: string,
  attachments: ChatAttachmentInput[],
  options?: {
    clientTurnId?: string;
    signal?: AbortSignal;
    perception?: PerceptionContextPayload;
  },
) {
  return apiFetch<ChatResponse>(
    "/api/v2/chat",
    {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        text,
        attachments,
        client_turn_id: options?.clientTurnId,
        perception: options?.perception,
      }),
      signal: options?.signal,
    },
    { retryable: false },
  );
}

export async function listMessages(sessionId: string) {
  return apiFetch<{ api_version: "v2"; session: Session; messages: Message[] }>(
    `/api/v2/sessions/${sessionId}/messages`,
  );
}

export async function listApprovals(sessionId: string) {
  const params = new URLSearchParams({ session_id: sessionId });
  return apiFetch<{ api_version: "v2"; approvals: Approval[] }>(`/api/v2/approvals?${params.toString()}`);
}

export async function fetchConnectors() {
  return apiFetch<{ api_version: "v2"; connectors: Connector[] }>("/api/v2/connectors");
}

export async function disconnectConnector(connectorId: Connector["id"]) {
  return apiFetch<{ api_version: "v2"; connector: Connector }>(
    `/api/v2/connectors/${connectorId}/disconnect`,
    {
      method: "POST",
      body: JSON.stringify({ confirmed: true }),
    },
  );
}

export async function startGoogleOauth() {
  return apiFetch<{ auth_url: string; state: string }>("/oauth/start");
}

export async function approveAction(approvalId: string) {
  return apiFetch<{ api_version: "v2"; approval: Approval; tool_result?: unknown }>(
    `/api/v2/approvals/${approvalId}/approve`,
    {
      method: "POST",
      body: JSON.stringify({ confirmed: true, client_surface: "web" }),
    },
  );
}

export async function denyAction(approvalId: string) {
  return apiFetch<{ api_version: "v2"; approval: Approval }>(
    `/api/v2/approvals/${approvalId}/deny`,
    {
      method: "POST",
      body: JSON.stringify({ confirmed: true, client_surface: "web" }),
    },
  );
}

export async function runDesktopAction(payload: DesktopActionRequest) {
  return apiFetch<DesktopActionResponse>("/api/v2/desktop/actions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function syncAvatar(sessionId: string, text: string) {
  return apiFetch<AvatarSyncPayload>("/api/v2/avatar/sync", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, text }),
  });
}

export async function fetchMediaSession(sessionId: string) {
  const params = new URLSearchParams({ session_id: sessionId });
  return apiFetch<{ api_version: "v2"; media_session: MediaSession }>(
    `/api/v2/media/session?${params.toString()}`,
  );
}

export async function patchMediaSession(
  payload: {
    session_id: string;
    assistant_turn_id?: string;
    voice_mode?: MediaSession["voice_mode"];
    turn_state?: MediaSession["turn_state"];
    mic_state?: MediaSession["mic_state"];
    speaking_state?: MediaSession["speaking_state"];
    capture_source?: string;
    last_transcript?: string;
    recognition_latency_ms?: number;
    end_of_speech_to_transcript_ms?: number;
    speech_duration_ms?: number;
    speech_detected?: boolean;
    model_latency_ms?: number;
    tts_generation_latency_ms?: number;
    first_audio_latency_ms?: number;
    end_to_end_latency_ms?: number;
    playback_latency_ms?: number;
    last_error?: string;
    interrupted?: boolean;
  },
) {
  return apiFetch<{ api_version: "v2"; media_session: MediaSession }>("/api/v2/media/session", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

async function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

export async function transcribeAudioBlob(
  sessionId: string,
  audio: Blob,
  durationMs?: number,
  options?: {
    voiceMode?: MediaSession["voice_mode"];
    speechDetected?: boolean;
    wakeProbe?: boolean;
  },
) {
  const dataUrl = await blobToDataUrl(audio);
  return apiFetch<MediaTranscriptionResponse>(
    "/api/v2/media/transcribe",
    {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        media_type: audio.type || "audio/webm",
        data_url: dataUrl,
        duration_ms: durationMs,
        voice_mode: options?.voiceMode ?? "push_to_talk",
        speech_detected: options?.speechDetected ?? false,
        // Ambient wake probes transcribe silently (no state/events on the backend).
        wake_probe: options?.wakeProbe ?? false,
      }),
    },
    { retryable: false },
  );
}

export async function fetchRecentMemories() {
  return apiFetch<{ api_version: "v2"; memories: MemoryItem[] }>("/api/v2/memory/recent?limit=12");
}

export async function searchMemories(query: string) {
  const params = new URLSearchParams({ query, mode: "graph", limit: "8" });
  return apiFetch<{ api_version: "v2"; query: string; items: MemorySearchItem[] }>(
    `/api/v2/memory/search?${params.toString()}`,
  );
}

export async function fetchProfile() {
  return apiFetch<ProfileBundle>("/api/v2/profile");
}

export async function patchProfile(payload: Partial<ProfileBundle["profile"]>) {
  return apiFetch<ProfileBundle>("/api/v2/profile", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function fetchPlannerContext() {
  return apiFetch<{ api_version: "v2"; snapshot: PlannerResponse["snapshot"] }>("/api/v2/planner/context");
}

export async function generatePlan(payload: {
  key_tasks: string[];
  focus_areas: string[];
  energy_level: number;
}) {
  return apiFetch<PlannerResponse>("/api/v2/planner/generate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchPerceptionPolicy() {
  return apiFetch<{ api_version: "v2"; policy: PerceptionPolicy }>("/api/v2/perception/policy");
}

export async function patchPerceptionPolicy(patch: Partial<PerceptionPolicy>) {
  return apiFetch<{ api_version: "v2"; policy: PerceptionPolicy }>("/api/v2/perception/policy", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function postActivityState(
  sessionId: string,
  state: "active" | "away" | "returned",
  source = "browser",
): void {
  const params = new URLSearchParams({ session_id: sessionId, state, source });
  fetch(toUrl(`/api/v2/initiative/activity?${params}`), {
    method: "POST",
    cache: "no-store",
    headers: authHeaders(),
  }).catch(() => null);
}

export async function analyzeSnapshot(
  sessionId: string,
  dataUrl: string,
  contextHint?: string,
): Promise<SnapshotAnalysis> {
  const response = await apiFetch<{
    api_version: "v2";
    session_id: string;
    description: string;
    tags: string[];
    captured_at: string;
  }>("/api/v2/vision/analyze", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      data_url: dataUrl,
      context_hint: contextHint,
    }),
  });
  return {
    description: response.description,
    tags: response.tags,
    capturedAt: response.captured_at,
    previewDataUrl: dataUrl,
  };
}

export async function fetchDiagnostics() {
  return apiFetch<DiagnosticsResponse>("/diagnostics/runtime");
}

export async function fetchUserModel(userId = "default") {
  const params = new URLSearchParams({ user_id: userId });
  return apiFetch<UserModelResponse>(`/api/v2/user-model?${params}`);
}

export async function postUserModelCorrection(
  payload: UserModelCorrectionRequest,
  userId = "default",
) {
  const params = new URLSearchParams({ user_id: userId });
  return apiFetch<UserModelCorrectionResponse>(`/api/v2/user-model/correct?${params}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchUserModelPromptPreview(userId = "default") {
  const params = new URLSearchParams({ user_id: userId });
  return apiFetch<UserModelPromptPreview>(`/api/v2/user-model/prompt-preview?${params}`);
}

export async function runUserModelSynthesis(
  sessionId: string,
  method: SynthesisMethod,
  userId = "default",
) {
  const params = new URLSearchParams({ session_id: sessionId, user_id: userId, method });
  return apiFetch<SynthesisResponse>(`/api/v2/user-model/synthesize?${params}`, {
    method: "POST",
  });
}

export async function fetchSynthesisRecords(
  payload: { userId?: string; sessionId?: string; limit?: number } = {},
) {
  const params = new URLSearchParams({
    user_id: payload.userId ?? "default",
    limit: String(payload.limit ?? 25),
  });
  if (payload.sessionId?.trim()) {
    params.set("session_id", payload.sessionId.trim());
  }
  return apiFetch<SynthesisRecordListResponse>(`/api/v2/user-model/synthesis-records?${params}`);
}

export type SettingsShape = {
  airgap: boolean;
  autonomy_level: string;
  enable_proactive_messaging: boolean;
  initiative_enabled: boolean;
  initiative_daily_limit: number;
  initiative_timezone: string;
  initiative_daily_greeting_start: string;
  initiative_daily_greeting_end: string;
  initiative_quiet_hours_start: string;
  initiative_quiet_hours_end: string;
  initiative_focus_mode: boolean;
  initiative_do_not_disturb: boolean;
  initiative_late_night_start: string;
  initiative_late_night_end: string;
  initiative_silence_threshold_minutes: number;
  initiative_allowed_types: string;
  context_commentary_enabled: boolean;
  context_min_confidence: number;
  context_dedup_minutes: number;
  context_allowed_categories: string;
  enable_hardware_nodes: boolean;
  mqtt_broker_host: string;
  mqtt_broker_port: number;
  mqtt_client_id: string;
  mqtt_topic_prefix: string;
  mqtt_node_id: string;
  model_chat: string;
  model_embed: string;
  router_timeout: number;
  gguf_n_ctx: number;
  gguf_n_gpu_layers: number;
};

export async function fetchSettings() {
  return apiFetch<{ api_version: "v2"; settings: SettingsShape }>("/api/v2/settings");
}

export async function patchSettings(payload: Partial<SettingsShape>) {
  return apiFetch<{ api_version: "v2"; settings: SettingsShape }>("/api/v2/settings", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function submitContextFeedback(
  eventId: string,
  action: "useful" | "wrong" | "too_much" | "never_comment",
) {
  const params = new URLSearchParams({ action });
  return apiFetch<{
    api_version: "v2";
    event_id: string;
    feedback: Record<string, unknown>;
  }>(`/api/v2/context/events/${encodeURIComponent(eventId)}/feedback?${params}`, {
    method: "POST",
  });
}

const SSE_EVENT_NAMES = [
  "session.created",
  "message.received",
  "response.started",
  "message.created",
  "message.delta",
  "message.completed",
  "approval.requested",
  "approval.resolved",
  "tool.completed",
  "avatar.state",
  "media.session.updated",
  "media.transcription.completed",
  "media.transcription.failed",
  "tts.ready",
  "settings.updated",
  "perception.snapshot",
  "initiative.emitted",
  "initiative.suppressed",
  "initiative.activity",
  "avatar.life_state_changed",
  "desktop.action.completed",
  "desktop.action.blocked",
  "heartbeat",
] as const;

const SSE_RECONNECT_BASE_MS = 1_000;
const SSE_RECONNECT_MAX_MS = 30_000;
const SSE_MAX_RETRIES = 8;

export function createEventStream(
  sessionId: string,
  onEvent: (event: RealtimeEvent) => void,
): { close: () => void } {
  let source: EventSource | null = null;
  let retries = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let closed = false;

  function connect() {
    if (closed) return;
    // toUrl() may be relative in proxy mode, so resolve against the page origin.
    const streamUrl = new URL(toUrl("/api/v2/events/stream"), window.location.origin);
    streamUrl.searchParams.set("session_id", sessionId);
    streamUrl.searchParams.set("backfill", retries === 0 ? "8" : "0");
    // Direct mode carries the token as a query param (EventSource can't set
    // headers); proxy mode injects it server-side, so API_TOKEN is empty here.
    if (API_TOKEN) {
      streamUrl.searchParams.set("api_token", API_TOKEN);
    }

    source = new EventSource(streamUrl.toString());

    const handleMessage = (message: MessageEvent<string>) => {
      retries = 0;
      try {
        const payload = JSON.parse(message.data) as RealtimeEvent;
        onEvent(payload);
      } catch {
        // Ignore malformed packets.
      }
    };

    source.onmessage = handleMessage;
    for (const name of SSE_EVENT_NAMES) {
      source.addEventListener(name, handleMessage as EventListener);
    }

    source.onerror = () => {
      source?.close();
      source = null;
      if (closed || retries >= SSE_MAX_RETRIES) return;
      const delay = Math.min(SSE_RECONNECT_BASE_MS * Math.pow(2, retries), SSE_RECONNECT_MAX_MS);
      retries++;
      reconnectTimer = setTimeout(connect, delay);
    };
  }

  connect();

  return {
    close() {
      closed = true;
      if (reconnectTimer !== null) clearTimeout(reconnectTimer);
      source?.close();
    },
  };
}
