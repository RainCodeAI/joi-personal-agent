"use client";

import { useState } from "react";
import { recordInitiativeFeedback } from "@/lib/api";
import { InitiativeEmission, InitiativeResponse } from "@/lib/types";

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

function EmissionRow({ emission }: { emission: InitiativeEmission }) {
  const [response, setResponse] = useState<InitiativeResponse>(emission.user_response);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(next: Exclude<InitiativeResponse, "unknown">) {
    if (busy || response === next) return;
    setBusy(true);
    setError(null);
    const previous = response;
    setResponse(next); // optimistic
    try {
      await recordInitiativeFeedback(emission.id, next);
    } catch {
      setResponse(previous);
      setError("Couldn't save — try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="list-row">
      <div>
        <strong>{emission.type}</strong>
        <p>{emission.message}</p>
        <p style={{ opacity: 0.55, fontSize: 12 }}>
          {fmt(emission.emitted_at)} * score {emission.quality_score.toFixed(2)}
        </p>
        <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
          <button
            type="button"
            className="button ghost"
            disabled={busy || response === "negative"}
            onClick={() => submit("negative")}
          >
            Not welcome
          </button>
          <button
            type="button"
            className="button ghost"
            disabled={busy || response === "engaged"}
            onClick={() => submit("engaged")}
          >
            Helpful
          </button>
        </div>
        {error && <p style={{ color: "var(--danger, #c0392b)", fontSize: 12 }}>{error}</p>}
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
  return (
    <section className="panel">
      <p className="eyebrow">Initiative</p>
      <h3>Proactive history</h3>
      {initialEmissions.length === 0 ? (
        <p style={{ opacity: 0.5, fontSize: 13 }}>
          No evidence-bound initiatives emitted yet.
        </p>
      ) : (
        <div className="list">
          {initialEmissions.map((emission) => (
            <EmissionRow key={emission.id} emission={emission} />
          ))}
        </div>
      )}
    </section>
  );
}
