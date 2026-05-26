"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { patchMediaSession, transcribeAudioBlob } from "@/lib/api";
import { MediaSession } from "@/lib/types";

type VoiceComposerProps = {
  sessionId: string | null;
  mediaSession: MediaSession | null;
  spokenRepliesEnabled: boolean;
  autoSendVoiceEnabled: boolean;
  onMediaSession: (session: MediaSession) => void;
  onTranscript: (transcript: string) => Promise<void> | void;
  onInterruptPlayback: (statusMessage?: string) => Promise<void> | void;
  onToggleSpokenReplies: () => void;
  onToggleAutoSendVoice: () => void;
};

const NATIVE_PTT_START_EVENT = "joi:native-ptt-start";
const NATIVE_PTT_STOP_EVENT = "joi:native-ptt-stop";

function isPushToTalkHotkey(event: KeyboardEvent) {
  return (
    event.code === "Space" &&
    event.ctrlKey &&
    event.shiftKey &&
    !event.altKey &&
    !event.metaKey
  );
}

function pickRecorderMimeType() {
  if (typeof window === "undefined" || typeof MediaRecorder === "undefined") {
    return "";
  }

  const preferred = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  for (const candidate of preferred) {
    if (MediaRecorder.isTypeSupported(candidate)) {
      return candidate;
    }
  }
  return "";
}

