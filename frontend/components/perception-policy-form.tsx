"use client";

import { useState } from "react";

import { patchPerceptionPolicy } from "@/lib/api";
import type { PerceptionPolicy } from "@/lib/types";

type PerceptionPolicyFormProps = {
  policy: PerceptionPolicy;
};

const LIVE_ONLY_SIGNALS = [
  { label: "Face presence detection", detail: "Is a face visible right now?" },
  { label: "Gaze & attention state", detail: "looked_away, returned_to_frame, leaned_in" },
  { label: "Expression classification", detail: "smile, stress, surprise — local WASM only" },
];

export function PerceptionPolicyForm({ policy: initialPolicy }: PerceptionPolicyFormProps) {
  const [policy, setPolicy] = useState(initialPolicy);
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  async function save(patch: Partial<PerceptionPolicy>) {
    setStatus("saving");
    setErrorMsg(null);
    try {
      const result = await patchPerceptionPolicy(patch);
      setPolicy(result.policy);
      setStatus("saved");
      setTimeout(() => setStatus("idle"), 2000);
    } catch (cause) {
      setErrorMsg(cause instanceof Error ? cause.message : "Save failed");
      setStatus("error");
    }
  }

  function toggle(field: keyof PerceptionPolicy) {
    const next = { ...policy, [field]: !policy[field as keyof typeof policy] };
    setPolicy(next);
    void save({ [field]: next[field as keyof typeof next] });
  }

  function handleRetentionDays(value: number) {
    const clamped = Math.max(0, Math.min(365, value));
    setPolicy((p) => ({ ...p, retention_days: clamped }));
  }

  function saveRetentionDays() {
    void save({ retention_days: policy.retention_days });
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* ── Global kill switch ─────────────────────────────────────────── */}
      <div className="panel">
        <p className="eyebrow">Camera Access</p>
        <h3>Master control</h3>
        <p style={{ fontSize: "0.82rem", color: "var(--color-muted)", margin: "6px 0 14px" }}>
          When disabled, Joi will not request camera access and all perception features are suspended.
        </p>
        <div className="button-row">
          <button
            className={`button ${policy.camera_enabled ? "secondary" : "ghost"}`}
            type="button"
            onClick={() => toggle("camera_enabled")}
            disabled={status === "saving"}
          >
            Camera: {policy.camera_enabled ? "enabled" : "disabled"}
          </button>
          <span className={`badge ${policy.camera_enabled ? "ok" : "warn"}`}>
            {policy.camera_enabled ? "active" : "suspended"}
          </span>
        </div>
      </div>

      <div className="panel">
        <p className="eyebrow">Screen Access</p>
        <h3>One-shot desktop context</h3>
        <p style={{ fontSize: "0.82rem", color: "var(--color-muted)", margin: "6px 0 14px" }}>
          Manual capture opens the operating-system screen/window picker every time. Joi cannot
          capture silently or continuously, and the raw frame is discarded after the chat request.
        </p>
        <div className="button-row">
          <button
            className={`button ${policy.screen_access === "disabled" ? "secondary" : "ghost"}`}
            type="button"
            disabled={status === "saving"}
            onClick={() => void save({ screen_access: "disabled" })}
          >
            Disabled
          </button>
          <button
            className={`button ${policy.screen_access === "manual_only" ? "secondary" : "ghost"}`}
            type="button"
            disabled={status === "saving"}
            onClick={() => void save({ screen_access: "manual_only" })}
          >
            Manual only
          </button>
          <span className={`badge ${policy.screen_access === "disabled" ? "ok" : "warn"}`}>
            {policy.screen_access === "disabled" ? "no access" : "asks every time"}
          </span>
        </div>
      </div>

      {/* ── Live-only section ──────────────────────────────────────────── */}
      <div className="panel">
        <p className="eyebrow">Always Local</p>
        <h3>Live sensing — never stored</h3>
        <p style={{ fontSize: "0.82rem", color: "var(--color-muted)", margin: "6px 0 14px" }}>
          These signals are computed in your browser via WebAssembly and are discarded immediately.
          No data reaches any server and nothing is written to memory.
        </p>
        <div className="list">
          {LIVE_ONLY_SIGNALS.map((s) => (
            <div className="list-row" key={s.label}>
              <div>
                <strong>{s.label}</strong>
                <p style={{ fontSize: "0.78rem", color: "var(--color-muted)" }}>{s.detail}</p>
              </div>
              <span className="badge ok">local only</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Retention section ──────────────────────────────────────────── */}
      <div className="panel">
        <p className="eyebrow">Visual Memory</p>
        <h3>What gets remembered</h3>
        <p style={{ fontSize: "0.82rem", color: "var(--color-muted)", margin: "6px 0 14px" }}>
          Both options below are <strong>off by default</strong>. Enabling either means Joi will
          write perception data into her long-term memory store so it can influence future
          conversations.
        </p>

        <div className="list">
          <div className="list-row">
            <div>
              <strong>Expression events</strong>
              <p style={{ fontSize: "0.78rem", color: "var(--color-muted)" }}>
                Stores a note when your expression changes (e.g. "user smiled at 14:32").
              </p>
            </div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
              <span className={`badge ${policy.retain_expressions ? "warn" : ""}`}>
                {policy.retain_expressions ? "stored" : "discarded"}
              </span>
              <button
                className={`button ${policy.retain_expressions ? "secondary" : "ghost"}`}
                type="button"
                disabled={status === "saving"}
                onClick={() => toggle("retain_expressions")}
              >
                {policy.retain_expressions ? "Turn off" : "Turn on"}
              </button>
            </div>
          </div>

          <div className="list-row">
            <div>
              <strong>Scene snapshots</strong>
              <p style={{ fontSize: "0.78rem", color: "var(--color-muted)" }}>
                Stores the text description from "Capture scene" in memory. No image is ever saved —
                only the AI-generated description.
              </p>
            </div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
              <span className={`badge ${policy.retain_snapshots ? "warn" : ""}`}>
                {policy.retain_snapshots ? "stored" : "discarded"}
              </span>
              <button
                className={`button ${policy.retain_snapshots ? "secondary" : "ghost"}`}
                type="button"
                disabled={status === "saving"}
                onClick={() => toggle("retain_snapshots")}
              >
                {policy.retain_snapshots ? "Turn off" : "Turn on"}
              </button>
            </div>
          </div>
        </div>

        {(policy.retain_expressions || policy.retain_snapshots) ? (
          <div style={{ marginTop: 18 }}>
            <div className="field">
              <label htmlFor="retention-days">
                Retention window (days) — <strong>0 = current session only</strong>
              </label>
              <div className="button-row" style={{ marginTop: 6 }}>
                <input
                  id="retention-days"
                  className="input"
                  type="number"
                  min={0}
                  max={365}
                  value={policy.retention_days}
                  onChange={(e) => handleRetentionDays(Number(e.target.value))}
                  style={{ width: 100 }}
                />
                <button
                  className="button ghost"
                  type="button"
                  disabled={status === "saving"}
                  onClick={saveRetentionDays}
                >
                  Save
                </button>
                <span className="badge">
                  {policy.retention_days === 0 ? "session only" : `${policy.retention_days}d`}
                </span>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      {/* ── Status + audit trail ───────────────────────────────────────── */}
      <div className="panel">
        <p className="eyebrow">Audit</p>
        <h3>Current posture</h3>
        <div className="list">
          <div className="list-row">
            <span>Camera access</span>
            <span className={`badge ${policy.camera_enabled ? "ok" : "warn"}`}>
              {policy.camera_enabled ? "enabled" : "disabled"}
            </span>
          </div>
          <div className="list-row">
            <span>Screen access</span>
            <span className={`badge ${policy.screen_access === "disabled" ? "ok" : "warn"}`}>
              {policy.screen_access === "disabled" ? "disabled" : "manual only"}
            </span>
          </div>
          <div className="list-row">
            <span>Expression memory</span>
            <span className={`badge ${policy.retain_expressions ? "warn" : "ok"}`}>
              {policy.retain_expressions ? "on" : "off"}
            </span>
          </div>
          <div className="list-row">
            <span>Snapshot memory</span>
            <span className={`badge ${policy.retain_snapshots ? "warn" : "ok"}`}>
              {policy.retain_snapshots ? "on" : "off"}
            </span>
          </div>
          <div className="list-row">
            <span>Retention window</span>
            <span className="badge">
              {policy.retention_days === 0 ? "session only" : `${policy.retention_days} days`}
            </span>
          </div>
          {policy.last_updated ? (
            <div className="list-row">
              <span>Last changed</span>
              <span className="badge">
                {new Date(policy.last_updated).toLocaleString([], {
                  month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                })}
              </span>
            </div>
          ) : null}
        </div>

        {status === "saving" ? <p style={{ fontSize: "0.78rem", marginTop: 8 }}>Saving…</p> : null}
        {status === "saved" ? (
          <p style={{ fontSize: "0.78rem", marginTop: 8, color: "var(--color-ok)" }}>Saved.</p>
        ) : null}
        {status === "error" && errorMsg ? (
          <div className="voice-error" style={{ marginTop: 8 }}>{errorMsg}</div>
        ) : null}
      </div>
    </div>
  );
}
