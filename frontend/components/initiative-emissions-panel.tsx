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

function fmt(ts: string | null | undefined): string {
  if (!ts) return "";
  const date = new Date(ts);
  return Number.isNaN(date.getTime()) ? String(ts) : date.toLocaleString();
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
  onFeedback,
}: {
  emission: InitiativeEmission;
  busy: boolean;
  onFeedback: (id: string, response: Exclude<InitiativeResponse, "unknown">) => void;
}) {
  const response = emission.user_response;
  return (
    <div className="list-row">
      <div>
        <strong>{emission.type}</strong>
        <p>{emission.message}</p>
        <p style={{ opacity: 0.55, fontSize: 12 }}>
          {fmt(emission.emitted_at)} * score {emission.quality_score.toFixed(2)}
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
              onFeedback={submitFeedback}
            />
          ))}
        </div>
      )}
    </section>
  );
}