export function VoiceComposer({
  sessionId,
  mediaSession,
  spokenRepliesEnabled,
  autoSendVoiceEnabled,
  onMediaSession,
  onTranscript,
  onInterruptPlayback,
  onToggleSpokenReplies,
  onToggleAutoSendVoice,
}: VoiceComposerProps) {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number>(0);
  const hotkeyActiveRef = useRef(false);
  const pendingStopRef = useRef(false);
  const cancelRequestedRef = useRef(false);

  const [isSupported, setIsSupported] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsSupported(
      typeof window !== "undefined" &&
        typeof navigator !== "undefined" &&
        Boolean(navigator.mediaDevices?.getUserMedia) &&
        typeof MediaRecorder !== "undefined",
    );
  }, []);

  useEffect(() => {
    return () => {
      recorderRef.current?.stop();
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  const syncSession = useCallback(async (patch: Parameters<typeof patchMediaSession>[0]) => {
    const response = await patchMediaSession(patch);
    onMediaSession(response.media_session);
  }, [onMediaSession]);

  const stopRecording = useCallback(() => {
    if (!recorderRef.current || recorderRef.current.state === "inactive") {
      pendingStopRef.current = true;
      return;
    }
    pendingStopRef.current = false;
    setBusy(true);
    recorderRef.current.stop();
  }, []);

  const cancelRecording = useCallback(() => {
    cancelRequestedRef.current = true;
    chunksRef.current = [];
    if (!recorderRef.current || recorderRef.current.state === "inactive") {
      pendingStopRef.current = false;
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      recorderRef.current = null;
      return;
    }
    pendingStopRef.current = false;
    setBusy(true);
    recorderRef.current.stop();
  }, []);

  const startRecording = useCallback(async () => {
    if (!sessionId || busy || !isSupported) {
      return;
    }

    setError(null);
    pendingStopRef.current = false;
    cancelRequestedRef.current = false;
    setBusy(true);

    try {
      if (mediaSession?.speaking_state === "playing" || mediaSession?.speaking_state === "queued") {
        await onInterruptPlayback("Voice playback interrupted by microphone capture");
      }

      await syncSession({
        session_id: sessionId,
        mic_state: "requesting",
        capture_source: "browser",
        last_error: "",
      });

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      startedAtRef.current = performance.now();

      const mimeType = pickRecorderMimeType();
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      recorderRef.current = recorder;

      recorder.addEventListener("dataavailable", (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      });

      recorder.addEventListener("stop", async () => {
        const durationMs = Math.max(0, Math.round(performance.now() - startedAtRef.current));
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        recorderRef.current = null;

        try {
          if (cancelRequestedRef.current) {
            await syncSession({
              session_id: sessionId,
              mic_state: "idle",
              last_error: "",
            });
            return;
          }

          const response = await transcribeAudioBlob(sessionId, blob, durationMs);
          onMediaSession(response.media_session);
          if (response.transcript.trim()) {
            onTranscript(response.transcript.trim());
          } else if (response.media_session.last_error) {
            setError(response.media_session.last_error);
          }
        } catch (cause) {
          const message = cause instanceof Error ? cause.message : "Voice transcription failed";
          setError(message);
          try {
            await syncSession({
              session_id: sessionId,
              mic_state: "error",
              last_error: message,
            });
          } catch {
            // Ignore follow-up sync failures after the primary transcription error.
          }
        } finally {
          pendingStopRef.current = false;
          cancelRequestedRef.current = false;
          setBusy(false);
        }
      });

      recorder.start();
      await syncSession({
        session_id: sessionId,
        mic_state: "recording",
        capture_source: "browser",
      });
      setBusy(false);

      if (pendingStopRef.current) {
        pendingStopRef.current = false;
        stopRecording();
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Microphone capture failed";
      setError(message);
      pendingStopRef.current = false;
      cancelRequestedRef.current = false;
      if (sessionId) {
        try {
          await syncSession({
            session_id: sessionId,
            mic_state: "error",
            last_error: message,
          });
        } catch {
          // Ignore session sync errors while already reporting a capture failure.
        }
      }
      setBusy(false);
    }
  }, [busy, isSupported, mediaSession?.speaking_state, onInterruptPlayback, sessionId, stopRecording, syncSession]);

  const isRecording = mediaSession?.mic_state === "recording";
  const isCapturing =
    mediaSession?.mic_state === "requesting" ||
    mediaSession?.mic_state === "recording" ||
    mediaSession?.mic_state === "processing";
  const canStopSpeaking =
    mediaSession?.speaking_state === "playing" || mediaSession?.speaking_state === "queued";

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!isPushToTalkHotkey(event) || event.repeat || hotkeyActiveRef.current) {
        return;
      }

      event.preventDefault();
      hotkeyActiveRef.current = true;
      void startRecording();
    };

    const handleKeyUp = (event: KeyboardEvent) => {
      if (!isPushToTalkHotkey(event) || !hotkeyActiveRef.current) {
        return;
      }

      event.preventDefault();
      hotkeyActiveRef.current = false;
      stopRecording();
    };

    const handleCancelOrInterrupt = (event: KeyboardEvent) => {
      if (event.code !== "Escape") {
        return;
      }

      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        event.preventDefault();
        hotkeyActiveRef.current = false;
        cancelRecording();
        return;
      }

      if (canStopSpeaking) {
        event.preventDefault();
        void onInterruptPlayback("Voice playback interrupted");
      }
    };

    const handleNativeStart = (event: Event) => {
      event.preventDefault();
      if (hotkeyActiveRef.current) {
        return;
      }
      hotkeyActiveRef.current = true;
      void startRecording();
    };

    const handleNativeStop = (event: Event) => {
      event.preventDefault();
      if (!hotkeyActiveRef.current) {
        return;
      }
      hotkeyActiveRef.current = false;
      stopRecording();
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    window.addEventListener("keydown", handleCancelOrInterrupt);
    window.addEventListener(NATIVE_PTT_START_EVENT, handleNativeStart);
    window.addEventListener(NATIVE_PTT_STOP_EVENT, handleNativeStop);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
      window.removeEventListener("keydown", handleCancelOrInterrupt);
      window.removeEventListener(NATIVE_PTT_START_EVENT, handleNativeStart);
      window.removeEventListener(NATIVE_PTT_STOP_EVENT, handleNativeStop);
    };
  }, [canStopSpeaking, cancelRecording, onInterruptPlayback, startRecording, stopRecording]);

  async function handleStopSpeaking() {
    if (!sessionId || busy || !canStopSpeaking) {
      return;
    }

    setError(null);
    await onInterruptPlayback("Voice playback stopped");
  }

  return (
    <div className="voice-panel">
      <div className="voice-panel-header">
        <div>
          <strong>Browser voice capture</strong>
          <p>Mic capture happens in the browser and posts audio back to Python for transcription.</p>
        </div>
        <div className="voice-badges">
          <button
            className={`button ${spokenRepliesEnabled ? "secondary" : "ghost"} voice-default-toggle`}
            type="button"
            aria-pressed={spokenRepliesEnabled}
            onClick={onToggleSpokenReplies}
          >
            Spoken replies {spokenRepliesEnabled ? "on" : "off"}
          </button>
          <button
            className={`button ${autoSendVoiceEnabled ? "secondary" : "ghost"} voice-default-toggle`}
            type="button"
            aria-pressed={autoSendVoiceEnabled}
            onClick={onToggleAutoSendVoice}
          >
            Voice sends {autoSendVoiceEnabled ? "on" : "off"}
          </button>
          <span className={`badge ${isRecording ? "warn" : "ok"}`}>
            mic {mediaSession?.mic_state ?? "idle"}
          </span>
          <span className="badge">speech {mediaSession?.speaking_state ?? "idle"}</span>
        </div>
      </div>

      <div className="button-row">
        <button
          className={`button ${isRecording ? "secondary" : "ghost"}`}
          type="button"
          disabled={!sessionId || busy || !isSupported}
          onClick={() => void (isRecording ? stopRecording() : startRecording())}
        >
          {isRecording ? "Stop recording" : "Record voice"}
        </button>
        {canStopSpeaking ? (
          <button
            className="button secondary"
            type="button"
            disabled={!sessionId || busy}
            onClick={() => void handleStopSpeaking()}
          >
            Stop speaking
          </button>
        ) : null}
        {isCapturing ? (
          <button
            className="button ghost"
            type="button"
            disabled={busy && mediaSession?.mic_state !== "recording"}
            onClick={cancelRecording}
          >
            Cancel recording
          </button>
        ) : null}
        {mediaSession?.recognition_latency_ms ? (
          <span className="badge ok">{mediaSession.recognition_latency_ms}ms STT</span>
        ) : null}
        {mediaSession?.interruption_count ? (
          <span className="badge warn">{mediaSession.interruption_count} interruptions</span>
        ) : null}
      </div>

      {!isSupported ? (
        <div className="empty-state">This browser does not expose MediaRecorder microphone capture.</div>
      ) : error ? (
        <div className="voice-error">{error}</div>
      ) : mediaSession?.last_transcript ? (
        <div className="voice-transcript-preview" aria-live="polite">
          <span className="voice-transcript-label">Latest transcript</span>
          <p title={mediaSession.last_transcript}>{mediaSession.last_transcript}</p>
        </div>
      ) : (
        <div className="empty-state">Voice capture is idle. Record a short prompt to append it to the draft.</div>
      )}
    </div>
  );
}
