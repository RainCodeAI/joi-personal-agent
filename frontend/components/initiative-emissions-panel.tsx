"use client";

import { useCallback, useEffect, useState } from "react";
import { createEventStream, listInitiativeEmissions, recordInitiativeFeedback } from "@/lib/api";
import { InitiativeEmission, InitiativeResponse } from "@/lib/types";

// Backend events that change what belongs in this panel.
const REFRESH_EVENTS = new Set([
  "initiative.emitted",
  "initiative.feedback",
  "initiative.suppressed",
]);

function responseTone(response: InitiativeResponse): string {
  if (response === "engaged") return "ok";
  if (response === "negative") return "warn";
  return "";
}

// "2h ago" / "in 30m", with the full timestamp kept for the tooltip. `now` is
// null until the client mounts — the server can't compute a locale/clock value
// that matches the browser, so we render a stable placeholder until then to
// avoid a hydration mismatch.
function relativeTime(
  ts: string | null | undefined,
  now: number | null,
): { rel: string; abs: string } {
  if (!ts) return { rel: "", abs: "" };
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return { rel: String(ts), abs: String(ts) };
  if (now === null) return { rel: "…", abs: "" };
  const abs = date.toLocaleString();
  const diffMs = now - date.getTime();
  const past = diffMs >= 0;
  const seconds = Math.abs(diffMs) / 1000;
  if (seconds < 45) return { rel: "just now", abs };
  const minutes = seconds / 60;
  const hours = minutes / 60;
  const days = hours / 24;
  const magnitude =
    minutes < 45 ? `${Math.round(minutes)}m` : hours < 24 ? `${Math.round(hours)}h` : `${Math.round(days)}d`;
  return { rel: past ? `${magnitude} ago` : `in ${magnitude}`, abs };
}

function humanizeType(type: string): string {
  const spaced = type.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

const SOURCE_BY_TYPE: Record<string, string> = {
  calendar_heads_up: "calendar",
  memory_followup: "memory",
};

function sourceOf(type: string): string {
  return SOURCE_BY_TYPE[type] ?? type.split("_")[0];
}

// Order the gate's dimensions read naturally: what/when/how-fresh/how-novel/safe.
const DIMENSION_ORDER = ["relevance", "timing", "recency", "novelty", "safety"] as const;

function DimensionBar({ label, value, tone }: { label: string; value: number; tone?: "warn" }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  const fill = tone === "warn" ? "var(--amber, #d08a2c)" : "var(--joi, #4bb3a7)";
  return (
    <span
      title={`${label} ${value.toFixed(2)}`}
      style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--muted)" }}
    >
      <span style={{ minWidth: 58, textTransform: "capitalize" }}>{label}</span>
      <span
        style={{
          position: "relative",
          width: 44,
          height: 4,
          borderRadius: 2,
          background: "var(--line, rgba(128,128,128,0.25))",
        }}
      >
        <span
          style={{
            position: "absolute",
            insetBlock: 0,
            left: 0,
            width: `${pct}%`,
            borderRadius: 2,
            background: fill,
          }}
        />
      </span>
      <span style={{ fontVariantNumeric: "tabular-nums" }}>{value.toFixed(2)}</span>
    </span>
  );
}

function QualityBreakdown({ dimensions }: { dimensions?: Record<string, number> }) {
  if (!dimensions || Object.keys(dimensions).length === 0) return null;
  const factor = dimensions.feedback_factor;
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: "4px 14px",
        marginTop: 6,
        paddingTop: 6,
        borderTop: "1px solid var(--line, rgba(128,128,128,0.2))",
      }}
    >
      {DIMENSION_ORDER.filter((key) => key in dimensions).map((key) => (
        <DimensionBar key={key} label={key} value={dimensions[key]} />
      ))}
      {typeof factor === "number" && factor !== 1 && (
        <DimensionBar label="feedback" value={factor} tone="warn" />
      )}
    </div>
  );
}

