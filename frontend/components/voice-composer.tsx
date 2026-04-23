"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { patchMediaSession, transcribeAudioBlob } from "@/lib/api";
import { MediaSession } from "@/lib/types";

type VoiceComposerProps = {
  sessionId: string | null;
  mediaSession: MediaSession | null;
  onMediaSession: (session: MediaSession) => void;
  onTranscript: (transcript: string) => void;
  onInterruptPlayback: () => void;
};

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
  onMediaSession,
  onTranscript,
  onInterruptPlayback,
}: VoiceComposerProps) {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number>(0);
  const hotkeyActiveRef = useRef(false);
  const pendingStopRef = useRef(false);

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

  const startRecording = useCallback(async () => {
    if (!sessionId || busy || !isSupported) {
      return;
    }

    setError(null);
    pendingStopRef.current = false;
    setBusy(true);

    try {
      if (mediaSession?.speaking_state === "playing" || mediaSession?.speaking_state === "queued") {
        onInterruptPlayback();
        await syncSession({
          session_id: sessionId,
          speaking_state: "interrupted",
          interrupted: true,
        });
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

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, [startRecording, stopRecording]);

  const isRecording = mediaSession?.mic_state === "recording";

  return (
    <div className="voice-panel">
      <div className="voice-panel-header">
        <div>
          <strong>Browser voice capture</strong>
          <p>Mic capture happens in the browser and posts audio back to Python for transcription.</p>
        </div>
        <div className="voice-badges">
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
        <div className="voice-transcript-preview">
          <strong>Latest transcript</strong>
          <p>{mediaSession.last_transcript}</p>
        </div>
      ) : (
        <div className="empty-state">Voice capture is idle. Record a short prompt to append it to the draft.</div>
      )}
    </div>
  );
}
