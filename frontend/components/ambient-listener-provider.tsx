"use client";

import {
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { createSession, sendChatMessage, syncAvatar } from "@/lib/api";
import { usePerceptionService } from "@/components/perception-service-provider";
import { useAmbientListener, type AmbientStatus } from "@/hooks/use-ambient-listener";
import { DEFAULT_WAKE_PHRASE } from "@/lib/wake-word";

const AMBIENT_ENABLED_KEY = "joi_ambient_enabled";
const WAKE_PHRASE_KEY = "joi_wake_phrase";
const SESSION_STORAGE_KEY = "joi-v2-session"; // shared with the chat client

export function ambientStatusLabel(status: AmbientStatus, phrase: string): string {
  switch (status) {
    case "listening":
      return `Listening for “${phrase}”…`;
    case "recording":
      return "Hearing you…";
    case "thinking":
      return "Checking if that was for me…";
    case "active":
      return "Joi’s listening — go ahead";
    case "heard":
      return "On it.";
    default:
      return "Starting ambient listening…";
  }
}

// A short, gentle two-note rise synthesized with the Web Audio API — no asset,
// no dependency. Reuses a primed AudioContext so it survives autoplay policy.
function playWakeChime(ctx: AudioContext | null) {
  if (!ctx) return;
  if (ctx.state === "suspended") void ctx.resume();
  const now = ctx.currentTime;
  [660, 988].forEach((freq, index) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = freq;
    const start = now + index * 0.085;
    gain.gain.setValueAtTime(0, start);
    gain.gain.linearRampToValueAtTime(0.14, start + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.22);
    osc.connect(gain).connect(ctx.destination);
    osc.start(start);
    osc.stop(start + 0.24);
  });
}

type AmbientContextValue = {
  enabled: boolean;
  setEnabled: (enabled: boolean) => void;
  wakePhrase: string;
  setWakePhrase: (phrase: string) => void;
  status: AmbientStatus;
  error: string | null;
  speaking: boolean;
  retry: () => void;
};

const AmbientContext = createContext<AmbientContextValue | null>(null);

