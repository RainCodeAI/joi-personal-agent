"use client";

import { FormEvent, useState } from "react";

import { patchSettings } from "@/lib/api";

type SettingsFormProps = {
  settings: {
    airgap: boolean;
    autonomy_level: string;
    enable_proactive_messaging: boolean;
    model_chat: string;
    model_embed: string;
    router_timeout: number;
    gguf_n_ctx: number;
    gguf_n_gpu_layers: number;
  };
};

export function SettingsForm({ settings }: SettingsFormProps) {
  const [form, setForm] = useState(settings);
  const [status, setStatus] = useState("Ready");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("Saving settings");
    try {
      await patchSettings(form);
      setStatus("Settings updated");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to save settings");
    }
  }

  return (
    <form className="panel" onSubmit={onSubmit}>
      <p className="eyebrow">Runtime Controls</p>
      <h3>Settings patch</h3>
      <div className="field-grid">
        <div className="field">
          <label htmlFor="settings-autonomy">Autonomy</label>
          <select
            id="settings-autonomy"
            className="select"
            value={form.autonomy_level}
            onChange={(event) => setForm((current) => ({ ...current, autonomy_level: event.target.value }))}
          >
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="settings-timeout">Router Timeout</label>
          <input
            id="settings-timeout"
            className="input"
            type="number"
            value={form.router_timeout}
            onChange={(event) =>
              setForm((current) => ({ ...current, router_timeout: Number(event.target.value || 0) }))
            }
          />
        </div>
        <div className="field">
          <label htmlFor="settings-model-chat">Chat Model</label>
          <input
            id="settings-model-chat"
            className="input"
            value={form.model_chat}
            onChange={(event) => setForm((current) => ({ ...current, model_chat: event.target.value }))}
          />
        </div>
        <div className="field">
          <label htmlFor="settings-model-embed">Embed Model</label>
          <input
            id="settings-model-embed"
            className="input"
            value={form.model_embed}
            onChange={(event) => setForm((current) => ({ ...current, model_embed: event.target.value }))}
          />
        </div>
      </div>

      <div className="button-row">
        <button
          className="button secondary"
          type="button"
          onClick={() => setForm((current) => ({ ...current, airgap: !current.airgap }))}
        >
          Airgap: {form.airgap ? "on" : "off"}
        </button>
        <button
          className="button secondary"
          type="button"
          onClick={() =>
            setForm((current) => ({
              ...current,
              enable_proactive_messaging: !current.enable_proactive_messaging,
            }))
          }
        >
          Proactive: {form.enable_proactive_messaging ? "on" : "off"}
        </button>
        <button className="button primary" type="submit">
          Save settings
        </button>
        <span className="badge">{status}</span>
      </div>
    </form>
  );
}
