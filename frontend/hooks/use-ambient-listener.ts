"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { transcribeAudioBlob } from "@/lib/api";
import { detectWakeWord } from "@/lib/wake-word";

// Reuses the same VAD tuning as the push-to-talk/conversation composer.
const VAD_RMS_THRESHOLD = 0.025;
const VAD_PLAYBACK_RMS_THRESHOLD = 0.055;
const VAD_REQUIRED_FRAMES = 3;
const VAD_INTERVAL_MS = 80;
const SILENCE_MS = 900; // end an utterance after this much trailing silence
const MAX_UTTERANCE_MS = 15_000;
const MIN_UTTERANCE_MS = 350; // ignore blips too short to be speech
// After a bare "Hey Joi", the next utterance is treated as the command without
// needing the wake word again.
const ACTIVE_WINDOW_MS = 8_000;

export type AmbientStatus =
  | "idle"
  | "listening" // waiting for the wake phrase
  | "recording" // capturing an utterance
  | "thinking" // transcribing / gating
  | "active" // heard a bare wake, awaiting the command
  | "heard"; // a command was dispatched

type UseAmbientListenerArgs = {
  enabled: boolean;
  sessionId: string | null;
  wakePhrase: string;
  assistantSpeaking: boolean;
  onCommand: (command: string) => void | Promise<void>;
  onInterrupt: () => void | Promise<void>;
  /** Fired the instant the wake phrase is recognized, before the command runs. */
  onWake?: () => void;
  /** Bumping this re-acquires the microphone — used to retry after a denial. */
  retryToken?: number;
};

type UseAmbientListenerResult = {
  status: AmbientStatus;
  supported: boolean;
  error: string | null;
};

function pickRecorderMimeType(): string {
  if (typeof MediaRecorder === "undefined") return "";
  for (const candidate of ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"]) {
    if (MediaRecorder.isTypeSupported(candidate)) return candidate;
  }
  return "";
}

/**
 * Always-listening wake-word loop. While `enabled`, holds the mic open, gates
 * speech through a local VAD, transcribes each utterance as a silent wake probe,
 * and only surfaces a command (via `onCommand`) when the wake phrase is heard.
 * Everything else is discarded — nothing Joi merely overhears leaves this hook.
 */
