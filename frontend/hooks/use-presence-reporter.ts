"use client";

import { useEffect, useRef } from "react";

import { postActivityState } from "@/lib/api";

// Fire "active" at most once per 2 minutes to avoid spamming the endpoint on
// every mousemove. The idle timer below fires "away" after IDLE_TIMEOUT_MS of
// no activity regardless of this debounce.
const ACTIVE_DEBOUNCE_MS = 2 * 60 * 1000;
const IDLE_TIMEOUT_MS = 10 * 60 * 1000;

const TRACKED_EVENTS = ["mousemove", "keydown", "pointerdown", "scroll"] as const;

/**
 * Detects browser-level presence (tab visibility + mouse/keyboard idle) and
 * posts activity state changes to the initiative endpoint. Complements the
 * camera-based PerceptionEngine signals in chat-client.tsx.
 *
 * Uses "returned" (not "active") on tab-visible and page-focus transitions so
 * the backend return-after-absence gate can evaluate correctly.
 */
export function usePresenceReporter(sessionId: string | null): void {
  const sessionIdRef = useRef<string | null>(sessionId);
  const lastActiveSentRef = useRef<number>(0);
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Keep ref in sync so event handlers always see the current sessionId
  // without needing to be recreated.
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) return;

    function resetIdleTimer() {
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
      idleTimerRef.current = setTimeout(() => {
        const sid = sessionIdRef.current;
        if (sid) postActivityState(sid, "away", "browser_idle");
      }, IDLE_TIMEOUT_MS);
    }

    function sendActive(state: "active" | "returned" = "active") {
      const sid = sessionIdRef.current;
      if (!sid) return;
      const now = Date.now();
      if (state === "active" && now - lastActiveSentRef.current < ACTIVE_DEBOUNCE_MS) return;
      lastActiveSentRef.current = now;
      postActivityState(sid, state, "browser_idle");
      resetIdleTimer();
    }

    function handleVisibility() {
      if (document.hidden) {
        const sid = sessionIdRef.current;
        if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
        if (sid) postActivityState(sid, "away", "browser_visibility");
      } else {
        // Tab became visible — treat as return, not just active, so the
        // return-after-absence gate has a chance to fire if the user was
        // gone long enough.
        lastActiveSentRef.current = 0;
        sendActive("returned");
      }
    }

    function handleActivity() {
      sendActive("active");
    }

    document.addEventListener("visibilitychange", handleVisibility);
    for (const ev of TRACKED_EVENTS) {
      window.addEventListener(ev, handleActivity, { passive: true });
    }

    // Kick off the idle timer immediately so a user who opens the tab and
    // does nothing for 10 minutes still gets marked away.
    resetIdleTimer();

    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
      for (const ev of TRACKED_EVENTS) {
        window.removeEventListener(ev, handleActivity);
      }
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    };
  // Only re-run when sessionId transitions from null → a real value.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);
}
