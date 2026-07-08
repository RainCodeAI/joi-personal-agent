"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState, startTransition } from "react";

import { AvatarSyncPanel } from "@/components/avatar-sync-panel";
import { usePerceptionService } from "@/components/perception-service-provider";
import { VoiceComposer } from "@/components/voice-composer";
import { usePresenceReporter } from "@/hooks/use-presence-reporter";
import {
  approveAction,
  createEventStream,
  createSession,
  denyAction,
  fetchBackendHealth,
  fetchMediaSession,
  fetchPerceptionPolicy,
  listApprovals,
  listMessages,
  patchMediaSession,
  runDesktopAction,
  sendChatMessageWithAttachments,
  submitContextFeedback,
  syncAvatar,
} from "@/lib/api";
import {
  Approval,
  AvatarCue,
  AvatarSyncPayload,
  BackendHealth,
  ChatAttachment,
  ChatAttachmentInput,
  ChatResponse,
  DesktopActionName,
  DesktopActionResult,
  LifeStateName,
  MediaSession,
  Message,
  ReadinessState,
  RealtimeEvent,
} from "@/lib/types";

const SESSION_STORAGE_KEY = "joi-v2-session";
const SPOKEN_REPLIES_STORAGE_KEY = "joi-v2-spoken-replies";
const AUTO_SEND_VOICE_STORAGE_KEY = "joi-v2-auto-send-voice";
const DEV_MODE_STORAGE_KEY = "joi-v2-dev-mode";

type ChatClientProps = {
  initialSessionId?: string | null;
};

type BackendStatus = "checking" | "online" | "degraded" | "offline";
type PresenceMode = "full" | "mini";

type AttachmentDraft = ChatAttachmentInput & {
  preview_url?: string;
  preview_text?: string;
};

type DisplayMessage = Message & {
  attachments?: ChatAttachment[];
  contextEventId?: string;
};

type ApprovalField = {
  label: string;
  value: string;
};

type ApprovalPresentation = {
  title: string;
  summary: string;
  riskLabel: string;
  riskTone: "ok" | "warn";
  fields: ApprovalField[];
  preview?: string;
};

type DesktopActionDraft = {
  action: DesktopActionName;
  args: Record<string, unknown>;
};

type PyWebviewCaptureApi = {
  set_capture_active?: (active: boolean) => Promise<boolean> | boolean;
};

declare global {
  interface Window {
    pywebview?: {
      api?: PyWebviewCaptureApi;
    };
  }
}

const RUNTIME_READINESS_KEYS = [
  "providers",
  "storage",
  "media",
  "realtime",
  "hardware_bridge",
] as const;

type RuntimeReadinessKey = (typeof RUNTIME_READINESS_KEYS)[number];

function formatTimestamp(value: string) {
  try {
    return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return value;
  }
}