export function useAmbientListener({
  enabled,
  sessionId,
  wakePhrase,
  assistantSpeaking,
  onCommand,
  onInterrupt,
  onWake,
  retryToken = 0,
}: UseAmbientListenerArgs): UseAmbientListenerResult {
  const [status, setStatus] = useState<AmbientStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [supported, setSupported] = useState(false);

  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const samplesRef = useRef<Float32Array<ArrayBuffer> | null>(null);
  const vadTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const phaseRef = useRef<"monitoring" | "recording" | "transcribing">("monitoring");
  const speechFramesRef = useRef(0);
  const recordingStartedAtRef = useRef(0);
  const lastSpeechAtRef = useRef(0);
  const activeUntilRef = useRef(0);
  const runningRef = useRef(false);

  // Keep the latest callbacks / flags without re-subscribing the loop.
  const assistantSpeakingRef = useRef(assistantSpeaking);
  const wakePhraseRef = useRef(wakePhrase);
  const onCommandRef = useRef(onCommand);
  const onInterruptRef = useRef(onInterrupt);
  const onWakeRef = useRef(onWake);
  useEffect(() => {
    assistantSpeakingRef.current = assistantSpeaking;
  }, [assistantSpeaking]);
  useEffect(() => {
    wakePhraseRef.current = wakePhrase;
  }, [wakePhrase]);
  useEffect(() => {
    onCommandRef.current = onCommand;
  }, [onCommand]);
  useEffect(() => {
    onInterruptRef.current = onInterrupt;
  }, [onInterrupt]);
  useEffect(() => {
    onWakeRef.current = onWake;
  }, [onWake]);

  useEffect(() => {
    setSupported(
      typeof window !== "undefined" &&
        typeof navigator !== "undefined" &&
        Boolean(navigator.mediaDevices?.getUserMedia) &&
        typeof MediaRecorder !== "undefined",
    );
  }, []);

  const gateTranscript = useCallback(async (transcript: string) => {
    const now = performance.now();
    const withinActiveWindow = now < activeUntilRef.current;
    const { matched, command } = detectWakeWord(transcript, wakePhraseRef.current);

    let dispatch: string | null = null;
    if (matched) {
      if (command) {
        dispatch = command;
        activeUntilRef.current = 0;
      } else {
        // Bare "Hey Joi" — open a short window for the follow-up command.
        activeUntilRef.current = now + ACTIVE_WINDOW_MS;
        setStatus("active");
      }
    } else if (withinActiveWindow) {
      dispatch = transcript.trim();
      activeUntilRef.current = 0;
    }
    // Otherwise: overheard speech, silently discarded.

    // Acknowledge the moment we recognize we're being addressed — before the
    // (slower) command round-trip — so the chime/flash feels instant.
    if (matched || dispatch) {
      onWakeRef.current?.();
    }

    if (dispatch) {
      setStatus("heard");
      if (assistantSpeakingRef.current) {
        try {
          await onInterruptRef.current();
        } catch {
          // Barge-in is best-effort; still deliver the command.
        }
      }
      try {
        await onCommandRef.current(dispatch);
      } catch {
        // Command dispatch failures are surfaced by the chat pipeline itself.
      }
    }
  }, []);

  useEffect(() => {
    if (!enabled || !sessionId || !supported) {
      setStatus("idle");
      return;
    }

    runningRef.current = true;
    let cancelled = false;
    setError(null);

    const finishSegmentToMonitoring = () => {
      phaseRef.current = "monitoring";
      speechFramesRef.current = 0;
      if (runningRef.current && !cancelled) {
        setStatus(performance.now() < activeUntilRef.current ? "active" : "listening");
      }
    };

    const stopRecorder = () => {
      const recorder = recorderRef.current;
      if (recorder && recorder.state !== "inactive") {
        recorder.stop();
      }
    };

    const beginRecording = () => {
      const stream = streamRef.current;
      if (!stream) return;
      chunksRef.current = [];
      const mimeType = pickRecorderMimeType();
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      recorderRef.current = recorder;
      recordingStartedAtRef.current = performance.now();
      lastSpeechAtRef.current = performance.now();

      recorder.addEventListener("dataavailable", (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      });

      recorder.addEventListener("stop", async () => {
        const durationMs = performance.now() - recordingStartedAtRef.current;
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        recorderRef.current = null;

        if (cancelled || durationMs < MIN_UTTERANCE_MS || blob.size === 0) {
          finishSegmentToMonitoring();
          return;
        }

        phaseRef.current = "transcribing";
        setStatus("thinking");
        try {
          const response = await transcribeAudioBlob(sessionId, blob, Math.round(durationMs), {
            voiceMode: "ambient",
            speechDetected: true,
            wakeProbe: true,
          });
          if (!cancelled && response.transcript.trim()) {
            await gateTranscript(response.transcript);
          }
        } catch (cause) {
          if (!cancelled) {
            setError(cause instanceof Error ? cause.message : "Wake-word transcription failed");
          }
        } finally {
          finishSegmentToMonitoring();
        }
      });

      recorder.start();
      phaseRef.current = "recording";
      setStatus("recording");
    };

    const tick = () => {
      const analyser = analyserRef.current;
      const samples = samplesRef.current;
      if (!analyser || !samples) return;
      analyser.getFloatTimeDomainData(samples);
      let sum = 0;
      for (const sample of samples) sum += sample * sample;
      const rms = Math.sqrt(sum / samples.length);
      const now = performance.now();
      const threshold = assistantSpeakingRef.current
        ? VAD_PLAYBACK_RMS_THRESHOLD
        : VAD_RMS_THRESHOLD;

      if (phaseRef.current === "monitoring") {
        if (rms >= threshold) {
          speechFramesRef.current += 1;
          if (speechFramesRef.current >= VAD_REQUIRED_FRAMES) {
            beginRecording();
          }
        } else {
          speechFramesRef.current = 0;
        }
        return;
      }

      if (phaseRef.current === "recording") {
        if (rms >= threshold) {
          lastSpeechAtRef.current = now;
        }
        const elapsed = now - recordingStartedAtRef.current;
        const silence = now - lastSpeechAtRef.current;
        if (silence >= SILENCE_MS || elapsed >= MAX_UTTERANCE_MS) {
          stopRecorder();
        }
      }
    };

    const start = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;

        const AudioContextClass = window.AudioContext;
        const context = new AudioContextClass();
        const analyser = context.createAnalyser();
        analyser.fftSize = 1024;
        context.createMediaStreamSource(stream).connect(analyser);
        audioContextRef.current = context;
        analyserRef.current = analyser;
        samplesRef.current = new Float32Array(analyser.fftSize);

        phaseRef.current = "monitoring";
        speechFramesRef.current = 0;
        setStatus("listening");
        vadTimerRef.current = setInterval(tick, VAD_INTERVAL_MS);
      } catch (cause) {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Microphone unavailable for ambient mode");
          setStatus("idle");
        }
      }
    };

    void start();

    return () => {
      cancelled = true;
      runningRef.current = false;
      activeUntilRef.current = 0;
      if (vadTimerRef.current) clearInterval(vadTimerRef.current);
      vadTimerRef.current = null;
      const recorder = recorderRef.current;
      if (recorder && recorder.state !== "inactive") recorder.stop();
      recorderRef.current = null;
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      void audioContextRef.current?.close();
      audioContextRef.current = null;
      analyserRef.current = null;
      samplesRef.current = null;
      setStatus("idle");
    };
    // retryToken is intentionally a dependency: bumping it re-runs this effect,
    // tearing down and re-acquiring the mic (used to retry after a denial).
  }, [enabled, sessionId, supported, gateTranscript, retryToken]);

  // Clear a stale error on each fresh (re)start attempt.
  useEffect(() => {
    if (enabled) setError(null);
  }, [enabled, retryToken]);

  return { status, supported, error };
}
