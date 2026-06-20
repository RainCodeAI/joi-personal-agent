"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { patchMediaSession, transcribeAudioBlob } from "@/lib/api";
import { MediaSession } from "@/lib/types";

type VoiceComposerProps = {
  sessionId: string | null;
  mediaSession: MediaSession | null;
  assistantTurnActive: boolean;
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
const CONVERSATION_SILENCE_MS = 900;
const CONVERSATION_MAX_MS = 30_000;
const VAD_RMS_THRESHOLD = 0.025;

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
  assistantTurnActive,
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
  const captureAttemptRef = useRef(0);
  const captureInFlightRef = useRef(false);
  const interruptInFlightRef = useRef(false);
  const conversationActiveRef = useRef(false);
  const restartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startRecordingRef = useRef<() => Promise<void>>(async () => {});
  const assistantTurnActiveRef = useRef(assistantTurnActive);
  const audioContextRef = useRef<AudioContext | null>(null);
  const vadTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const speechDetectedRef = useRef(false);
  const speechStartedAtRef = useRef<number | null>(null);
  const lastSpeechAtRef = useRef<number | null>(null);

  const [isSupported, setIsSupported] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [voiceMode, setVoiceMode] = useState<MediaSession["voice_mode"]>("push_to_talk");

  useEffect(() => {
    const stored = window.localStorage.getItem("joi_voice_mode");
    if (stored === "conversation" || stored === "push_to_talk") {
      setVoiceMode(stored);
    }
    setIsSupported(
      typeof window !== "undefined" &&
        typeof navigator !== "undefined" &&
        Boolean(navigator.mediaDevices?.getUserMedia) &&
        typeof MediaRecorder !== "undefined",
    );
  }, []);

  useEffect(() => {
    assistantTurnActiveRef.current = assistantTurnActive;
  }, [assistantTurnActive]);

  useEffect(() => {
    return () => {
      captureAttemptRef.current += 1;
      captureInFlightRef.current = false;
      recorderRef.current?.stop();
      streamRef.current?.getTracks().forEach((track) => track.stop());
      if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
      if (vadTimerRef.current) clearInterval(vadTimerRef.current);
      void audioContextRef.current?.close();
    };
  }, []);

  const syncSession = useCallback(async (patch: Parameters<typeof patchMediaSession>[0]) => {
    const response = await patchMediaSession(patch);
    onMediaSession(response.media_session);
    return response.media_session;
  }, [onMediaSession]);

  const stopVad = useCallback(() => {
    if (vadTimerRef.current) {
      clearInterval(vadTimerRef.current);
      vadTimerRef.current = null;
    }
    if (audioContextRef.current) {
      void audioContextRef.current.close();
      audioContextRef.current = null;
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (!recorderRef.current || recorderRef.current.state === "inactive") {
      pendingStopRef.current = true;
      return;
    }
    pendingStopRef.current = false;
    setBusy(true);
    stopVad();
    recorderRef.current.stop();
  }, [stopVad]);

  const cancelRecording = useCallback(() => {
    conversationActiveRef.current = false;
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }
    captureAttemptRef.current += 1;
    captureInFlightRef.current = false;
    cancelRequestedRef.current = true;
    chunksRef.current = [];
    if (!recorderRef.current || recorderRef.current.state === "inactive") {
      pendingStopRef.current = false;
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      recorderRef.current = null;
      setBusy(false);
      stopVad();
      if (sessionId) {
        void syncSession({
          session_id: sessionId,
          turn_state: "idle",
          mic_state: "idle",
          last_error: "",
        });
      }
      return;
    }
    pendingStopRef.current = false;
    setBusy(true);
    stopVad();
    recorderRef.current.stop();
  }, [sessionId, stopVad, syncSession]);

  const interruptPlayback = useCallback(async (statusMessage: string) => {
    if (interruptInFlightRef.current) {
      return;
    }
    interruptInFlightRef.current = true;
    try {
      await onInterruptPlayback(statusMessage);
    } finally {
      interruptInFlightRef.current = false;
    }
  }, [onInterruptPlayback]);

  const startVad = useCallback((
    stream: MediaStream,
    startedAt: number,
    autoStop: () => void,
  ) => {
    const AudioContextClass = window.AudioContext;
    if (!AudioContextClass) return;

    const context = new AudioContextClass();
    const analyser = context.createAnalyser();
    analyser.fftSize = 1024;
    context.createMediaStreamSource(stream).connect(analyser);
    const samples = new Float32Array(analyser.fftSize);
    audioContextRef.current = context;

    vadTimerRef.current = setInterval(() => {
      analyser.getFloatTimeDomainData(samples);
      let sum = 0;
      for (const sample of samples) sum += sample * sample;
      const rms = Math.sqrt(sum / samples.length);
      const now = performance.now();

      if (rms >= VAD_RMS_THRESHOLD) {
        lastSpeechAtRef.current = now;
        if (!speechDetectedRef.current) {
          speechDetectedRef.current = true;
          speechStartedAtRef.current = now;
          void (async () => {
            try {
              if (voiceMode === "conversation" && assistantTurnActiveRef.current) {
                await interruptPlayback("Conversation speech interrupted Joi");
              }
              await syncSession({
                session_id: sessionId!,
                voice_mode: voiceMode,
                turn_state: "speech_detected",
                speech_detected: true,
              });
            } catch {
              // Local barge-in remains effective if telemetry sync is unavailable.
            }
          })();
        }
      }

      if (
        voiceMode === "conversation" &&
        speechDetectedRef.current &&
        lastSpeechAtRef.current !== null &&
        now - lastSpeechAtRef.current >= CONVERSATION_SILENCE_MS
      ) {
        autoStop();
      } else if (voiceMode === "conversation" && now - startedAt >= CONVERSATION_MAX_MS) {
        autoStop();
      }
    }, 80);
  }, [interruptPlayback, sessionId, syncSession, voiceMode]);

  const startRecording = useCallback(async () => {
    if (!sessionId || busy || captureInFlightRef.current || !isSupported) {
      return;
    }

    const captureAttempt = captureAttemptRef.current + 1;
    captureAttemptRef.current = captureAttempt;
    captureInFlightRef.current = true;
    setError(null);
    pendingStopRef.current = false;
    cancelRequestedRef.current = false;
    speechDetectedRef.current = false;
    speechStartedAtRef.current = null;
    lastSpeechAtRef.current = null;
    setBusy(true);
    if (voiceMode === "conversation") {
      conversationActiveRef.current = true;
    }

    try {
      if (
        voiceMode === "push_to_talk" &&
        (mediaSession?.speaking_state === "playing" || mediaSession?.speaking_state === "queued")
      ) {
        await interruptPlayback("Voice playback interrupted by microphone capture");
        if (captureAttempt !== captureAttemptRef.current) {
          return;
        }
      }

      await syncSession({
        session_id: sessionId,
        voice_mode: voiceMode,
        turn_state: "listening",
        mic_state: "requesting",
        capture_source: "browser",
        last_error: "",
      });
      if (captureAttempt !== captureAttemptRef.current) {
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      if (captureAttempt !== captureAttemptRef.current || cancelRequestedRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        await syncSession({
          session_id: sessionId,
          turn_state: "idle",
          mic_state: "idle",
          last_error: "",
        });
        return;
      }
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
        const speechDurationMs = speechStartedAtRef.current === null
          ? 0
          : Math.max(
              0,
              Math.round((lastSpeechAtRef.current ?? performance.now()) - speechStartedAtRef.current),
            );
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
              turn_state: "idle",
              mic_state: "idle",
              last_error: "",
            });
            return;
          }

          if (voiceMode === "conversation" && !speechDetectedRef.current) {
            await syncSession({
              session_id: sessionId,
              turn_state: "idle",
              mic_state: "idle",
              speech_detected: false,
              speech_duration_ms: 0,
              last_error: "",
            });
            return;
          }

          const endedAt = performance.now();
          const response = await transcribeAudioBlob(sessionId, blob, speechDurationMs || durationMs, {
            voiceMode,
            speechDetected: speechDetectedRef.current,
          });
          const endOfSpeechToTranscriptMs = Math.max(0, Math.round(performance.now() - endedAt));
          const measuredSession = await syncSession({
            session_id: sessionId,
            turn_state: "idle",
            end_of_speech_to_transcript_ms: endOfSpeechToTranscriptMs,
            speech_duration_ms: speechDurationMs || durationMs,
            speech_detected: speechDetectedRef.current,
          });
          onMediaSession(measuredSession);
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
              turn_state: "error",
              mic_state: "error",
              last_error: message,
            });
          } catch {
            // Ignore follow-up sync failures after the primary transcription error.
          }
        } finally {
          const shouldRestartConversation =
            voiceMode === "conversation" &&
            conversationActiveRef.current &&
            !cancelRequestedRef.current;
          captureInFlightRef.current = false;
          pendingStopRef.current = false;
          cancelRequestedRef.current = false;
          setBusy(false);
          stopVad();
          if (shouldRestartConversation) {
            restartTimerRef.current = setTimeout(() => {
              restartTimerRef.current = null;
              void startRecordingRef.current();
            }, 120);
          }
        }
      });

      recorder.start();
      await syncSession({
        session_id: sessionId,
        voice_mode: voiceMode,
        turn_state: "listening",
        mic_state: "recording",
        capture_source: "browser",
      });
      if (
        captureAttempt !== captureAttemptRef.current ||
        recorder.state === "inactive"
      ) {
        return;
      }
      setBusy(false);
      startVad(stream, startedAtRef.current, stopRecording);

      if (pendingStopRef.current) {
        pendingStopRef.current = false;
        stopRecording();
      }
    } catch (cause) {
      if (captureAttempt !== captureAttemptRef.current) {
        return;
      }
      const message = cause instanceof Error ? cause.message : "Microphone capture failed";
      setError(message);
      pendingStopRef.current = false;
      cancelRequestedRef.current = false;
      if (sessionId) {
        try {
          await syncSession({
            session_id: sessionId,
            turn_state: "error",
            mic_state: "error",
            last_error: message,
          });
        } catch {
          // Ignore session sync errors while already reporting a capture failure.
        }
      }
      setBusy(false);
      stopVad();
    } finally {
      if (captureAttempt === captureAttemptRef.current && !recorderRef.current) {
        captureInFlightRef.current = false;
        setBusy(false);
      }
    }
  }, [busy, interruptPlayback, isSupported, mediaSession?.speaking_state, sessionId, startVad, stopRecording, stopVad, syncSession, voiceMode]);

  useEffect(() => {
    startRecordingRef.current = startRecording;
  }, [startRecording]);

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
      if (event.code !== "Space" || !hotkeyActiveRef.current) {
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

      if (
        captureInFlightRef.current ||
        (recorderRef.current && recorderRef.current.state !== "inactive")
      ) {
        event.preventDefault();
        hotkeyActiveRef.current = false;
        cancelRecording();
        return;
      }

      if (canStopSpeaking) {
        event.preventDefault();
        void interruptPlayback("Voice playback interrupted");
      }
    };

    const handleWindowBlur = () => {
      if (!hotkeyActiveRef.current) {
        return;
      }
      hotkeyActiveRef.current = false;
      stopRecording();
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
    window.addEventListener("blur", handleWindowBlur);
    window.addEventListener(NATIVE_PTT_START_EVENT, handleNativeStart);
    window.addEventListener(NATIVE_PTT_STOP_EVENT, handleNativeStop);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
      window.removeEventListener("keydown", handleCancelOrInterrupt);
      window.removeEventListener("blur", handleWindowBlur);
      window.removeEventListener(NATIVE_PTT_START_EVENT, handleNativeStart);
      window.removeEventListener(NATIVE_PTT_STOP_EVENT, handleNativeStop);
    };
  }, [canStopSpeaking, cancelRecording, interruptPlayback, startRecording, stopRecording]);

  async function handleStopSpeaking() {
    if (!sessionId || busy || !canStopSpeaking) {
      return;
    }

    setError(null);
    await interruptPlayback("Voice playback stopped");
  }

  function toggleVoiceMode() {
    const next = voiceMode === "push_to_talk" ? "conversation" : "push_to_talk";
    if (next === "push_to_talk") {
      conversationActiveRef.current = false;
      if (captureInFlightRef.current || recorderRef.current?.state === "recording") {
        cancelRecording();
      }
    }
    setVoiceMode(next);
    window.localStorage.setItem("joi_voice_mode", next);
    if (sessionId) {
      void syncSession({ session_id: sessionId, voice_mode: next });
    }
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
            className={`button ${voiceMode === "conversation" ? "secondary" : "ghost"} voice-default-toggle`}
            type="button"
            aria-pressed={voiceMode === "conversation"}
            onClick={toggleVoiceMode}
          >
            {voiceMode === "conversation" ? "Conversation mode" : "Push to talk"}
          </button>
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
            turn {mediaSession?.turn_state ?? "idle"}
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
        {mediaSession?.end_of_speech_to_transcript_ms ? (
          <span className="badge ok">
            {mediaSession.end_of_speech_to_transcript_ms}ms turn
          </span>
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
        <div className="empty-state">
          {voiceMode === "conversation"
            ? "Conversation mode stops automatically after a short silence."
            : "Voice capture is idle. Hold Ctrl+Shift+Space or record a short prompt."}
        </div>
      )}
    </div>
  );
}
