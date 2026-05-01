"use client";

import { useState } from "react";
import {
  fetchSynthesisRecords,
  fetchUserModelPromptPreview,
  postUserModelCorrection,
  runUserModelSynthesis,
} from "@/lib/api";
import {
  SynthesisCandidate,
  SynthesisMethod,
  SynthesisRecord,
  SynthesisResponse,
  UserModelCorrectionRequest,
  UserModelItem,
  UserModelResponse,
  UserModelSection,
} from "@/lib/types";

type Props = {
  initialUserModel: UserModelResponse;
  initialPromptBlock: string;
};

function confidenceTone(c: number): string {
  if (c >= 0.85) return "ok";
  if (c >= 0.6) return "warn";
  return "";
}

function lifecycleTone(l: UserModelItem["lifecycle"]): string {
  if (l === "pinned") return "ok";
  if (l === "fresh") return "warn";
  return "";
}

function flagTone(candidate: Pick<SynthesisCandidate, "blocked_by_correction" | "duplicate_of_existing">): string {
  if (candidate.blocked_by_correction) return "warn";
  if (candidate.duplicate_of_existing) return "warn";
  return "ok";
}

function statusTone(status: SynthesisRecord["status"]): string {
  if (status === "skipped") return "warn";
  if (status === "written") return "ok";
  return "";
}

