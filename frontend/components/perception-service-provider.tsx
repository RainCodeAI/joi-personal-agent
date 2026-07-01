"use client";

import {
  ReactNode,
  createContext,
  startTransition,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { PerceptionEngine } from "@/components/perception-engine";
import { postActivityState } from "@/lib/api";
import type { PerceptionSignal, PerceptionState, SnapshotAnalysis } from "@/lib/types";

type PerceptionServiceContextValue = {
  perceptionState: PerceptionState;
  perceptionExpression: string | null;
  lastSnapshotAnalysis: SnapshotAnalysis | null;
  sessionId: string | null;
  setSessionId: (sessionId: string | null) => void;
  clearLastSnapshotAnalysis: () => void;
  handleSignal: (signal: PerceptionSignal) => void;
};

const INITIAL_PERCEPTION_STATE: PerceptionState = {
  userPresent: false,
  faceVisible: false,
  leanedIn: false,
  currentExpression: null,
  lastSignal: null,
  updatedAt: 0,
};

const PerceptionServiceContext = createContext<PerceptionServiceContextValue | null>(null);

export function PerceptionServiceProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionIdState] = useState<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const [perceptionState, setPerceptionState] = useState<PerceptionState>(
    INITIAL_PERCEPTION_STATE,
  );
  const [perceptionExpression, setPerceptionExpression] = useState<string | null>(null);
  const [lastSnapshotAnalysis, setLastSnapshotAnalysis] = useState<SnapshotAnalysis | null>(null);
  const lookAwayResetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (lookAwayResetTimerRef.current) {
        clearTimeout(lookAwayResetTimerRef.current);
      }
    };
  }, []);

  const setSessionId = useCallback((nextSessionId: string | null) => {
    sessionIdRef.current = nextSessionId;
    setSessionIdState(nextSessionId);
  }, []);

  const clearLastSnapshotAnalysis = useCallback(() => {
    setLastSnapshotAnalysis(null);
  }, []);

  const handlePerceptionSignal = useCallback((signal: PerceptionSignal) => {
    // returned_to_frame is edge-triggered by the camera engine, so no extra debounce is needed.
    const activeSessionId = sessionIdRef.current;
    if (activeSessionId) {
      if (signal.signal === "returned_to_frame") {
        postActivityState(activeSessionId, "returned", "browser_perception");
      } else if (signal.signal === "looked_away") {
        postActivityState(activeSessionId, "away", "browser_perception");
      }
    }

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
            signal.signal === "expression_possible_tension" ? "possible_tension" :
            signal.signal === "expression_surprise" ? "surprise" :
            signal.signal === "expression_neutral"  ? "neutral"  :
            prev.currentExpression,
          lastSignal: signal,
          updatedAt: signal.timestamp,
        };
      });
    });

    if (signal.signal === "expression_smile") {
      setPerceptionExpression("smirk");
    } else if (signal.signal === "expression_possible_tension") {
      setPerceptionExpression("concern");
    } else if (signal.signal === "expression_surprise") {
      setPerceptionExpression("shock");
    } else if (signal.signal === "expression_neutral") {
      setPerceptionExpression(null);
    } else if (signal.signal === "looked_away") {
      setPerceptionExpression("missing");
      if (lookAwayResetTimerRef.current) {
        clearTimeout(lookAwayResetTimerRef.current);
      }
      lookAwayResetTimerRef.current = setTimeout(() => {
        setPerceptionExpression(null);
      }, 4000);
    } else if (signal.signal === "returned_to_frame") {
      if (lookAwayResetTimerRef.current) {
        clearTimeout(lookAwayResetTimerRef.current);
      }
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

  const value = useMemo<PerceptionServiceContextValue>(
    () => ({
      perceptionState,
      perceptionExpression,
      lastSnapshotAnalysis,
      sessionId,
      setSessionId,
      clearLastSnapshotAnalysis,
      handleSignal: handlePerceptionSignal,
    }),
    [
      clearLastSnapshotAnalysis,
      handlePerceptionSignal,
      lastSnapshotAnalysis,
      perceptionExpression,
      perceptionState,
      sessionId,
      setSessionId,
    ],
  );

  return (
    <PerceptionServiceContext.Provider value={value}>
      {children}
    </PerceptionServiceContext.Provider>
  );
}

export function PerceptionServicePanel() {
  const { sessionId, handleSignal } = usePerceptionService();
  return <PerceptionEngine sessionId={sessionId} onSignal={handleSignal} />;
}

export function usePerceptionService() {
  const context = useContext(PerceptionServiceContext);
  if (!context) {
    throw new Error("usePerceptionService must be used within PerceptionServiceProvider");
  }
  return context;
}
