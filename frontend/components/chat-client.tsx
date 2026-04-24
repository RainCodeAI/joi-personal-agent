"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState, startTransition } from "react";

import { AvatarSyncPanel } from "@/components/avatar-sync-panel";
import { PerceptionEngine } from "@/components/perception-engine";
import { VoiceComposer } from "@/components/voice-composer";
import {
  approveAction,
  createEventStream,
  createSession,
  denyAction,
  fetchBackendHealth,
  fetchMediaSession,
  listApprovals,
  listMessages,
  patchMediaSession,
  sendChatMessageWithAttachments,
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
  MediaSession,
  Message,
  PerceptionSignal,
  PerceptionState,
  ReadinessState,
  RealtimeEvent,
  SnapshotAnalysis,
} from "@/lib/types";

const SESSION_STORAGE_KEY = "joi-v2-session";
const SPOKEN_REPLIES_STORAGE_KEY = "joi-v2-spoken-replies";

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
  };
}

export function ChatClient({ initialSessionId }: ChatClientProps) {
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId ?? null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [events, setEvents] = useState<RealtimeEvent[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [selectedApprovalId, setSelectedApprovalId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [attachments, setAttachments] = useState<AttachmentDraft[]>([]);
  const [status, setStatus] = useState("Checking backend");
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");
  const [backendHealth, setBackendHealth] = useState<BackendHealth | null>(null);
  const [provider, setProvider] = useState("pending");
  const [streamingText, setStreamingText] = useState("");
  const [avatarCue, setAvatarCue] = useState<AvatarCue | null>(null);
  const [avatarSyncPayload, setAvatarSyncPayload] = useState<AvatarSyncPayload | null>(null);
  const [presenceMode, setPresenceMode] = useState<PresenceMode>("full");
  const [mediaSession, setMediaSession] = useState<MediaSession | null>(null);
  const [spokenRepliesEnabled, setSpokenRepliesEnabled] = useState(true);
  const [avatarSyncLoading, setAvatarSyncLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [perceptionState, setPerceptionState] = useState<PerceptionState>({
    userPresent: false,
    faceVisible: false,
    leanedIn: false,
    currentExpression: null,
    lastSignal: null,
    updatedAt: 0,
  });
  const [perceptionExpression, setPerceptionExpression] = useState<string | null>(null);
  const [lastSnapshotAnalysis, setLastSnapshotAnalysis] = useState<SnapshotAnalysis | null>(null);
  const lookAwayResetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const handlePerceptionSignal = useCallback((signal: PerceptionSignal) => {
    startTransition(() => {
      setPerceptionState((prev) => {
        const presenceSignals = new Set(["user_present", "face_visible", "returned_to_frame"]);
        return {
          userPresent: presenceSignals.has(signal.signal)
            ? true
            : signal.signal === "looked_away"
              ? false
              : prev.userPresent,
          faceVisible: presenceSignals.has(signal.signal)
            ? true
            : signal.signal === "looked_away"
              ? false
              : prev.faceVisible,
          leanedIn: signal.signal === "leaned_in"
            ? true
            : signal.signal === "leaned_back"
              ? false
              : prev.leanedIn,
          currentExpression:
            signal.signal === "expression_smile"    ? "smile"    :
            signal.signal === "expression_stress"   ? "stress"   :
            signal.signal === "expression_surprise" ? "surprise" :
            signal.signal === "expression_neutral"  ? "neutral"  :
            prev.currentExpression,
          lastSignal: signal,
          updatedAt: signal.timestamp,
        };
      });
    });

    // Map perception signals to avatar expression overrides
    if (signal.signal === "expression_smile") {
      setPerceptionExpression("smirk");
    } else if (signal.signal === "expression_stress") {
      setPerceptionExpression("concern");
    } else if (signal.signal === "expression_surprise") {
      setPerceptionExpression("shock");
    } else if (signal.signal === "expression_neutral") {
      setPerceptionExpression(null);
    } else if (signal.signal === "looked_away") {
      // Show Joi looking away — auto-restore after 4s
      setPerceptionExpression("missing");
      if (lookAwayResetTimerRef.current) clearTimeout(lookAwayResetTimerRef.current);
      lookAwayResetTimerRef.current = setTimeout(() => {
        setPerceptionExpression(null);
      }, 4000);
    } else if (signal.signal === "returned_to_frame") {
      if (lookAwayResetTimerRef.current) clearTimeout(lookAwayResetTimerRef.current);
      setPerceptionExpression(null);
    } else if (signal.signal === "snapshot_analyzed" && signal.payload) {
      setLastSnapshotAnalysis({
        description: String(signal.payload.description ?? ""),
        tags: Array.isArray(signal.payload.tags) ? (signal.payload.tags as string[]) : [],
        capturedAt: String(signal.payload.capturedAt ?? ""),
        previewDataUrl: "",
      });
    }
  }, []);

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
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(
      SPOKEN_REPLIES_STORAGE_KEY,
      spokenRepliesEnabled ? "on" : "off",
    );
  }, [spokenRepliesEnabled]);

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

    try {
      const response = await patchMediaSession({
        session_id: sessionId,
        speaking_state: state.speakingState,
        playback_latency_ms: state.playbackLatencyMs,
      });
      setMediaSession(response.media_session);
    } catch {
      // Ignore playback session sync failures and preserve local playback.
    }
  }

  function handleVoiceTranscript(transcript: string) {
    setDraft((current) => (current.trim() ? `${current.trim()} ${transcript}` : transcript));
    setStatus("Voice transcript appended to draft");
  }

  async function handleInterruptPlayback(statusMessage = "Voice playback interrupted") {
    setAvatarSyncPayload(null);
    setAvatarSyncLoading(false);
    setStatus(statusMessage);

    if (!sessionId) {
      return;
    }

    try {
      const response = await patchMediaSession({
        session_id: sessionId,
        speaking_state: "interrupted",
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

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!sessionId || isSending || (!draft.trim() && attachments.length === 0)) {
      return;
    }

    const text = draft.trim();
    const optimisticUser: DisplayMessage = {
      id: Date.now(),
      session_id: sessionId,
      role: "user",
      content: text || (attachments.length === 1 ? `Shared attachment: ${attachments[0].name}` : `Shared ${attachments.length} attachments`),
      timestamp: new Date().toISOString(),
      attachments: attachments.map(toAttachmentResource),
    };

    startTransition(() => {
      setMessages((current) => [...current, optimisticUser]);
    });
    setDraft("");
    setStreamingText("");
    setIsSending(true);
    setStatus("Sending message");

    try {
      const response: ChatResponse = await sendChatMessageWithAttachments(
        sessionId,
        text,
        attachments.map(({ preview_url, preview_text, ...attachment }) => attachment),
      );

      setProvider(response.provider.selected || "router");
      setApprovals(response.pending_approvals);
      startTransition(() => {
        setMessages((current) => [
          ...current.filter((message) => message.id !== optimisticUser.id),
          { ...response.user_message, attachments: response.attachments },
          response.assistant_message,
        ]);
      });
      setAttachments([]);
      setStreamingText("");
      setStatus(response.pending_approvals.length ? "Awaiting approval" : "Response complete");
      await handleAvatarSync(
        response.assistant_message.id,
        response.assistant_message.content,
        response.avatar,
      );
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to send message");
      startTransition(() => {
        setMessages((current) => current.filter((message) => message.id !== optimisticUser.id));
      });
    } finally {
      setIsSending(false);
    }
  }

  async function handleApprovalAction(approvalId: string, decision: "approve" | "deny") {
    setStatus(`${decision === "approve" ? "Approving" : "Denying"} action`);
    try {
      if (decision === "approve") {
        await approveAction(approvalId);
      } else {
        await denyAction(approvalId);
      }
      setApprovals((current) => current.filter((approval) => approval.id !== approvalId));
      setSelectedApprovalId((current) => (current === approvalId ? null : current));
      setStatus(`Approval ${decision}d`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Approval action failed");
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
              Ask for a plan, drop in context, or keep the realtime thread moving.
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
                {message.attachments?.length ? (
                  <div className="attachment-list">
                    {message.attachments.map((attachment) => (
                      <div className="attachment-card" key={attachment.id}>
                        <strong>{attachment.name}</strong>
                        <span>{attachment.media_type}</span>
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
              placeholder="Tell Joi what you need, attach context, or ask for a plan."
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
              <button className="button primary" disabled={!sessionId || isSending || (!draft.trim() && attachments.length === 0)} type="submit">
                {isSending ? "Transmitting..." : "Send to Joi"}
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
              spokenRepliesEnabled={spokenRepliesEnabled}
              onMediaSession={setMediaSession}
              onTranscript={handleVoiceTranscript}
              onInterruptPlayback={handleInterruptPlayback}
              onToggleSpokenReplies={() => void handleSpokenRepliesToggle()}
            />

            {attachments.length ? (
              <div className="attachment-draft-list">
                {attachments.map((attachment) => (
                  <div className="attachment-card" key={attachment.id ?? attachment.name}>
                    <strong>{attachment.name}</strong>
                    <span>{attachment.media_type}</span>
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
              compact={presenceMode === "mini"}
              perceptionExpression={perceptionExpression}
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
                        ? (perceptionState.currentExpression ?? "neutral")
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
                          <span className={`badge ${presentation.riskTone}`}>
                            {presentation.riskLabel}
                          </span>
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
          </section>

          <section className="panel chat-feed-panel">
            <div className="aside-panel-header">
              <p className="eyebrow">Feed</p>
              <h3>Signals and diagnostics</h3>
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
                  onClick={() => setLastSnapshotAnalysis(null)}
                >
                  Dismiss
                </button>
              </section>
            ) : null}

            <details className="aside-accordion">
              <summary>
                <span>Presence sensing</span>
              </summary>
              <div className="aside-accordion-body">
                <PerceptionEngine sessionId={sessionId} onSignal={handlePerceptionSignal} />
              </div>
            </details>

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
          </section>
        </aside>
      </div>
    </div>
  );
}