function formatTime(value: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function ItemRow({
  item,
  sectionKey,
  onCorrection,
  busy,
}: {
  item: UserModelItem;
  sectionKey: string;
  onCorrection: (req: UserModelCorrectionRequest) => Promise<void>;
  busy: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [editLabel, setEditLabel] = useState(item.label);
  const [editValue, setEditValue] = useState(item.value);

  function startEdit() {
    setEditLabel(item.label);
    setEditValue(item.value);
    setEditing(true);
  }

  async function submitEdit() {
    await onCorrection({ section_key: sectionKey, action: "edit", item_id: item.id, label: editLabel, value: editValue });
    setEditing(false);
  }

  return (
    <div className="list-row" style={{ flexDirection: "column", gap: 10, alignItems: "stretch" }}>
      {editing ? (
        <div style={{ display: "grid", gap: 8 }}>
          <div className="field">
            <label>Label</label>
            <input
              className="input"
              value={editLabel}
              onChange={(e) => setEditLabel(e.target.value)}
              style={{ fontSize: "0.9rem" }}
            />
          </div>
          <div className="field">
            <label>Value</label>
            <textarea
              className="textarea"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              rows={3}
              style={{ fontSize: "0.9rem", minHeight: 72 }}
            />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="button primary" onClick={submitEdit} disabled={busy} style={{ padding: "8px 16px", fontSize: "0.82rem" }}>
              Save
            </button>
            <button className="button ghost" onClick={() => setEditing(false)} disabled={busy} style={{ padding: "8px 16px", fontSize: "0.82rem" }}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
            <div style={{ minWidth: 0 }}>
              <strong style={{ display: "block", marginBottom: 4 }}>{item.label}</strong>
              <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.88rem", lineHeight: 1.5 }}>
                {item.value}
              </p>
            </div>
            <div style={{ display: "flex", gap: 6, flexShrink: 0, flexWrap: "wrap", justifyContent: "flex-end" }}>
              <span className={`badge ${confidenceTone(item.confidence)}`} style={{ padding: "4px 10px", fontSize: "0.72rem" }}>
                {Math.round(item.confidence * 100)}%
              </span>
              <span className={`badge ${lifecycleTone(item.lifecycle)}`} style={{ padding: "4px 10px", fontSize: "0.72rem" }}>
                {item.lifecycle}
              </span>
              {item.user_confirmed && (
                <span className="badge ok" style={{ padding: "4px 10px", fontSize: "0.72rem" }}>confirmed</span>
              )}
              {item.hidden && (
                <span className="badge warn" style={{ padding: "4px 10px", fontSize: "0.72rem" }}>hidden</span>
              )}
            </div>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {!item.user_confirmed && (
              <button
                className="button ghost"
                style={{ padding: "5px 12px", fontSize: "0.78rem" }}
                disabled={busy}
                onClick={() => onCorrection({ section_key: sectionKey, action: "confirm", item_id: item.id })}
              >
                Confirm
              </button>
            )}
            <button
              className="button ghost"
              style={{ padding: "5px 12px", fontSize: "0.78rem" }}
              disabled={busy}
              onClick={startEdit}
            >
              Edit
            </button>
            {!item.hidden && (
              <button
                className="button ghost"
                style={{ padding: "5px 12px", fontSize: "0.78rem" }}
                disabled={busy}
                onClick={() => onCorrection({ section_key: sectionKey, action: "hide", item_id: item.id })}
              >
                Hide
              </button>
            )}
            <button
              className="button ghost"
              style={{ padding: "5px 12px", fontSize: "0.78rem", color: "var(--rose)" }}
              disabled={busy}
              onClick={() => onCorrection({ section_key: sectionKey, action: "delete", item_id: item.id })}
            >
              Delete
            </button>
            <span style={{ marginLeft: "auto", color: "var(--muted)", fontSize: "0.72rem", alignSelf: "center" }}>
              {item.source_summary}
            </span>
          </div>
        </>
      )}
    </div>
  );
}

function CandidateRow({ candidate }: { candidate: SynthesisCandidate }) {
  const flag = candidate.blocked_by_correction
    ? "blocked"
    : candidate.duplicate_of_existing
      ? "duplicate"
      : "candidate";

  return (
    <div className="list-row" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start" }}>
        <div style={{ minWidth: 0 }}>
          <strong style={{ display: "block", marginBottom: 4 }}>{candidate.label}</strong>
          <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.82rem", lineHeight: 1.45 }}>
            {candidate.value}
          </p>
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end", flexShrink: 0 }}>
          <span className="badge" style={{ padding: "4px 10px", fontSize: "0.72rem" }}>
            {candidate.inference_method}
          </span>
          <span className={`badge ${confidenceTone(candidate.confidence)}`} style={{ padding: "4px 10px", fontSize: "0.72rem" }}>
            {Math.round(candidate.confidence * 100)}%
          </span>
          <span className={`badge ${flagTone(candidate)}`} style={{ padding: "4px 10px", fontSize: "0.72rem" }}>
            {flag}
          </span>
        </div>
      </div>
      <div style={{ display: "grid", gap: 4, color: "var(--muted)", fontSize: "0.76rem", lineHeight: 1.45 }}>
        <span>{candidate.section_key.replace(/_/g, " ")} · message {candidate.source_message_index}</span>
        {candidate.source_excerpt && <span style={{ wordBreak: "break-word" }}>{candidate.source_excerpt}</span>}
      </div>
    </div>
  );
}

function RecordRow({ record }: { record: SynthesisRecord }) {
  return (
    <div className="list-row" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start" }}>
        <div style={{ minWidth: 0 }}>
          <strong style={{ display: "block", marginBottom: 4 }}>{record.label}</strong>
          <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.78rem", lineHeight: 1.45, wordBreak: "break-word" }}>
            {record.evidence_excerpt || record.candidate_id}
          </p>
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end", flexShrink: 0 }}>
          <span className="badge" style={{ padding: "4px 10px", fontSize: "0.72rem" }}>
            {record.method}
          </span>
          <span className={`badge ${statusTone(record.status)}`} style={{ padding: "4px 10px", fontSize: "0.72rem" }}>
            {record.status}
          </span>
        </div>
      </div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", color: "var(--muted)", fontSize: "0.72rem" }}>
        <span>{record.section_key.replace(/_/g, " ")}</span>
        <span>{Math.round(record.confidence * 100)}%</span>
        {record.skipped_reason && <span>{record.skipped_reason}</span>}
        <span>{formatTime(record.created_at)}</span>
      </div>
    </div>
  );
}

function SynthesisDiagnostics() {
  const [sessionId, setSessionId] = useState("");
  const [method, setMethod] = useState<SynthesisMethod>("pattern");
  const [result, setResult] = useState<SynthesisResponse | null>(null);
  const [records, setRecords] = useState<SynthesisRecord[]>([]);
  const [busy, setBusy] = useState(false);
  const [recordsBusy, setRecordsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runSynthesis() {
    const trimmed = sessionId.trim();
    if (!trimmed) {
      setError("Session id is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await runUserModelSynthesis(trimmed, method);
      setResult(response);
      setRecords(response.audit_records);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Synthesis failed");
    } finally {
      setBusy(false);
    }
  }

  async function loadRecords() {
    setRecordsBusy(true);
    setError(null);
    try {
      const response = await fetchSynthesisRecords({
        sessionId: sessionId.trim() || undefined,
        limit: 25,
      });
      setRecords(response.records);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Record load failed");
    } finally {
      setRecordsBusy(false);
    }
  }

  const skipped = result?.candidates.filter((c) => c.blocked_by_correction || c.duplicate_of_existing).length ?? 0;

  return (
    <section className="panel">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "flex-start", flexWrap: "wrap" }}>
        <div>
          <p className="eyebrow" style={{ marginBottom: 4 }}>Synthesis diagnostics</p>
          <h3 style={{ margin: 0 }}>Dry-run extraction</h3>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <span className="badge" style={{ padding: "4px 10px", fontSize: "0.72rem" }}>
            writes off
          </span>
          {result && (
            <span className="badge ok" style={{ padding: "4px 10px", fontSize: "0.72rem" }}>
              {result.candidates.length} candidates
            </span>
          )}
          {result && skipped > 0 && (
            <span className="badge warn" style={{ padding: "4px 10px", fontSize: "0.72rem" }}>
              {skipped} skipped
            </span>
          )}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10, alignItems: "end", marginTop: 16 }}>
        <div className="field">
          <label>Session id</label>
          <input
            className="input"
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            placeholder="session id"
            style={{ fontSize: "0.88rem" }}
          />
        </div>
        <div className="field">
          <label>Method</label>
          <select
            className="input"
            value={method}
            onChange={(e) => setMethod(e.target.value as SynthesisMethod)}
            style={{ fontSize: "0.88rem" }}
          >
            <option value="pattern">pattern</option>
            <option value="llm">llm</option>
          </select>
        </div>
        <button className="button primary" onClick={runSynthesis} disabled={busy || !sessionId.trim()} style={{ padding: "10px 16px", fontSize: "0.82rem" }}>
          {busy ? "Running" : "Run"}
        </button>
        <button className="button ghost" onClick={loadRecords} disabled={recordsBusy} style={{ padding: "10px 16px", fontSize: "0.82rem" }}>
          {recordsBusy ? "Loading" : "Records"}
        </button>
      </div>

      {error && (
        <div style={{ marginTop: 14, padding: "10px 14px", borderRadius: 10, border: "1px solid rgba(255,123,136,0.35)", background: "rgba(255,123,136,0.08)", color: "var(--rose)", fontSize: "0.82rem" }}>
          {error}
        </div>
      )}

      {result && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 10, marginTop: 16 }}>
          {[
            ["Messages", result.message_count],
            ["Written", result.written_count],
            ["Skipped", result.skipped_count],
            ["Provider", result.provider.selected || "none"],
          ].map(([label, value]) => (
            <div className="status-card" key={String(label)}>
              <span>{label}</span>
              <strong style={{ fontSize: "1rem", wordBreak: "break-word" }}>{value}</strong>
            </div>
          ))}
        </div>
      )}

      {result && result.candidates.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <p className="eyebrow" style={{ marginBottom: 10 }}>Candidates</p>
          <div className="list">
            {result.candidates.map((candidate) => (
              <CandidateRow key={candidate.candidate_id} candidate={candidate} />
            ))}
          </div>
        </div>
      )}

      {result && result.candidates.length === 0 && (
        <p style={{ margin: "16px 0 0", color: "var(--muted)", fontSize: "0.82rem" }}>
          No candidates returned for this dry run.
        </p>
      )}

      {records.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <p className="eyebrow" style={{ marginBottom: 10 }}>Audit records</p>
          <div className="list">
            {records.map((record) => (
              <RecordRow key={record.id} record={record} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function SectionPanel({
  section,
  onCorrection,
  busy,
}: {
  section: UserModelSection;
  onCorrection: (req: UserModelCorrectionRequest) => Promise<void>;
  busy: boolean;
}) {
  const [adding, setAdding] = useState(false);
  const [addLabel, setAddLabel] = useState("");
  const [addValue, setAddValue] = useState("");

  async function submitAdd() {
    if (!addLabel.trim() && !addValue.trim()) return;
    await onCorrection({ section_key: section.key, action: "add", label: addLabel.trim() || addValue.trim(), value: addValue.trim() || addLabel.trim() });
    setAdding(false);
    setAddLabel("");
    setAddValue("");
  }

  const visibleItems = section.items.filter((i) => !i.hidden);
  const hiddenCount = section.items.length - visibleItems.length;

  return (
    <section className="panel">
      <p className="eyebrow">{section.key.replace(/_/g, " ")}</p>
      <h3 style={{ marginBottom: 6 }}>{section.title}</h3>
      <p style={{ margin: "0 0 16px", color: "var(--muted)", fontSize: "0.82rem", lineHeight: 1.5 }}>
        {section.description}
      </p>

      {visibleItems.length > 0 && (
        <div className="list" style={{ marginBottom: 14 }}>
          {visibleItems.map((item) => (
            <ItemRow
              key={item.id}
              item={item}
              sectionKey={section.key}
              onCorrection={onCorrection}
              busy={busy}
            />
          ))}
        </div>
      )}

      {hiddenCount > 0 && (
        <p style={{ margin: "0 0 12px", color: "var(--muted)", fontSize: "0.78rem" }}>
          {hiddenCount} item{hiddenCount > 1 ? "s" : ""} hidden
        </p>
      )}

      {visibleItems.length === 0 && hiddenCount === 0 && (
        <p style={{ margin: "0 0 12px", color: "var(--muted)", fontSize: "0.82rem", opacity: 0.6 }}>
          No items yet.
        </p>
      )}

      {adding ? (
        <div style={{ display: "grid", gap: 8, borderTop: "1px solid var(--line)", paddingTop: 14 }}>
          <div className="field">
            <label>Label</label>
            <input
              className="input"
              placeholder="e.g. Current focus"
              value={addLabel}
              onChange={(e) => setAddLabel(e.target.value)}
              style={{ fontSize: "0.9rem" }}
            />
          </div>
          <div className="field">
            <label>Value</label>
            <textarea
              className="textarea"
              placeholder="e.g. Building the Joi personal agent"
              value={addValue}
              onChange={(e) => setAddValue(e.target.value)}
              rows={2}
              style={{ fontSize: "0.9rem", minHeight: 60 }}
            />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="button primary" onClick={submitAdd} disabled={busy || (!addLabel.trim() && !addValue.trim())} style={{ padding: "8px 16px", fontSize: "0.82rem" }}>
              Add
            </button>
            <button className="button ghost" onClick={() => { setAdding(false); setAddLabel(""); setAddValue(""); }} disabled={busy} style={{ padding: "8px 16px", fontSize: "0.82rem" }}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          className="button ghost"
          style={{ padding: "6px 14px", fontSize: "0.78rem" }}
          disabled={busy}
          onClick={() => setAdding(true)}
        >
          + Add item
        </button>
      )}
    </section>
  );
}

export function UserModelPanel({ initialUserModel, initialPromptBlock }: Props) {
  const [userModel, setUserModel] = useState<UserModelResponse>(initialUserModel);
  const [promptBlock, setPromptBlock] = useState(initialPromptBlock);
  const [promptExpanded, setPromptExpanded] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const totalItems = userModel.sections.reduce((n, s) => n + s.items.length, 0);
  const confirmedItems = userModel.sections.reduce(
    (n, s) => n + s.items.filter((i) => i.user_confirmed).length,
    0,
  );
  const hiddenItems = userModel.sections.reduce(
    (n, s) => n + s.items.filter((i) => i.hidden).length,
    0,
  );

  async function applyCorrection(payload: UserModelCorrectionRequest) {
    setBusy(true);
    setError(null);
    try {
      const res = await postUserModelCorrection(payload);
      setUserModel(res.user_model);
      const preview = await fetchUserModelPromptPreview();
      setPromptBlock(preview.prompt_block);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Correction failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header className="page-header">
        <div>
          <p className="eyebrow">Phase 9</p>
          <h1 className="page-title">User Model</h1>
          <p className="page-copy">
            What Joi knows about you. Confirm, correct, or add items to shape the context she carries into every conversation.
          </p>
        </div>
        <div className="status-strip">
          <div className="status-card">
            <span>Items</span>
            <strong>{totalItems}</strong>
          </div>
          <div className="status-card">
            <span>Confirmed</span>
            <strong>{confirmedItems}</strong>
          </div>
          <div className="status-card">
            <span>Hidden</span>
            <strong>{hiddenItems}</strong>
          </div>
          <div className="status-card">
            <span>Status</span>
            <strong style={{ textTransform: "capitalize" }}>{userModel.status.replace("_", " ")}</strong>
          </div>
        </div>
      </header>

      <div className="page-body" style={{ display: "grid", gap: 18 }}>
        {error && (
          <div style={{ padding: "12px 18px", borderRadius: 14, border: "1px solid rgba(255,123,136,0.35)", background: "rgba(255,123,136,0.08)", color: "var(--rose)", fontSize: "0.88rem" }}>
            {error}
          </div>
        )}

        <SynthesisDiagnostics />

        <section className="panel">
          <div
            style={{ display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer" }}
            onClick={() => setPromptExpanded((p) => !p)}
          >
            <div>
              <p className="eyebrow" style={{ marginBottom: 4 }}>Prompt context</p>
              <h3 style={{ margin: 0 }}>[User Model] injection preview</h3>
            </div>
            <span style={{ color: "var(--muted)", fontSize: "0.8rem" }}>{promptExpanded ? "hide" : "show"}</span>
          </div>
          {promptExpanded && (
            <div style={{ marginTop: 16 }}>
              {promptBlock ? (
                <pre style={{ margin: 0, padding: "14px 16px", borderRadius: 12, background: "rgba(0,0,0,0.32)", border: "1px solid var(--line)", color: "var(--muted)", fontSize: "0.82rem", lineHeight: 1.65, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                  {promptBlock}
                </pre>
              ) : (
                <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.82rem", opacity: 0.6 }}>
                  No prompt context yet. Confirm items or add new ones above to populate the [User Model] block.
                </p>
              )}
            </div>
          )}
        </section>

        <div className="grid two">
          {userModel.sections.map((section) => (
            <SectionPanel
              key={section.key}
              section={section}
              onCorrection={applyCorrection}
              busy={busy}
            />
          ))}
        </div>

        <section className="panel" style={{ opacity: 0.7 }}>
          <p className="eyebrow">Policy</p>
          <h3>Inference boundaries</h3>
          <div className="list">
            {[
              ["Inference enabled", userModel.policy.inference_enabled],
              ["Corrections supported", userModel.policy.correction_supported],
              ["Initiative surfacing", userModel.policy.initiative_surface_enabled],
              ["Stores raw files", userModel.policy.stores_raw_files],
              ["Stores presence streams", userModel.policy.stores_raw_presence_streams],
            ].map(([label, value]) => (
              <div className="list-row" key={String(label)}>
                <strong style={{ margin: 0 }}>{label}</strong>
                <span className={`badge ${value ? "ok" : ""}`} style={{ padding: "4px 10px", fontSize: "0.72rem" }}>
                  {value ? "on" : "off"}
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