export function AmbientListenerProvider({ children }: { children: ReactNode }) {
  const { sessionId, setSessionId } = usePerceptionService();
  const [enabled, setEnabledState] = useState(false);
  const [wakePhrase, setWakePhraseState] = useState(DEFAULT_WAKE_PHRASE);
  const [speaking, setSpeaking] = useState(false);
  const [dispatchError, setDispatchError] = useState<string | null>(null);
  const [wakeFlash, setWakeFlash] = useState(false);
  const [retryToken, setRetryToken] = useState(0);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const chimeCtxRef = useRef<AudioContext | null>(null);
  const flashTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sessionIdRef = useRef<string | null>(sessionId);
  const ensuringSessionRef = useRef(false);
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  // Lazily create/resume the chime AudioContext. Called from user gestures
  // (the enable toggle) so it satisfies the browser autoplay policy.
  const primeChime = useCallback(() => {
    try {
      if (!chimeCtxRef.current) chimeCtxRef.current = new window.AudioContext();
      if (chimeCtxRef.current.state === "suspended") void chimeCtxRef.current.resume();
    } catch {
      chimeCtxRef.current = null;
    }
    return chimeCtxRef.current;
  }, []);

  const handleWake = useCallback(() => {
    playWakeChime(primeChime());
    setWakeFlash(true);
    if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
    flashTimerRef.current = setTimeout(() => setWakeFlash(false), 700);
  }, [primeChime]);

  const retry = useCallback(() => {
    setDispatchError(null);
    primeChime();
    setRetryToken((token) => token + 1);
  }, [primeChime]);

  useEffect(() => {
    return () => {
      if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
      void chimeCtxRef.current?.close();
    };
  }, []);

  // Restore persisted ambient state — an always-on companion stays on across reloads.
  useEffect(() => {
    try {
      setEnabledState(window.localStorage.getItem(AMBIENT_ENABLED_KEY) === "true");
      const storedPhrase = window.localStorage.getItem(WAKE_PHRASE_KEY);
      if (storedPhrase && storedPhrase.trim()) setWakePhraseState(storedPhrase.trim());
    } catch {
      // localStorage unavailable — stay disabled.
    }
  }, []);

  const setEnabled = useCallback(
    (next: boolean) => {
      // Turning on is a user gesture — prime the chime context now so it's
      // allowed to play later without further interaction.
      if (next) primeChime();
      setEnabledState(next);
      try {
        window.localStorage.setItem(AMBIENT_ENABLED_KEY, String(next));
      } catch {
        // ignore persistence failures
      }
    },
    [primeChime],
  );

  const setWakePhrase = useCallback((phrase: string) => {
    setWakePhraseState(phrase);
    try {
      window.localStorage.setItem(WAKE_PHRASE_KEY, phrase.trim() || DEFAULT_WAKE_PHRASE);
    } catch {
      // ignore persistence failures
    }
  }, []);

  // Ensure a session exists while ambient is enabled, reusing the chat client's
  // stored session so both surfaces share one conversation.
  useEffect(() => {
    if (!enabled || sessionId || ensuringSessionRef.current) return;
    ensuringSessionRef.current = true;
    const stored =
      typeof window !== "undefined" ? window.sessionStorage.getItem(SESSION_STORAGE_KEY) : null;
    if (stored) {
      setSessionId(stored);
      ensuringSessionRef.current = false;
      return;
    }
    createSession("Joi Ambient Session")
      .then((result) => {
        try {
          window.sessionStorage.setItem(SESSION_STORAGE_KEY, result.session.id);
        } catch {
          // ignore
        }
        setSessionId(result.session.id);
      })
      .catch((error: Error) => {
        setDispatchError(error.message);
        setEnabled(false);
      })
      .finally(() => {
        ensuringSessionRef.current = false;
      });
  }, [enabled, sessionId, setSessionId, setEnabled]);

  const stopSpeaking = useCallback(() => {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
    }
    setSpeaking(false);
  }, []);

  const handleCommand = useCallback(async (command: string) => {
    const sid = sessionIdRef.current;
    if (!sid || !command.trim()) return;
    setDispatchError(null);
    try {
      const response = await sendChatMessage(sid, command);
      const reply = response.assistant_message?.content?.trim() ?? "";
      const shouldSpeak = response.avatar ? response.avatar.should_speak !== false : true;
      if (reply && shouldSpeak) {
        const payload = await syncAvatar(sid, reply);
        const audio = audioRef.current;
        if (payload.audio_url && audio) {
          audio.src = payload.audio_url;
          setSpeaking(true);
          try {
            await audio.play();
          } catch {
            setSpeaking(false);
          }
        }
      }
    } catch (error) {
      setDispatchError(error instanceof Error ? error.message : "Ambient command failed");
    }
  }, []);

  const { status, error: listenerError } = useAmbientListener({
    enabled: enabled && Boolean(sessionId),
    sessionId,
    wakePhrase,
    assistantSpeaking: speaking,
    onCommand: handleCommand,
    onInterrupt: stopSpeaking,
    onWake: handleWake,
    retryToken,
  });

  // Ambient turned off: stop any in-progress reply.
  useEffect(() => {
    if (!enabled) stopSpeaking();
  }, [enabled, stopSpeaking]);

  const error = listenerError ?? dispatchError;
  const value = useMemo<AmbientContextValue>(
    () => ({
      enabled,
      setEnabled,
      wakePhrase,
      setWakePhrase,
      status,
      error,
      speaking,
      retry,
    }),
    [enabled, setEnabled, wakePhrase, setWakePhrase, status, error, speaking, retry],
  );

  // A mic error only matters while ambient is meant to be on.
  const micError = enabled ? listenerError : null;

  return (
    <AmbientContext.Provider value={value}>
      {children}
      {enabled ? (
        <div
          className={`ambient-indicator${micError ? " error" : ""}${wakeFlash ? " wake" : ""}${
            speaking ? " speaking" : ""
          }`}
          role="status"
          aria-live="polite"
        >
          {micError ? (
            <button
              type="button"
              className="ambient-indicator-retry"
              onClick={retry}
              title="Microphone blocked or unavailable — click to retry"
            >
              <span className="ambient-dot error" aria-hidden="true" />
              <span className="ambient-indicator-label">Mic unavailable — retry</span>
            </button>
          ) : (
            <>
              <span className={`ambient-dot${speaking ? " speaking" : ""}`} aria-hidden="true" />
              <span className="ambient-indicator-label">
                {ambientStatusLabel(status, wakePhrase)}
              </span>
            </>
          )}
          <button
            type="button"
            className="ambient-indicator-off"
            onClick={() => setEnabled(false)}
            aria-label="Turn off ambient listening"
            title="Turn off ambient listening"
          >
            ×
          </button>
        </div>
      ) : null}
      <audio
        ref={audioRef}
        onEnded={() => setSpeaking(false)}
        onError={() => setSpeaking(false)}
        hidden
      />
    </AmbientContext.Provider>
  );
}

export function useAmbient(): AmbientContextValue {
  const context = useContext(AmbientContext);
  if (!context) {
    throw new Error("useAmbient must be used within AmbientListenerProvider");
  }
  return context;
}
