import {
  Approval,
  AvatarSyncPayload,
  ChatAttachmentInput,
  ChatResponse,
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
} from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.API_BASE_URL ||
  "http://127.0.0.1:8000";

function toUrl(path: string) {
  return `${API_BASE_URL}${path}`;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(toUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `API request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function createSession(title?: string) {
  return apiFetch<{ api_version: "v2"; session: Session }>("/api/v2/sessions", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export async function sendChatMessage(sessionId: string, text: string) {
  return apiFetch<ChatResponse>("/api/v2/chat", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, text }),
  });
}

export async function sendChatMessageWithAttachments(
  sessionId: string,
  text: string,
  attachments: ChatAttachmentInput[],
) {
  return apiFetch<ChatResponse>("/api/v2/chat", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, text, attachments }),
  });
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

export async function approveAction(approvalId: string) {
  return apiFetch<{ api_version: "v2"; approval: Approval; tool_result?: unknown }>(
    `/api/v2/approvals/${approvalId}/approve`,
    { method: "POST" },
  );
}

export async function denyAction(approvalId: string) {
  return apiFetch<{ api_version: "v2"; approval: Approval }>(
    `/api/v2/approvals/${approvalId}/deny`,
    { method: "POST" },
  );
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
    mic_state?: MediaSession["mic_state"];
    speaking_state?: MediaSession["speaking_state"];
    capture_source?: string;
    last_transcript?: string;
    recognition_latency_ms?: number;
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
) {
  const dataUrl = await blobToDataUrl(audio);
  return apiFetch<MediaTranscriptionResponse>("/api/v2/media/transcribe", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      media_type: audio.type || "audio/webm",
      data_url: dataUrl,
      duration_ms: durationMs,
    }),
  });
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

export async function fetchSettings() {
  return apiFetch<{
    api_version: "v2";
    settings: {
      airgap: boolean;
      autonomy_level: string;
      enable_proactive_messaging: boolean;
      model_chat: string;
      model_embed: string;
      router_timeout: number;
      gguf_n_ctx: number;
      gguf_n_gpu_layers: number;
    };
  }>("/api/v2/settings");
}

export async function patchSettings(
  payload: Partial<{
    airgap: boolean;
    autonomy_level: string;
    enable_proactive_messaging: boolean;
    model_chat: string;
    model_embed: string;
    router_timeout: number;
    gguf_n_ctx: number;
    gguf_n_gpu_layers: number;
  }>,
) {
  return apiFetch<{
    api_version: "v2";
    settings: {
      airgap: boolean;
      autonomy_level: string;
      enable_proactive_messaging: boolean;
      model_chat: string;
      model_embed: string;
      router_timeout: number;
      gguf_n_ctx: number;
      gguf_n_gpu_layers: number;
    };
  }>("/api/v2/settings", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function createEventStream(sessionId: string, onEvent: (event: RealtimeEvent) => void) {
  const streamUrl = new URL(toUrl("/api/v2/events/stream"));
  streamUrl.searchParams.set("session_id", sessionId);
  streamUrl.searchParams.set("backfill", "8");
  const source = new EventSource(streamUrl.toString());
  const eventNames = [
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
    "heartbeat",
  ];

  const handleMessage = (message: MessageEvent<string>) => {
    try {
      const payload = JSON.parse(message.data) as RealtimeEvent;
      onEvent(payload);
    } catch {
      // Ignore malformed event packets for now.
    }
  };

  source.onmessage = handleMessage;
  for (const eventName of eventNames) {
    source.addEventListener(eventName, handleMessage as EventListener);
  }

  return source;
}
