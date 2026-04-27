"use client";

import { useState } from "react";
import { fetchUserModelPromptPreview, postUserModelCorrection } from "@/lib/api";
import {
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
