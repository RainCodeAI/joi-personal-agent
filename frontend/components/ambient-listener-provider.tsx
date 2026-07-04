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
      return "Ambient listening is off.";
  }
}

type AmbientContextValue = {
  enabled: boolean;
  setEnabled: (enabled: boolean) => void;
  wakePhrase: string;
  setWakePhrase: (phrase: string) => void;
  status: AmbientStatus;
  error: string | null;
  speaking: boolean;
};

const AmbientContext = createContext<AmbientContextValue | null>(null);

export function AmbientListenerProvider({ children }: { children: ReactNode }) {
  const { sessionId, setSessionId } = usePerceptionService();
  const [enabled, setEnabledState] = useState(false);
  const [wakePhrase, setWakePhraseState] = useState(DEFAULT_WAKE_PHRASE);
  const [speaking, setSpeaking] = useState(false);
  const [dispatchError, setDispatchError] = useState<string | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const sessionIdRef = useRef<string | null>(sessionId);
  const ensuringSessionRef = useRef(false);
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

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

  const setEnabled = useCallback((next: boolean) => {
    setEnabledState(next);
    try {
      window.localStorage.setItem(AMBIENT_ENABLED_KEY, String(next));
    } catch {
      // ignore persistence failures
    }
  }, []);

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
  });

  // Ambient turned off: stop any in-progress reply.
  useEffect(() => {
    if (!enabled) stopSpeaking();
  }, [enabled, stopSpeaking]);

  const value = useMemo<AmbientContextValue>(
    () => ({
      enabled,
      setEnabled,
      wakePhrase,
      setWakePhrase,
      status,
      error: listenerError ?? dispatchError,
      speaking,
    }),
    [enabled, setEnabled, wakePhrase, setWakePhrase, status, listenerError, dispatchError, speaking],
  );

  return (
    <AmbientContext.Provider value={value}>
      {children}
      {enabled ? (
        <div className="ambient-indicator" role="status" aria-live="polite">
          <span className={`ambient-dot${speaking ? " speaking" : ""}`} aria-hidden="true" />
          <span className="ambient-indicator-label">{ambientStatusLabel(status, wakePhrase)}</span>
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