function EmissionRow({
  emission,
  busy,
  now,
  onFeedback,
}: {
  emission: InitiativeEmission;
  busy: boolean;
  now: number | null;
  onFeedback: (id: string, response: Exclude<InitiativeResponse, "unknown">) => void;
}) {
  const response = emission.user_response;
  const time = relativeTime(emission.emitted_at, now);
  return (
    <div className="list-row">
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            style={{
              fontSize: 10,
              textTransform: "uppercase",
              letterSpacing: "0.04em",
              padding: "1px 6px",
              borderRadius: 999,
              color: "var(--muted)",
              border: "1px solid var(--line, rgba(128,128,128,0.3))",
            }}
          >
            {sourceOf(emission.type)}
          </span>
          <strong>{humanizeType(emission.type)}</strong>
        </div>
        <p>{emission.message}</p>
        <p
          style={{ opacity: 0.55, fontSize: 12 }}
          title={time.abs || undefined}
          suppressHydrationWarning
        >
          {time.rel} * score {emission.quality_score.toFixed(2)}
        </p>
        <QualityBreakdown dimensions={emission.dimensions} />
        <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
          <button
            type="button"
            className="button ghost"
            disabled={busy || response === "negative"}
            onClick={() => onFeedback(emission.id, "negative")}
          >
            Not welcome
          </button>
          <button
            type="button"
            className="button ghost"
            disabled={busy || response === "engaged"}
            onClick={() => onFeedback(emission.id, "engaged")}
          >
            Helpful
          </button>
        </div>
      </div>
      <span className={`badge ${responseTone(response)}`}>{response}</span>
    </div>
  );
}

export function InitiativeEmissionsPanel({
  initialEmissions,
}: {
  initialEmissions: InitiativeEmission[];
}) {
  const [emissions, setEmissions] = useState<InitiativeEmission[]>(initialEmissions);
  const [busyIds, setBusyIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  // Null on the server / first render; set on mount so relative times are the
  // browser's (avoids a hydration mismatch) and tick forward each minute.
  const [now, setNow] = useState<number | null>(null);

  useEffect(() => {
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(timer);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const { emissions: latest } = await listInitiativeEmissions();
      setEmissions(latest);
    } catch {
      // Keep the current view; a later event or reload will resync.
    }
  }, []);

  // Live-refresh: re-pull the list whenever an initiative is emitted, suppressed,
  // or gets feedback (possibly from another surface). Initiatives fire on the
  // "default" session; null-session events (feedback) reach every subscriber.
  useEffect(() => {
    const stream = createEventStream("default", (event) => {
      if (REFRESH_EVENTS.has(event.event)) {
        void refresh();
      }
    });
    return () => stream.close();
  }, [refresh]);

  const submitFeedback = useCallback(
    async (id: string, next: Exclude<InitiativeResponse, "unknown">) => {
      setBusyIds((prev) => new Set(prev).add(id));
      setError(null);
      setEmissions((prev) =>
        prev.map((em) => (em.id === id ? { ...em, user_response: next } : em)),
      );
      try {
        await recordInitiativeFeedback(id, next);
      } catch {
        setError("Couldn't save feedback — try again.");
        await refresh(); // resync to the authoritative server state
      } finally {
        setBusyIds((prev) => {
          const nextSet = new Set(prev);
          nextSet.delete(id);
          return nextSet;
        });
      }
    },
    [refresh],
  );

  return (
    <section className="panel">
      <p className="eyebrow">Initiative</p>
      <h3>Proactive history</h3>
      {error && <p style={{ color: "var(--danger, #c0392b)", fontSize: 12 }}>{error}</p>}
      {emissions.length === 0 ? (
        <p style={{ opacity: 0.5, fontSize: 13 }}>
          No evidence-bound initiatives emitted yet.
        </p>
      ) : (
        <div className="list">
          {emissions.map((emission) => (
            <EmissionRow
              key={emission.id}
              emission={emission}
              busy={busyIds.has(emission.id)}
              now={now}
              onFeedback={submitFeedback}
            />
          ))}
        </div>
      )}
    </section>
  );
}