function humanizeKey(key: string) {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function valuePreview(value: unknown): string {
  if (value == null) {
    return "Not provided";
  }
  if (typeof value === "string") {
    return value.length > 140 ? `${value.slice(0, 137)}...` : value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map((entry) => valuePreview(entry)).join(", ");
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function apiErrorMessage(error: Error): string {
  if (
    error.message === "Failed to fetch" ||
    error.message.includes("NetworkError") ||
    error.message.includes("timed out")
  ) {
    return "Backend offline: start the FastAPI service on 127.0.0.1:8000";
  }

  return error.message;
}

function readinessTone(state?: ReadinessState["state"]): string {
  if (state === "ready") return "ok";
  if (state === "degraded") return "warn";
  return "";
}

function readinessLabel(state?: ReadinessState["state"]): string {
  if (state === "ready") return "ready";
  if (state === "degraded") return "degraded";
  if (state === "disabled") return "disabled";
  return "unknown";
}

function readinessEntry(health: BackendHealth | null, key: RuntimeReadinessKey) {
  return health?.readiness?.[key];
}

function providerAvailabilitySummary(health: BackendHealth | null): string {
  if (!health) {
    return "not connected";
  }

  const providerEntries = Object.entries(health.providers ?? {});
  const availableCount = providerEntries.filter(([, provider]) => provider.available).length;
  return `${availableCount}/${providerEntries.length} routes available`;
}

function backendStatusCopy(status: BackendStatus, health: BackendHealth | null): string {
  if (status === "checking") {
    return "Checking backend";
  }

  if (status === "offline") {
    return "Backend offline: start the FastAPI service on 127.0.0.1:8000";
  }

  if (status === "degraded") {
    const degradedSystems = RUNTIME_READINESS_KEYS
      .map((key) => [key, readinessEntry(health, key)] as const)
      .filter(([, entry]) => entry?.state === "degraded")
      .map(([key, entry]) => `${humanizeKey(key)} ${entry?.summary.toLowerCase()}`);
    return degradedSystems.length
      ? `Runtime degraded: ${degradedSystems.join(" | ")}`
      : "Runtime degraded";
  }

  return "Backend online";
}

function backendBadgeClass(status: BackendStatus): string {
  if (status === "online") return "ok";
  if (status === "checking") return "";
  return "warn";
}

function approvalPresentation(approval: Approval): ApprovalPresentation {
  const args = approval.args ?? {};
  const toolName = approval.tool_name;
  const fieldEntries = Object.entries(args)
    .filter(([key]) => !["body", "content", "html", "message"].includes(key))
    .slice(0, 4)
    .map(([key, value]) => ({ label: humanizeKey(key), value: valuePreview(value) }));

  const longTextPreview =
    [args.body, args.content, args.html, args.message]
      .map((value) => (typeof value === "string" ? value.trim() : ""))
      .find(Boolean) || undefined;

  switch (toolName) {
    case "send_email":
      return {
        title: "Send an email",
        summary: `Joi wants permission to send an email${typeof args.to === "string" ? ` to ${args.to}` : ""}.`,
        riskLabel: "external action",
        riskTone: "warn",
        fields: fieldEntries,
        preview: longTextPreview,
      };
    case "create_calendar_event":
      return {
        title: "Create a calendar event",
        summary: `Joi wants to add${typeof args.title === "string" ? ` "${args.title}"` : " a new event"} to your calendar.`,
        riskLabel: "calendar write",
        riskTone: "warn",
        fields: fieldEntries,
      };
    case "write_file":
    case "save_file":
      return {
        title: "Write a local file",
        summary: `Joi wants permission to write${typeof args.path === "string" ? ` ${args.path}` : " a local file"}.`,
        riskLabel: "filesystem write",
        riskTone: "warn",
        fields: fieldEntries,
        preview: longTextPreview,
      };
    case "delete_file":
    case "remove_file":
      return {
        title: "Delete a local file",
        summary: `Joi wants permission to delete${typeof args.path === "string" ? ` ${args.path}` : " a local file"}.`,
        riskLabel: "destructive",
        riskTone: "warn",
        fields: fieldEntries,
      };
    case "web_search":
      return {
        title: "Run a web search",
        summary: `Joi wants to search the web${typeof args.query === "string" ? ` for "${args.query}"` : ""}.`,
        riskLabel: "read only",
        riskTone: "ok",
        fields: fieldEntries,
      };
    default:
      return {
        title: humanizeKey(toolName),
        summary: `Joi wants permission to run ${humanizeKey(toolName).toLowerCase()}.`,
        riskLabel: "tool action",
        riskTone: "warn",
        fields: fieldEntries,
        preview: longTextPreview,
      };
  }
}

async function fileToAttachmentDraft(file: File): Promise<AttachmentDraft> {
  const data_url = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });

  const kind = file.type.startsWith("image/")
    ? "image"
    : file.type.startsWith("text/")
      ? "text"
      : "file";
  const preview_text = kind === "text" ? (await file.text()).slice(0, 240) : undefined;

  return {
    id: `${file.name}-${file.lastModified}`,
    kind,
    name: file.name,
    media_type: file.type || "application/octet-stream",
    data_url,
    size_bytes: file.size,
    preview_url: kind === "image" ? data_url : undefined,
    preview_text,
  };
}

function toAttachmentResource(draft: AttachmentDraft): ChatAttachment {
  return {
    id: draft.id ?? draft.name,
    kind: draft.kind,
    name: draft.name,
    media_type: draft.media_type,
    size_bytes: draft.size_bytes ?? 0,
    preview_text: draft.preview_text ?? null,
    source: draft.source ?? "user_upload",
    capture_metadata: draft.capture_metadata ?? {},
  };
}

async function captureSelectedScreen(): Promise<AttachmentDraft> {
  if (!navigator.mediaDevices?.getDisplayMedia) {
    throw new Error("Screen capture is not supported in this browser.");
  }

  const stream = await navigator.mediaDevices.getDisplayMedia({
    video: true,
    audio: false,
  });
  try {
    const videoTrack = stream.getVideoTracks()[0];
    const trackSettings = videoTrack?.getSettings();
    const video = document.createElement("video");
    video.srcObject = stream;
    video.muted = true;
    video.playsInline = true;
    await new Promise<void>((resolve, reject) => {
      video.onloadedmetadata = () => resolve();
      video.onerror = () => reject(new Error("The selected screen could not be read."));
    });
    await video.play();

    const maxDimension = 1920;
    const scale = Math.min(1, maxDimension / Math.max(video.videoWidth, video.videoHeight));
    const width = Math.max(1, Math.round(video.videoWidth * scale));
    const height = Math.max(1, Math.round(video.videoHeight * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("Screen capture canvas is unavailable.");
    }
    context.drawImage(video, 0, 0, width, height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.86);
    const estimatedBytes = Math.max(0, Math.floor((dataUrl.length - dataUrl.indexOf(",") - 1) * 0.75));
    const capturedAt = new Date();
    return {
      id: crypto.randomUUID(),
      kind: "image",
      name: `screen-${capturedAt.toISOString().replace(/[:.]/g, "-")}.jpg`,
      media_type: "image/jpeg",
      data_url: dataUrl,
      size_bytes: estimatedBytes,
      preview_url: dataUrl,
      preview_text: "One-shot screen capture. Raw image is discarded after this chat request.",
      source: "screen_capture",
      capture_metadata: {
        display_surface: String(trackSettings?.displaySurface ?? "unknown"),
        source_label: videoTrack?.label || "Selected screen or window",
        width: String(video.videoWidth),
        height: String(video.videoHeight),
      },
    };
  } finally {
    stream.getTracks().forEach((track) => track.stop());
  }
}

async function setNativeCaptureIndicator(active: boolean) {
  try {
    await window.pywebview?.api?.set_capture_active?.(active);
  } catch {
    // Browser launches do not expose the native shell bridge.
  }
}

export function ChatClient({ initialSessionId }: ChatClientProps) {
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId ?? null);
  const sessionIdRef = useRef<string | null>(initialSessionId ?? null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [events, setEvents] = useState<RealtimeEvent[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [selectedApprovalId, setSelectedApprovalId] = useState<string | null>(null);
  const [desktopUrlDraft, setDesktopUrlDraft] = useState("https://example.com");
  const [desktopNotificationTitle, setDesktopNotificationTitle] = useState("Joi");
  const [desktopNotificationMessage, setDesktopNotificationMessage] = useState("Joi is running locally.");
  const [pendingDesktopAction, setPendingDesktopAction] = useState<DesktopActionDraft | null>(null);
  const [desktopActionResult, setDesktopActionResult] = useState<DesktopActionResult | null>(null);
  const [desktopActionBusy, setDesktopActionBusy] = useState(false);
  const [contextFeedbackPending, setContextFeedbackPending] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [attachments, setAttachments] = useState<AttachmentDraft[]>([]);
  const [status, setStatus] = useState("Checking backend");
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");
  const [backendHealth, setBackendHealth] = useState<BackendHealth | null>(null);
  const [provider, setProvider] = useState("pending");
  const [streamingText, setStreamingText] = useState("");
  const [avatarCue, setAvatarCue] = useState<AvatarCue | null>(null);
  const [avatarSyncPayload, setAvatarSyncPayload] = useState<AvatarSyncPayload | null>(null);
  const [lifeState, setLifeState] = useState<LifeStateName>("calm");
  const [presenceMode, setPresenceMode] = useState<PresenceMode>("full");
  const [mediaSession, setMediaSession] = useState<MediaSession | null>(null);
  const [spokenRepliesEnabled, setSpokenRepliesEnabled] = useState(true);
  const spokenRepliesEnabledRef = useRef(true);
  const [autoSendVoiceEnabled, setAutoSendVoiceEnabled] = useState(true);
  // Developer view keeps raw telemetry (event stream, VRM audit, phoneme track,
  // desktop actions) out of the default "room" but a click away when needed.
  const [devMode, setDevMode] = useState(false);
  const [avatarSyncLoading, setAvatarSyncLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const isSendingRef = useRef(false);
  const {
    perceptionState,
    perceptionExpression,
    lastSnapshotAnalysis,
    setSessionId: setPerceptionSessionId,
    clearLastSnapshotAnalysis,
  } = usePerceptionService();
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const chatAbortControllerRef = useRef<AbortController | null>(null);
  const activeAssistantTurnIdRef = useRef<string | null>(null);
  const assistantInterruptedRef = useRef(false);

  useEffect(() => {
    let active = true;

    async function probeBackend() {
      try {
        const health = await fetchBackendHealth();
        if (!active) return;
        const nextStatus: BackendStatus = health.status === "ok" ? "online" : "degraded";
        setBackendHealth(health);
        setBackendStatus(nextStatus);
        setStatus((current) =>
          current === "Checking backend" || current.startsWith("Backend offline")
            ? backendStatusCopy(nextStatus, health)
            : current,
        );
      } catch {
        if (!active) return;
        setBackendHealth(null);
        setBackendStatus("offline");
        setStatus(backendStatusCopy("offline", null));
      }
    }

    void probeBackend();
    const timer = window.setInterval(() => void probeBackend(), 15_000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const stored = window.localStorage.getItem(SPOKEN_REPLIES_STORAGE_KEY);
    if (stored === "off") {
      setSpokenRepliesEnabled(false);
    }
    const storedAutoSend = window.localStorage.getItem(AUTO_SEND_VOICE_STORAGE_KEY);
    if (storedAutoSend === "off") {
      setAutoSendVoiceEnabled(false);
    }
    if (window.localStorage.getItem(DEV_MODE_STORAGE_KEY) === "on") {
      setDevMode(true);
    }
  }, []);

  function handleDevModeToggle() {
    setDevMode((current) => {
      const next = !current;
      try {
        window.localStorage.setItem(DEV_MODE_STORAGE_KEY, next ? "on" : "off");
      } catch {
        // localStorage unavailable — dev view still toggles for the session.
      }
      return next;
    });
  }

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(
      SPOKEN_REPLIES_STORAGE_KEY,
      spokenRepliesEnabled ? "on" : "off",
    );
    spokenRepliesEnabledRef.current = spokenRepliesEnabled;
  }, [spokenRepliesEnabled]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(
      AUTO_SEND_VOICE_STORAGE_KEY,
      autoSendVoiceEnabled ? "on" : "off",
    );
  }, [autoSendVoiceEnabled]);

  // Keep refs and app-level services in sync with the active chat session.
  useEffect(() => {
    sessionIdRef.current = sessionId;
    setPerceptionSessionId(sessionId);
  }, [sessionId, setPerceptionSessionId]);

  useEffect(() => {
    isSendingRef.current = isSending;
  }, [isSending]);

  usePresenceReporter(sessionId);

  useEffect(() => {
    const stored =
      typeof window !== "undefined" ? window.sessionStorage.getItem(SESSION_STORAGE_KEY) : null;
    if (!sessionId && stored) {
      setSessionId(stored);
      return;
    }

    if (backendStatus === "checking" || backendStatus === "offline") {
      return;
    }

    if (!sessionId) {
      createSession("Joi Web Session")
        .then((result) => {
          if (typeof window !== "undefined") {
            window.sessionStorage.setItem(SESSION_STORAGE_KEY, result.session.id);
          }
          setSessionId(result.session.id);
          setStatus("Session ready");
        })
        .catch((error: Error) => {
          setStatus(apiErrorMessage(error));
          setBackendStatus("offline");
        });
    }
  }, [backendStatus, sessionId]);

  useEffect(() => {
    if (!sessionId || backendStatus === "checking" || backendStatus === "offline") {
      return;
    }

    void Promise.all([listMessages(sessionId), listApprovals(sessionId), fetchMediaSession(sessionId)])
      .then(([messageResponse, approvalsResponse, mediaResponse]) => {
        setMessages(messageResponse.messages);
        setApprovals(approvalsResponse.approvals);
        setMediaSession(mediaResponse.media_session);
      })
      .catch((error: Error) => {
        setStatus(`Bootstrap error: ${apiErrorMessage(error)}`);
      });
  }, [backendStatus, sessionId]);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    const source = createEventStream(sessionId, (event: RealtimeEvent) => {
      const eventTurnId =
        typeof event.payload.client_turn_id === "string"
          ? event.payload.client_turn_id
          : null;
      const isAssistantTurnEvent =
        event.event === "response.started" ||
        event.event === "message.delta" ||
        event.event === "message.completed" ||
        event.event === "avatar.state";
      if (
        isAssistantTurnEvent &&
        eventTurnId &&
        eventTurnId !== activeAssistantTurnIdRef.current
      ) {
        return;
      }

      startTransition(() => {
        setEvents((current) => [event, ...current].slice(0, 30));
      });

      if (event.event === "response.started") {
        setStreamingText("");
        setStatus("Joi is composing a response");
      }

      if (event.event === "message.delta") {
        const delta = typeof event.payload.delta === "string" ? event.payload.delta : "";
        if (delta) {
          setStreamingText((current) => `${current}${delta}`);
          setStatus("Streaming assistant response");
        }
      }

      if (event.event === "message.completed") {
        const eventProvider = event.payload.provider as { selected?: string } | undefined;
        if (eventProvider?.selected) {
          setProvider(eventProvider.selected);
        }
      }

      if (event.event === "approval.requested") {
        const approval = event.payload.approval as Approval | undefined;
        if (approval) {
          setApprovals((current) => [approval, ...current.filter((item) => item.id !== approval.id)]);
          setSelectedApprovalId(approval.id);
        }
        setStatus("Approval required");
      }

      if (event.event === "approval.resolved") {
        const approval = event.payload.approval as Approval | undefined;
        if (approval) {
          setApprovals((current) => current.filter((item) => item.id !== approval.id));
          setSelectedApprovalId((current) => (current === approval.id ? null : current));
        }
        setStatus("Approval resolved");
      }

      if (event.event === "avatar.state") {
        const cue = event.payload.avatar as AvatarCue | undefined;
        if (cue) {
          setAvatarCue(cue);
        }
      }

      if (event.event === "avatar.life_state_changed") {
        const ls = event.payload.life_state as LifeStateName | undefined;
        if (ls) setLifeState(ls);
      }

      if (event.event === "media.session.updated") {
        const payload = event.payload.media_session as MediaSession | undefined;
        if (payload) {
          setMediaSession(payload);
        }
      }

      if (event.event === "media.transcription.completed") {
        const payload = event.payload.media_session as MediaSession | undefined;
        if (payload) {
          setMediaSession(payload);
        }
        setStatus("Voice transcription ready");
      }

      if (event.event === "media.transcription.failed") {
        const payload = event.payload.media_session as MediaSession | undefined;
        if (payload) {
          setMediaSession(payload);
        }
        setStatus("Voice transcription failed");
      }

      if (event.event === "tts.ready") {
        const payload = event.payload as Omit<AvatarSyncPayload, "api_version" | "session_id">;
        if (payload.audio_url) {
          setAvatarSyncPayload({
            api_version: "v2",
            session_id: sessionId,
            audio_url: payload.audio_url,
            phoneme_timeline: (payload.phoneme_timeline ?? []) as Array<[number, string]>,
            sentiment: String(payload.sentiment ?? "neutral"),
            delivery_style: String(payload.delivery_style ?? "normal"),
          });
          setAvatarSyncLoading(false);
        }
        const eventMediaSession = event.payload.media_session as MediaSession | undefined;
        if (eventMediaSession) {
          setMediaSession(eventMediaSession);
        }
      }

      if (event.event === "initiative.emitted") {
        const candidate = event.payload.candidate as
          | {
              message?: string;
              type?: string;
              session_id?: string;
              context_event_id?: string;
            }
          | undefined;
        const message = candidate?.message;
        if (message && sessionId) {
          const contextEventId =
            candidate?.type === "context_commentary"
              ? candidate.context_event_id
              : undefined;
          const initiativeMsg: DisplayMessage = {
            id: Date.now(),
            session_id: candidate?.session_id ?? sessionId,
            role: "assistant",
            content: message,
            timestamp: new Date().toISOString(),
            contextEventId,
          };
          startTransition(() => {
            setMessages((current) => [...current, initiativeMsg]);
          });
          setStatus(`Joi: ${candidate?.type ?? "initiative"}`);
          if (
            spokenRepliesEnabledRef.current &&
            typeof document !== "undefined" &&
            document.visibilityState === "visible"
          ) {
            setAvatarSyncLoading(true);
            syncAvatar(sessionId, message)
              .then((syncPayload) => {
                setAvatarSyncPayload(syncPayload);
              })
              .catch(() => {
                /* non-fatal — TTS unavailable */
              })
              .finally(() => {
                setAvatarSyncLoading(false);
              });
          }
        }
      }

      if (event.event === "desktop.action.completed" || event.event === "desktop.action.blocked") {
        const payload = event.payload.desktop_action as DesktopActionResult | undefined;
        if (payload) {
          setDesktopActionResult(payload);
        }
      }
    });

    return () => {
      source.close();
    };
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: messages.length > 0 ? "smooth" : "auto", block: "end" });
  }, [messages, streamingText]);

  async function handleAttachmentSelect(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (!files.length) {
      return;
    }

    setStatus("Reading attachments");
    try {
      const drafts = await Promise.all(files.map(fileToAttachmentDraft));
      setAttachments((current) => [...current, ...drafts]);
      setStatus(`${files.length} attachment(s) ready`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Attachment read failed");
    } finally {
      event.target.value = "";
    }
  }

  async function handleScreenCapture() {
    if (isSending) {
      return;
    }
    setStatus("Checking screen-capture permission");
    try {
      const response = await fetchPerceptionPolicy();
      if (response.policy.screen_access !== "manual_only") {
        setStatus("Screen capture is disabled. Enable manual capture in Settings.");
        return;
      }
      setStatus("Choose a screen or window to share");
      await setNativeCaptureIndicator(true);
      const capture = await captureSelectedScreen();
      setAttachments((current) => [...current, capture]);
      setStatus("Screen capture ready. Add a question, then send it to Joi.");
    } catch (error) {
      if (error instanceof DOMException && error.name === "NotAllowedError") {
        setStatus("Screen capture cancelled.");
        return;
      }
      setStatus(error instanceof Error ? error.message : "Screen capture failed");
    } finally {
      await setNativeCaptureIndicator(false);
    }
  }

  useEffect(() => {
    const handleNativeCapture = () => {
      void handleScreenCapture();
    };
    window.addEventListener("joi:native-look-at-this", handleNativeCapture);
    return () => window.removeEventListener("joi:native-look-at-this", handleNativeCapture);
  });

  async function handleAvatarSync(messageId: number, text: string, cue: AvatarCue) {
    setAvatarCue(cue);

    if (!sessionId || !cue.should_speak || !spokenRepliesEnabled || !text.trim()) {
      return;
    }

    setAvatarSyncLoading(true);
    try {
      const payload = await syncAvatar(sessionId, text);
      setAvatarSyncPayload(payload);
      setStatus(`Avatar synced for message ${messageId}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Avatar sync failed");
    } finally {
      setAvatarSyncLoading(false);
    }
  }

  async function handlePlaybackStateChange(state: {
    speakingState: "playing" | "idle";
    playbackLatencyMs?: number;
  }) {
    if (!sessionId) {
      return;
    }
    if (state.speakingState === "idle" && assistantInterruptedRef.current) {
      return;
    }
    if (state.speakingState === "playing") {
      assistantInterruptedRef.current = false;
    }

    try {
      const firstAudioLatencyMs = state.playbackLatencyMs;
      const endToEndLatencyMs =
        firstAudioLatencyMs === undefined
          ? undefined
          : [
              mediaSession?.end_of_speech_to_transcript_ms,
              mediaSession?.model_latency_ms,
              mediaSession?.tts_generation_latency_ms,
              firstAudioLatencyMs,
            ].reduce<number>(
              (total, value) => total + (typeof value === "number" ? value : 0),
              0,
            );
      const response = await patchMediaSession({
        session_id: sessionId,
        speaking_state: state.speakingState,
        turn_state: state.speakingState === "playing" ? "speaking" : "idle",
        playback_latency_ms: state.playbackLatencyMs,
        first_audio_latency_ms: firstAudioLatencyMs,
        end_to_end_latency_ms: endToEndLatencyMs,
      });
      setMediaSession(response.media_session);
    } catch {
      // Ignore playback session sync failures and preserve local playback.
    }
  }

  async function handleVoiceTranscript(transcript: string) {
    const cleanedTranscript = transcript.trim();
    if (!cleanedTranscript) {
      return;
    }

    if (
      autoSendVoiceEnabled &&
      sessionId &&
      !isSendingRef.current &&
      !draft.trim() &&
      attachments.length === 0
    ) {
      setStatus("Sending voice message");
      try {
        const response = await patchMediaSession({
          session_id: sessionId,
          turn_state: "thinking",
        });
        setMediaSession(response.media_session);
      } catch {
        // Chat remains usable if voice-state telemetry cannot be updated.
      }
      await submitChatMessage(cleanedTranscript, []);
      return;
    }

    setDraft((current) => (current.trim() ? `${current.trim()} ${cleanedTranscript}` : cleanedTranscript));
    setStatus(
      autoSendVoiceEnabled && (draft.trim() || attachments.length > 0)
        ? "Voice transcript appended for review"
        : "Voice transcript appended to draft",
    );
  }

  async function handleInterruptPlayback(statusMessage = "Voice playback interrupted") {
    const interruptedTurnId = activeAssistantTurnIdRef.current;
    assistantInterruptedRef.current = true;
    activeAssistantTurnIdRef.current = null;
    chatAbortControllerRef.current?.abort();
    chatAbortControllerRef.current = null;
    setAvatarSyncPayload(null);
    setAvatarSyncLoading(false);
    setStreamingText("");
    isSendingRef.current = false;
    setIsSending(false);
    setStatus(statusMessage);

    if (!sessionId) {
      return;
    }

    try {
      const response = await patchMediaSession({
        session_id: sessionId,
        assistant_turn_id: interruptedTurnId ?? undefined,
        speaking_state: "interrupted",
        turn_state: "interrupted",
        interrupted: true,
      });
      setMediaSession(response.media_session);
    } catch {
      // Preserve the local stop even if media-session sync fails.
    }
  }

  async function handleSpokenRepliesToggle() {
    const nextEnabled = !spokenRepliesEnabled;
    setSpokenRepliesEnabled(nextEnabled);

    if (!nextEnabled) {
      await handleInterruptPlayback("Spoken replies muted");
      return;
    }

    setStatus("Spoken replies enabled");
  }

  function handleAutoSendVoiceToggle() {
    const nextEnabled = !autoSendVoiceEnabled;
    setAutoSendVoiceEnabled(nextEnabled);
    setStatus(nextEnabled ? "Voice auto-send enabled" : "Voice auto-send disabled");
  }

  async function submitChatMessage(
    text: string,
    attachmentDrafts: AttachmentDraft[],
  ) {
    if (!sessionId || isSendingRef.current || (!text.trim() && attachmentDrafts.length === 0)) {
      return;
    }

    const cleanedText = text.trim();
    const clientTurnId = crypto.randomUUID();
    const abortController = new AbortController();
    activeAssistantTurnIdRef.current = clientTurnId;
    assistantInterruptedRef.current = false;
    chatAbortControllerRef.current?.abort();
    chatAbortControllerRef.current = abortController;
    const optimisticUser: DisplayMessage = {
      id: Date.now(),
      session_id: sessionId,
      role: "user",
      content: cleanedText || (attachmentDrafts.length === 1 ? `Shared attachment: ${attachmentDrafts[0].name}` : `Shared ${attachmentDrafts.length} attachments`),
      timestamp: new Date().toISOString(),
      attachments: attachmentDrafts.map(toAttachmentResource),
    };

    startTransition(() => {
      setMessages((current) => [...current, optimisticUser]);
    });
    setDraft("");
    setStreamingText("");
    isSendingRef.current = true;
    setIsSending(true);
    setStatus("Sending message");
    try {
      const response = await patchMediaSession({
        session_id: sessionId,
        assistant_turn_id: clientTurnId,
        turn_state: "thinking",
      });
      setMediaSession(response.media_session);
    } catch {
      // Chat remains usable if voice-state telemetry cannot be updated.
    }

    // Only send live perception when the camera is actively sensing (a fresh
    // signal in the last ~10s), so Joi never claims to see with the camera off.
    const cameraActive =
      perceptionState.lastSignal !== null && Date.now() - perceptionState.updatedAt < 10_000;
    const perception = cameraActive
      ? {
          camera_active: true,
          user_present: perceptionState.userPresent,
          expression: perceptionState.currentExpression,
          leaned_in: perceptionState.leanedIn,
        }
      : undefined;

    try {
      const response: ChatResponse = await sendChatMessageWithAttachments(
        sessionId,
        cleanedText,
        attachmentDrafts.map(({ preview_url, preview_text, ...attachment }) => attachment),
        {
          clientTurnId,
          signal: abortController.signal,
          perception,
        },
      );
      if (activeAssistantTurnIdRef.current !== clientTurnId) {
        return;
      }

      setProvider(response.provider.selected || "router");
      const approvalResponse = await listApprovals(sessionId);
      setApprovals(approvalResponse.approvals);
      startTransition(() => {
        setMessages((current) => [
          ...current.filter((message) => message.id !== optimisticUser.id),
          { ...response.user_message, attachments: response.attachments },
          response.assistant_message,
        ]);
      });
      setAttachments((current) => (current === attachmentDrafts ? [] : current));
      setStreamingText("");
      setStatus(approvalResponse.approvals.length ? "Awaiting approval" : "Response complete");
      await handleAvatarSync(
        response.assistant_message.id,
        response.assistant_message.content,
        response.avatar,
      );
    } catch (error) {
      if (
        abortController.signal.aborted ||
        (error instanceof DOMException && error.name === "AbortError")
      ) {
        return;
      }
      setStatus(error instanceof Error ? error.message : "Failed to send message");
      startTransition(() => {
        setMessages((current) => current.filter((message) => message.id !== optimisticUser.id));
      });
    } finally {
      if (chatAbortControllerRef.current === abortController) {
        chatAbortControllerRef.current = null;
        isSendingRef.current = false;
        setIsSending(false);
      }
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitChatMessage(draft, attachments);
  }

  async function handleApprovalAction(approvalId: string, decision: "approve" | "deny") {
    if (!sessionId) {
      return;
    }

    setStatus(`${decision === "approve" ? "Approving" : "Denying"} action`);
    try {
      if (decision === "approve") {
        const response = await approveAction(approvalId);
        const toolResult = response.tool_result as { status?: string; result?: { status?: string } } | undefined;
        const resultStatus = toolResult?.result?.status ?? toolResult?.status;
        if (resultStatus) {
          setStatus(`Approval approved: ${resultStatus}`);
        }
      } else {
        await denyAction(approvalId);
      }
      const approvalResponse = await listApprovals(sessionId);
      setApprovals(approvalResponse.approvals);
      setSelectedApprovalId((current) => (current === approvalId ? null : current));
      if (decision === "deny") {
        setStatus("Approval denied");
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Approval action failed");
    }
  }

  async function handleContextFeedback(
    eventId: string,
    action: "useful" | "wrong" | "too_much" | "never_comment",
  ) {
    if (contextFeedbackPending === eventId) {
      return;
    }
    setContextFeedbackPending(eventId);
    try {
      await submitContextFeedback(eventId, action);
      setMessages((current) =>
        current.map((message) =>
          message.contextEventId === eventId
            ? { ...message, contextEventId: undefined }
            : message,
        ),
      );
      setStatus(`Context feedback recorded: ${action.replaceAll("_", " ")}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Context feedback failed");
    } finally {
      setContextFeedbackPending(null);
    }
  }

  function stageDesktopAction(action: DesktopActionName, args: Record<string, unknown>) {
    setPendingDesktopAction({ action, args });
    setDesktopActionResult(null);
    setStatus(`Review ${humanizeKey(action).toLowerCase()} action`);
  }

  async function executePendingDesktopAction() {
    if (!pendingDesktopAction || desktopActionBusy) {
      return;
    }

    setDesktopActionBusy(true);
    setDesktopActionResult(null);
    setStatus(`Running ${humanizeKey(pendingDesktopAction.action).toLowerCase()}`);
    try {
      const response = await runDesktopAction({
        session_id: sessionId,
        action: pendingDesktopAction.action,
        args: pendingDesktopAction.args,
        confirmed: true,
        source: "web",
      });
      setDesktopActionResult(response.desktop_action);
      setPendingDesktopAction(null);
      setStatus(response.desktop_action.summary);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Desktop action failed");
    } finally {
      setDesktopActionBusy(false);
    }
  }

  const selectedApproval =
    approvals.find((approval) => approval.id === selectedApprovalId) ?? null;
  const showPromptSuggestions =
    messages.length === 0 && streamingText.length === 0 && !draft.trim() && attachments.length === 0;

  return (
    <div className="page-body chat-page-body">
      <div className="chat-layout">
        <section className="panel chat-main-panel">
          <div className="chat-panel-header">
            <h2>Conversation</h2>
            <p className="panel-copy">
              Talk to me — type, speak, or share what you&apos;re looking at.
            </p>
          </div>

          <div className="message-list">
            {showPromptSuggestions ? (
              <div className="prompt-suggestions">
                <p className="prompt-suggestions-label">Start a conversation</p>
                <div className="prompt-chips">
                  {[
                    "What's on my calendar today?",
                    "Summarise my recent notes",
                    "Set a reminder for me",
                    "How are you feeling?",
                  ].map((suggestion) => (
                    <button
                      key={suggestion}
                      className="prompt-chip"
                      type="button"
                      onClick={() => setDraft(suggestion)}
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {messages.map((message) => (
              <article key={`${message.id}-${message.timestamp}`} className="message-card" data-role={message.role}>
                <header>
                  <span>{message.role}</span>
                  <span>{formatTimestamp(message.timestamp)}</span>
                </header>
                <p>{message.content}</p>
                {message.contextEventId ? (
                  <div className="button-row">
                    {(
                      [
                        ["useful", "Useful"],
                        ["wrong", "Wrong"],
                        ["too_much", "Too much"],
                        ["never_comment", "Never comment on this"],
                      ] as const
                    ).map(([action, label]) => (
                      <button
                        className="button ghost"
                        key={action}
                        type="button"
                        disabled={contextFeedbackPending === message.contextEventId}
                        onClick={() =>
                          void handleContextFeedback(message.contextEventId!, action)
                        }
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                ) : null}
                {message.attachments?.length ? (
                  <div className="attachment-list">
                    {message.attachments.map((attachment) => (
                      <div className="attachment-card" key={attachment.id}>
                        <strong>{attachment.name}</strong>
                        <span>{attachment.media_type}</span>
                        {attachment.source === "screen_capture" ? (
                          <span className="badge warn">screen capture</span>
                        ) : null}
                        {attachment.ocr_status ? (
                          <span className={`badge ${attachment.ocr_status === "complete" ? "ok" : ""}`}>
                            OCR {attachment.ocr_status.replace("_", " ")}
                          </span>
                        ) : null}
                        {attachment.preview_text ? <p>{attachment.preview_text}</p> : null}
                      </div>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}

            {streamingText ? (
              <div className="streaming-indicator" aria-live="polite">
                <span className="streaming-label">Joi is responding</span>
                <span className="typing-dots" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </span>
                <p>{streamingText}</p>
              </div>
            ) : null}

            <div ref={bottomRef} />
          </div>

          <form className="chat-composer" onSubmit={onSubmit}>
            <label className="sr-only" htmlFor="chat-draft">
              Message Joi
            </label>
            <textarea
              id="chat-draft"
              className="textarea chat-textarea"
              placeholder="What's on your mind?"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
            />

            <div className="button-row composer-actions">
              <label className="button secondary" htmlFor="chat-attachments">
                Add attachment
              </label>
              <input
                id="chat-attachments"
                className="sr-only"
                type="file"
                accept="image/*,text/plain"
                multiple
                onChange={handleAttachmentSelect}
              />
              <button
                className="button secondary"
                type="button"
                disabled={!sessionId || isSending}
                onClick={() => void handleScreenCapture()}
              >
                Look at this
              </button>
              <button className="button primary" disabled={!sessionId || isSending || (!draft.trim() && attachments.length === 0)} type="submit">
                {isSending ? "Transmitting..." : "Send"}
              </button>
              <button
                className="button tertiary"
                type="button"
                onClick={() => {
                  setMessages([]);
                  setEvents([]);
                  setApprovals([]);
                  setAttachments([]);
                  setStreamingText("");
                  setMediaSession(null);
                  setAvatarSyncPayload(null);
                  setStatus("Local shell cleared");
                }}
              >
                Clear local feed
              </button>
            </div>

            <VoiceComposer
              sessionId={sessionId}
              mediaSession={mediaSession}
              assistantTurnActive={
                isSending ||
                Boolean(streamingText) ||
                avatarSyncLoading ||
                mediaSession?.speaking_state === "queued" ||
                mediaSession?.speaking_state === "playing"
              }
              spokenRepliesEnabled={spokenRepliesEnabled}
              autoSendVoiceEnabled={autoSendVoiceEnabled}
              onMediaSession={setMediaSession}
              onTranscript={handleVoiceTranscript}
              onInterruptPlayback={handleInterruptPlayback}
              onToggleSpokenReplies={() => void handleSpokenRepliesToggle()}
              onToggleAutoSendVoice={handleAutoSendVoiceToggle}
            />

            {attachments.length ? (
              <div className="attachment-draft-list">
                {attachments.map((attachment) => (
                  <div className="attachment-card" key={attachment.id ?? attachment.name}>
                    <strong>{attachment.name}</strong>
                    <span>{attachment.media_type}</span>
                    {attachment.source === "screen_capture" ? (
                      <span className="badge warn">screen capture · transient</span>
                    ) : null}
                    {attachment.preview_url ? (
                      <img alt={attachment.name} className="attachment-preview" src={attachment.preview_url} />
                    ) : attachment.preview_text ? (
                      <p>{attachment.preview_text}</p>
                    ) : null}
                    <button
                      className="button ghost"
                      type="button"
                      onClick={() =>
                        setAttachments((current) => current.filter((item) => item.id !== attachment.id))
                      }
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            ) : null}
          </form>
        </section>

        <aside className="chat-sidebar">
          <section className="panel joi-status-panel">
            <div className="aside-panel-header">
              <p className="eyebrow">Joi status</p>
              <h3>Live presence</h3>
            </div>

            <AvatarSyncPanel
              cue={avatarCue}
              loading={avatarSyncLoading}
              sync={avatarSyncPayload}
              showDiagnostics={devMode}
              compact={presenceMode === "mini"}
              perceptionExpression={perceptionExpression}
              perceptionState={perceptionState}
              lifeState={lifeState}
              onToggleCompact={() =>
                setPresenceMode((mode) => (mode === "mini" ? "full" : "mini"))
              }
              onPlaybackStateChange={(state) => void handlePlaybackStateChange(state)}
            />

            <div className="list">
              <div className="list-row">
                <div>
                  <strong>Status</strong>
                  <p>{status}</p>
                </div>
                <span className={`badge ${backendBadgeClass(backendStatus)}`}>
                  {backendStatus}
                </span>
              </div>
              <div className="list-row">
                <div>
                  <strong>Provider</strong>
                  <p>{provider}</p>
                </div>
                <span className="badge">{messages.length} messages</span>
              </div>
            </div>
            <details className="status-details">
              <summary>More</summary>
              <div className="list status-details-list">
                <div className="list-row">
                  <div>
                    <strong>Session</strong>
                    <p>
                      {backendStatus === "offline"
                        ? "waiting for backend"
                        : sessionId ?? "creating..."}
                    </p>
                  </div>
                </div>
                <div className="list-row">
                  <div>
                    <strong>Backend</strong>
                    <p>
                      {backendHealth
                        ? `${providerAvailabilitySummary(backendHealth)} | ${readinessEntry(backendHealth, "providers")?.summary ?? "provider status pending"}`
                        : "not connected"}
                    </p>
                  </div>
                  <span className={`badge ${backendBadgeClass(backendStatus)}`}>
                    {backendStatus}
                  </span>
                </div>
                <div className="list-row">
                  <div>
                    <strong>Storage</strong>
                    <p>
                      {backendHealth
                        ? readinessEntry(backendHealth, "storage")?.summary ?? "storage status pending"
                        : "not connected"}
                    </p>
                  </div>
                  <span className={`badge ${readinessTone(readinessEntry(backendHealth, "storage")?.state)}`}>
                    {readinessLabel(readinessEntry(backendHealth, "storage")?.state)}
                  </span>
                </div>
                <div className="list-row">
                  <div>
                    <strong>Media</strong>
                    <p>
                      {backendHealth
                        ? readinessEntry(backendHealth, "media")?.summary ?? "media status pending"
                        : "not connected"}
                    </p>
                  </div>
                  <span className={`badge ${readinessTone(readinessEntry(backendHealth, "media")?.state)}`}>
                    {readinessLabel(readinessEntry(backendHealth, "media")?.state)}
                  </span>
                </div>
                <div className="list-row">
                  <div>
                    <strong>Realtime</strong>
                    <p>
                      {backendHealth
                        ? readinessEntry(backendHealth, "realtime")?.summary ?? "realtime status pending"
                        : "not connected"}
                    </p>
                  </div>
                  <span className={`badge ${readinessTone(readinessEntry(backendHealth, "realtime")?.state)}`}>
                    {readinessLabel(readinessEntry(backendHealth, "realtime")?.state)}
                  </span>
                </div>
                <div className="list-row">
                  <div>
                    <strong>Hardware bridge</strong>
                    <p>
                      {backendHealth
                        ? readinessEntry(backendHealth, "hardware_bridge")?.summary ?? "hardware bridge status pending"
                        : "not connected"}
                    </p>
                  </div>
                  <span className={`badge ${readinessTone(readinessEntry(backendHealth, "hardware_bridge")?.state)}`}>
                    {readinessLabel(readinessEntry(backendHealth, "hardware_bridge")?.state)}
                  </span>
                </div>
                <div className="list-row">
                  <div>
                    <strong>Presence</strong>
                    <p>
                      {perceptionState.userPresent
                        ? (perceptionState.currentExpression?.replace(/_/g, " ") ?? "neutral")
                        : (perceptionState.lastSignal ? "away" : "not sensing")}
                    </p>
                  </div>
                  <span className={`badge ${perceptionState.userPresent ? "ok" : ""}`}>
                    {perceptionState.userPresent
                      ? perceptionState.leanedIn ? "leaned in" : "present"
                      : "away"}
                  </span>
                </div>
              </div>
            </details>

            {approvals.length > 0 && (
              <section className="joi-approvals">
                <div className="aside-section-head">
                  <p className="eyebrow">Approvals</p>
                  <h3>Pending actions</h3>
                </div>
                <div className="list">
                  {approvals.map((approval) => {
                    const presentation = approvalPresentation(approval);
                    return (
                      <div className="approval-card" key={approval.id}>
                        <div className="approval-card-header">
                          <div>
                            <span className="approval-card-kicker">Joi wants permission</span>
                            <strong>{presentation.title}</strong>
                          </div>
                          <div className="approval-badges">
                            {approval.local_only ? <span className="badge ok">local only</span> : null}
                            <span className={`badge ${presentation.riskTone}`}>
                              {presentation.riskLabel}
                            </span>
                          </div>
                        </div>
                        <p>{presentation.summary}</p>
                        {presentation.fields.length ? (
                          <div className="approval-field-list">
                            {presentation.fields.map((field) => (
                              <div className="approval-field" key={`${approval.id}-${field.label}`}>
                                <span>{field.label}</span>
                                <strong>{field.value}</strong>
                              </div>
                            ))}
                          </div>
                        ) : null}
                        <div className="button-row">
                          <button
                            className="button ghost"
                            type="button"
                            onClick={() => setSelectedApprovalId(approval.id)}
                          >
                            Review
                          </button>
                          <button
                            className="button secondary"
                            type="button"
                            onClick={() => void handleApprovalAction(approval.id, "approve")}
                          >
                            Approve
                          </button>
                          <button
                            className="button ghost"
                            type="button"
                            onClick={() => void handleApprovalAction(approval.id, "deny")}
                          >
                            Deny
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {selectedApproval ? (
              <section className="approval-modal">
                <div className="approval-card-header">
                  <div>
                    <span className="approval-card-kicker">Permission review</span>
                    <h3>{approvalPresentation(selectedApproval).title}</h3>
                  </div>
                  <button
                    className="button ghost"
                    type="button"
                    onClick={() => setSelectedApprovalId(null)}
                  >
                    Close
                  </button>
                </div>
                <p>{approvalPresentation(selectedApproval).summary}</p>
                {approvalPresentation(selectedApproval).fields.length ? (
                  <div className="approval-field-list">
                    {approvalPresentation(selectedApproval).fields.map((field) => (
                      <div className="approval-field" key={`${selectedApproval.id}-modal-${field.label}`}>
                        <span>{field.label}</span>
                        <strong>{field.value}</strong>
                      </div>
                    ))}
                  </div>
                ) : null}
                {approvalPresentation(selectedApproval).preview ? (
                  <div className="approval-preview">
                    <strong>Preview</strong>
                    <p>{approvalPresentation(selectedApproval).preview}</p>
                  </div>
                ) : null}
                <details className="approval-raw">
                  <summary>Raw tool arguments</summary>
                  <pre>{JSON.stringify(selectedApproval.args, null, 2)}</pre>
                </details>
                <div className="button-row" style={{ marginTop: 18 }}>
                  <button
                    className="button secondary"
                    type="button"
                    onClick={() => void handleApprovalAction(selectedApproval.id, "approve")}
                  >
                    Approve
                  </button>
                  <button
                    className="button ghost"
                    type="button"
                    onClick={() => void handleApprovalAction(selectedApproval.id, "deny")}
                  >
                    Deny
                  </button>
                </div>
              </section>
            ) : null}

            {devMode ? (
            <section className="joi-approvals">
              <div className="aside-section-head">
                <p className="eyebrow">Desktop</p>
                <h3>Safe actions</h3>
              </div>
              <div className="desktop-action-panel">
                <div className="desktop-action-form">
                  <label htmlFor="desktop-url">Open URL</label>
                  <div className="desktop-action-inline">
                    <input
                      id="desktop-url"
                      className="input"
                      type="url"
                      value={desktopUrlDraft}
                      onChange={(event) => setDesktopUrlDraft(event.target.value)}
                    />
                    <button
                      className="button ghost"
                      type="button"
                      disabled={!desktopUrlDraft.trim()}
                      onClick={() => stageDesktopAction("open_url", { url: desktopUrlDraft.trim() })}
                    >
                      Review
                    </button>
                  </div>
                </div>

                <div className="desktop-action-form">
                  <label htmlFor="desktop-notification-message">Notification</label>
                  <input
                    className="input"
                    type="text"
                    value={desktopNotificationTitle}
                    onChange={(event) => setDesktopNotificationTitle(event.target.value)}
                  />
                  <textarea
                    id="desktop-notification-message"
                    className="textarea desktop-action-textarea"
                    value={desktopNotificationMessage}
                    onChange={(event) => setDesktopNotificationMessage(event.target.value)}
                  />
                  <button
                    className="button ghost"
                    type="button"
                    disabled={!desktopNotificationMessage.trim()}
                    onClick={() =>
                      stageDesktopAction("show_notification", {
                        title: desktopNotificationTitle.trim() || "Joi",
                        message: desktopNotificationMessage.trim(),
                      })
                    }
                  >
                    Review notification
                  </button>
                </div>

                {pendingDesktopAction ? (
                  <div className="approval-card desktop-action-review">
                    <div className="approval-card-header">
                      <div>
                        <span className="approval-card-kicker">Explicit confirmation required</span>
                        <strong>{humanizeKey(pendingDesktopAction.action)}</strong>
                      </div>
                      <span className="badge ok">local only</span>
                    </div>
                    <details className="approval-raw" open>
                      <summary>Action payload</summary>
                      <pre>{JSON.stringify(pendingDesktopAction.args, null, 2)}</pre>
                    </details>
                    <div className="button-row">
                      <button
                        className="button secondary"
                        type="button"
                        disabled={desktopActionBusy}
                        onClick={() => void executePendingDesktopAction()}
                      >
                        {desktopActionBusy ? "Running..." : "Run action"}
                      </button>
                      <button
                        className="button ghost"
                        type="button"
                        disabled={desktopActionBusy}
                        onClick={() => setPendingDesktopAction(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : null}

                {desktopActionResult ? (
                  <div className={`desktop-action-result ${desktopActionResult.status}`}>
                    <strong>{desktopActionResult.status}</strong>
                    <p>{desktopActionResult.summary}</p>
                  </div>
                ) : null}
              </div>
            </section>
            ) : null}
          </section>

          <section className="panel chat-feed-panel">
            <div className="aside-panel-header feed-panel-header">
              <div>
                <p className="eyebrow">Feed</p>
                <h3>Signals</h3>
              </div>
              <button
                className="button ghost avatar-mode-toggle"
                type="button"
                onClick={handleDevModeToggle}
                aria-pressed={devMode}
                title={devMode ? "Hide developer telemetry" : "Show developer telemetry"}
              >
                {devMode ? "Dev on" : "Dev"}
              </button>
            </div>

            {lastSnapshotAnalysis ? (
              <section className="feed-section">
                <p className="eyebrow">Scene analysis</p>
                <h3>Last snapshot</h3>
                <p className="feed-copy">
                  {lastSnapshotAnalysis.description}
                </p>
                {lastSnapshotAnalysis.tags.length > 0 ? (
                  <div className="voice-badges">
                    {lastSnapshotAnalysis.tags.map((tag) => (
                      <span className="badge" key={tag}>{tag}</span>
                    ))}
                  </div>
                ) : null}
                <button
                  className="button tertiary feed-dismiss"
                  type="button"
                  onClick={clearLastSnapshotAnalysis}
                >
                  Dismiss
                </button>
              </section>
            ) : null}

            {devMode ? (
              <details className="aside-accordion">
                <summary>
                  <span>Event stream {events.length > 0 ? `(${events.length})` : ""}</span>
                </summary>
                <div className="event-list aside-accordion-body">
                  {events.length === 0 ? (
                    <div className="empty-state">No events yet.</div>
                  ) : (
                    events.map((event) => (
                      <article key={event.event_id} className="event-card">
                        <header>
                          <span>{event.event}</span>
                          <span>{formatTimestamp(event.timestamp)}</span>
                        </header>
                        <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                      </article>
                    ))
                  )}
                </div>
              </details>
            ) : (
              <p className="feed-copy">
                Scene notes and signals from Joi appear here. Toggle Dev for raw telemetry.
              </p>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
