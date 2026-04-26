"use client";

import { FormEvent, useState } from "react";

import { patchSettings, SettingsShape } from "@/lib/api";

type SettingsFormProps = {
  settings: SettingsShape;
};

const INITIATIVE_TYPES = [
  { id: "daily_greeting", label: "Daily greeting" },
  { id: "return_after_absence", label: "Return after absence" },
  { id: "late_night_checkin", label: "Late-night check-in" },
  { id: "prolonged_silence", label: "Prolonged silence" },
  { id: "memory_followup", label: "Memory follow-up" },
] as const;

function parseAllowedTypes(raw: string): string[] {
  return raw.split(",").map((t) => t.trim()).filter(Boolean);
}

function toggleType(raw: string, type: string): string {
  const current = parseAllowedTypes(raw);
  const next = current.includes(type)
    ? current.filter((t) => t !== type)
    : [...current, type];
  return next.join(",");
}

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
        <div className="field">
          <label htmlFor="settings-mqtt-host">MQTT Host</label>
          <input
            id="settings-mqtt-host"
            className="input"
            value={form.mqtt_broker_host}
            onChange={(event) => setForm((current) => ({ ...current, mqtt_broker_host: event.target.value }))}
          />
        </div>
        <div className="field">
          <label htmlFor="settings-mqtt-port">MQTT Port</label>
          <input
            id="settings-mqtt-port"
            className="input"
            type="number"
            value={form.mqtt_broker_port}
            onChange={(event) =>
              setForm((current) => ({ ...current, mqtt_broker_port: Number(event.target.value || 0) }))
            }
          />
        </div>
        <div className="field">
          <label htmlFor="settings-mqtt-client">MQTT Client ID</label>
          <input
            id="settings-mqtt-client"
            className="input"
            value={form.mqtt_client_id}
            onChange={(event) => setForm((current) => ({ ...current, mqtt_client_id: event.target.value }))}
          />
        </div>
        <div className="field">
          <label htmlFor="settings-mqtt-topic-prefix">MQTT Topic Prefix</label>
          <input
            id="settings-mqtt-topic-prefix"
            className="input"
            value={form.mqtt_topic_prefix}
            onChange={(event) => setForm((current) => ({ ...current, mqtt_topic_prefix: event.target.value }))}
          />
        </div>
        <div className="field">
          <label htmlFor="settings-mqtt-node-id">MQTT Node ID</label>
          <input
            id="settings-mqtt-node-id"
            className="input"
            value={form.mqtt_node_id}
            onChange={(event) => setForm((current) => ({ ...current, mqtt_node_id: event.target.value }))}
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
        <button
          className="button secondary"
          type="button"
          onClick={() =>
            setForm((current) => ({
              ...current,
              enable_hardware_nodes: !current.enable_hardware_nodes,
            }))
          }
        >
          Hardware bridge: {form.enable_hardware_nodes ? "on" : "off"}
        </button>
      </div>

      <hr style={{ margin: "24px 0", opacity: 0.15 }} />
      <p className="eyebrow">Initiative</p>
      <h3>Presence triggers</h3>

      <div className="field-grid">
        <div className="field">
          <label htmlFor="initiative-daily-limit">Daily limit</label>
          <select
            id="initiative-daily-limit"
            className="select"
            value={form.initiative_daily_limit}
            onChange={(e) =>
              setForm((c) => ({ ...c, initiative_daily_limit: Number(e.target.value) }))
            }
          >
            {[0, 1, 2, 3].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="initiative-timezone">Timezone</label>
          <input
            id="initiative-timezone"
            className="input"
            placeholder="America/Toronto"
            value={form.initiative_timezone}
            onChange={(e) =>
              setForm((c) => ({ ...c, initiative_timezone: e.target.value }))
            }
          />
        </div>
        <div className="field">
          <label htmlFor="initiative-greeting-start">Greeting start</label>
          <input
            id="initiative-greeting-start"
            className="input"
            placeholder="HH:MM"
            value={form.initiative_daily_greeting_start}
            onChange={(e) =>
              setForm((c) => ({ ...c, initiative_daily_greeting_start: e.target.value }))
            }
          />
        </div>
        <div className="field">
          <label htmlFor="initiative-greeting-end">Greeting end</label>
          <input
            id="initiative-greeting-end"
            className="input"
            placeholder="HH:MM"
            value={form.initiative_daily_greeting_end}
            onChange={(e) =>
              setForm((c) => ({ ...c, initiative_daily_greeting_end: e.target.value }))
            }
          />
        </div>
        <div className="field">
          <label htmlFor="initiative-silence-threshold">Silence threshold (min)</label>
          <input
            id="initiative-silence-threshold"
            className="input"
            type="number"
            min={15}
            max={480}
            value={form.initiative_silence_threshold_minutes}
            onChange={(e) =>
              setForm((c) => ({
                ...c,
                initiative_silence_threshold_minutes: Number(e.target.value || 90),
              }))
            }
          />
        </div>
        <div className="field">
          <label htmlFor="initiative-quiet-start">Quiet hours start</label>
          <input
            id="initiative-quiet-start"
            className="input"
            placeholder="HH:MM"
            value={form.initiative_quiet_hours_start}
            onChange={(e) =>
              setForm((c) => ({ ...c, initiative_quiet_hours_start: e.target.value }))
            }
          />
        </div>
        <div className="field">
          <label htmlFor="initiative-quiet-end">Quiet hours end</label>
          <input
            id="initiative-quiet-end"
            className="input"
            placeholder="HH:MM"
            value={form.initiative_quiet_hours_end}
            onChange={(e) =>
              setForm((c) => ({ ...c, initiative_quiet_hours_end: e.target.value }))
            }
          />
        </div>
        <div className="field">
          <label htmlFor="initiative-late-night-start">Late-night start</label>
          <input
            id="initiative-late-night-start"
            className="input"
            placeholder="HH:MM"
            value={form.initiative_late_night_start}
            onChange={(e) =>
              setForm((c) => ({ ...c, initiative_late_night_start: e.target.value }))
            }
          />
        </div>
        <div className="field">
          <label htmlFor="initiative-late-night-end">Late-night end</label>
          <input
            id="initiative-late-night-end"
            className="input"
            placeholder="HH:MM"
            value={form.initiative_late_night_end}
            onChange={(e) =>
              setForm((c) => ({ ...c, initiative_late_night_end: e.target.value }))
            }
          />
        </div>
      </div>

      <div className="button-row" style={{ flexWrap: "wrap" }}>
        <button
          className="button secondary"
          type="button"
          onClick={() =>
            setForm((c) => ({ ...c, initiative_enabled: !c.initiative_enabled }))
          }
        >
          Initiatives: {form.initiative_enabled ? "on" : "off"}
        </button>
        <button
          className="button secondary"
          type="button"
          onClick={() =>
            setForm((c) => ({ ...c, initiative_focus_mode: !c.initiative_focus_mode }))
          }
        >
          Focus mode: {form.initiative_focus_mode ? "on" : "off"}
        </button>
        <button
          className="button secondary"
          type="button"
          onClick={() =>
            setForm((c) => ({
              ...c,
              initiative_do_not_disturb: !c.initiative_do_not_disturb,
            }))
          }
        >
          Do not disturb: {form.initiative_do_not_disturb ? "on" : "off"}
        </button>
      </div>

      <div className="button-row" style={{ flexWrap: "wrap" }}>
        {INITIATIVE_TYPES.map(({ id, label }) => {
          const enabled = parseAllowedTypes(form.initiative_allowed_types).includes(id);
          return (
            <button
              key={id}
              className={`button ${enabled ? "secondary" : "secondary"}`}
              type="button"
              style={{ opacity: enabled ? 1 : 0.45 }}
              onClick={() =>
                setForm((c) => ({
                  ...c,
                  initiative_allowed_types: toggleType(c.initiative_allowed_types, id),
                }))
              }
            >
              {label}: {enabled ? "on" : "off"}
            </button>
          );
        })}
      </div>

      <div className="button-row">
        <button className="button primary" type="submit">
          Save settings
        </button>
        <span className="badge">{status}</span>
      </div>
    </form>
  );
}
