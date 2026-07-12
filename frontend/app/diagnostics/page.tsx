import { fetchDiagnostics, listInitiativeEmissions } from "@/lib/api";
import { DiagnosticsResponse, InitiativeDiagnostics, InitiativeEmission, ReadinessState } from "@/lib/types";
import { InitiativeEmissionsPanel } from "@/components/initiative-emissions-panel";

export const dynamic = "force-dynamic";

const FALLBACK_DIAGNOSTICS: DiagnosticsResponse = {
  status: "error",
  readiness: {},
  providers: {},
  storage: {},
  media: {},
  realtime: {},
  hardware_bridge: {},
  initiative: undefined,
  context_events: {},
};

function readinessTone(state?: ReadinessState["state"]) {
  if (state === "ready") return "ok";
  if (state === "degraded") return "warn";
  return "";
}

function readinessLabel(state?: ReadinessState["state"]) {
  if (state === "ready") return "ready";
  if (state === "degraded") return "degraded";
  if (state === "disabled") return "disabled";
  return "unknown";
}

function DetailRows({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="diag-value">-</span>;
  if (typeof value !== "object" || Array.isArray(value)) {
    return <span className="diag-value">{String(value)}</span>;
  }

  const entries = Object.entries(value as Record<string, unknown>);
  if (entries.length === 0) return <span className="diag-value">-</span>;

  return (
    <div className="diag-rows">
      {entries.map(([k, v]) => (
        <div className="diag-row" key={k}>
          <span className="diag-key">{k}</span>
          <span className="diag-value">
            {v !== null && typeof v === "object" ? JSON.stringify(v) : String(v)}
          </span>
        </div>
      ))}
    </div>
  );
}

function fmt(ts: string | null | undefined): string {
  if (!ts) return "never";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function InitiativePanel({ initiative }: { initiative: InitiativeDiagnostics | undefined }) {
  if (!initiative) {
    return (
      <section className="panel">
        <p className="eyebrow">Initiative</p>
        <h3>Presence triggers</h3>
        <p style={{ opacity: 0.5, fontSize: 13 }}>No data</p>
      </section>
    );
  }

  const { scheduler } = initiative;
  const generalJob = scheduler?.jobs?.find((j) => j.id === "initiative_general_tick");
  const memoryJob = scheduler?.jobs?.find((j) => j.id === "initiative_memory_tick");
  const contextJob = scheduler?.jobs?.find((j) => j.id === "context_commentary_tick");

  return (
    <section className="panel">
      <p className="eyebrow">Initiative</p>
      <h3>Presence triggers</h3>
      <div className="list">
        <div className="list-row">
          <div><strong>Status</strong></div>
          <span className={`badge ${initiative.enabled ? "ok" : ""}`}>
            {initiative.enabled ? "enabled" : "disabled"}
          </span>
        </div>
        <div className="list-row">
          <div>
            <strong>Daily usage</strong>
            <p>{initiative.daily_count} of {initiative.daily_limit} used - {initiative.remaining_today} remaining</p>
          </div>
        </div>
        <div className="list-row">
          <div>
            <strong>Local policy time</strong>
            <p>{initiative.timezone}</p>
          </div>
        </div>
        <div className="list-row">
          <div>
            <strong>Greeting window</strong>
            <p>{initiative.daily_greeting.start}-{initiative.daily_greeting.end}</p>
          </div>
          <span className={`badge ${initiative.daily_greeting.active ? "ok" : ""}`}>
            {initiative.daily_greeting.active ? "active" : "outside"}
          </span>
        </div>
        <div className="list-row">
          <div>
            <strong>Quiet hours</strong>
            <p>{initiative.quiet_hours.start}-{initiative.quiet_hours.end}</p>
          </div>
          <span className={`badge ${initiative.quiet_hours.active ? "warn" : ""}`}>
            {initiative.quiet_hours.active ? "active" : "clear"}
          </span>
        </div>
        <div className="list-row">
          <div>
            <strong>Late-night window</strong>
            <p>{initiative.late_night.start}-{initiative.late_night.end}</p>
          </div>
          <span className={`badge ${initiative.late_night.active ? "ok" : ""}`}>
            {initiative.late_night.active ? "active" : "outside"}
          </span>
        </div>
        <div className="list-row">
          <div>
            <strong>Gates</strong>
            <p>
              Focus: {initiative.focus_mode ? "on" : "off"} * DND: {initiative.do_not_disturb ? "on" : "off"}
            </p>
          </div>
        </div>
        <div className="list-row">
          <div>
            <strong>Enabled types</strong>
            <p>{initiative.allowed_types.length > 0 ? initiative.allowed_types.join(", ") : "none"}</p>
          </div>
        </div>
        <div className="list-row">
          <div>
            <strong>Last emitted</strong>
            <p>{fmt(initiative.last_emitted_at)}</p>
          </div>
        </div>
        {initiative.last_suppressed && (
          <div className="list-row">
            <div>
              <strong>Last suppressed</strong>
              <p>{initiative.last_suppressed.type} - {initiative.last_suppressed.reason}</p>
              <p style={{ opacity: 0.55, fontSize: 12 }}>{fmt(initiative.last_suppressed.checked_at)}</p>
            </div>
          </div>
        )}
        <div className="list-row">
          <div>
            <strong>Scheduler</strong>
            <p>
              General: {generalJob ? fmt(generalJob.next_run_time) : "-"}
            </p>
            <p>
              Memory: {memoryJob ? fmt(memoryJob.next_run_time) : "-"}
            </p>
            <p>
              Context: {contextJob ? fmt(contextJob.next_run_time) : "-"}
            </p>
          </div>
          <span className={`badge ${scheduler?.running ? "ok" : ""}`}>
            {scheduler?.running ? "running" : "stopped"}
          </span>
        </div>
      </div>
    </section>
  );
}

export default async function DiagnosticsPage() {
  const diagnostics = await fetchDiagnostics().catch(() => FALLBACK_DIAGNOSTICS);
  const emissions: InitiativeEmission[] = await listInitiativeEmissions()
    .then((r) => r.emissions)
    .catch(() => []);

  const readinessEntries = Object.entries(diagnostics.readiness);
  const providerEntries = Object.entries(diagnostics.providers);
  const storageEntries = Object.entries(diagnostics.storage);
  const mediaEntries = Object.entries(diagnostics.media);
  const realtimeEntries = Object.entries(diagnostics.realtime);
  const hardwareBridgeEntries = Object.entries(diagnostics.hardware_bridge);
  const contextEventEntries = Object.entries(diagnostics.context_events ?? {});
  const readyCount = readinessEntries.filter(([, entry]) => entry.state === "ready").length;
  const degradedCount = readinessEntries.filter(([, entry]) => entry.state === "degraded").length;
  const disabledCount = readinessEntries.filter(([, entry]) => entry.state === "disabled").length;

  return (
    <>
      <header className="page-header">
        <span className="page-breadcrumb-label">Diagnostics</span>
        <div className="status-strip">
          <div className="status-card">
            <span>Status</span>
            <strong>{diagnostics.status}</strong>
          </div>
          <div className="status-card">
            <span>Ready</span>
            <strong>{readyCount}</strong>
          </div>
          <div className="status-card">
            <span>Degraded</span>
            <strong>{degradedCount}</strong>
          </div>
          <div className="status-card">
            <span>Disabled</span>
            <strong>{disabledCount}</strong>
          </div>
        </div>
      </header>

      <div className="page-body grid three">
        <section className="panel">
          <p className="eyebrow">Readiness</p>
          <h3>Runtime gates</h3>
          <div className="list">
            {readinessEntries.map(([name, details]) => (
              <div className="list-row" key={name}>
                <div>
                  <strong>{name}</strong>
                  <p>{details.summary}</p>
                </div>
                <span className={`badge ${readinessTone(details.state)}`}>
                  {readinessLabel(details.state)}
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <p className="eyebrow">Providers</p>
          <h3>Availability</h3>
          <div className="list">
            {providerEntries.map(([name, details]) => (
              <div className="list-row" key={name}>
                <div>
                  <strong>{name}</strong>
                  <DetailRows value={details} />
                </div>
                <span
                  className={`badge ${Boolean((details as Record<string, unknown>)["available"]) ? "ok" : "warn"}`}
                >
                  {Boolean((details as Record<string, unknown>)["available"]) ? "ready" : "check"}
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <p className="eyebrow">Storage</p>
          <h3>Mode and targets</h3>
          <div className="list">
            {storageEntries.map(([name, value]) => (
              <div className="list-row" key={name}>
                <div>
                  <strong>{name}</strong>
                  <DetailRows value={value} />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <p className="eyebrow">Media</p>
          <h3>Capabilities</h3>
          <div className="list">
            {mediaEntries.map(([name, details]) => (
              <div className="list-row" key={name}>
                <div>
                  <strong>{name}</strong>
                  <DetailRows value={details} />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <p className="eyebrow">Realtime</p>
          <h3>Transport and sessions</h3>
          <div className="list">
            {realtimeEntries.map(([name, value]) => (
              <div className="list-row" key={name}>
                <div>
                  <strong>{name}</strong>
                  <DetailRows value={value} />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <p className="eyebrow">Hardware bridge</p>
          <h3>Ambient link state</h3>
          <div className="list">
            {hardwareBridgeEntries.map(([name, value]) => (
              <div className="list-row" key={name}>
                <div>
                  <strong>{name}</strong>
                  <DetailRows value={value} />
                </div>
              </div>
            ))}
          </div>
        </section>

        <InitiativePanel initiative={diagnostics.initiative} />

        <InitiativeEmissionsPanel initialEmissions={emissions} />

        <section className="panel">
          <p className="eyebrow">Context gate</p>
          <h3>Observation buffer and commentary policy</h3>
          <div className="list">
            {contextEventEntries.length > 0 ? (
              contextEventEntries.map(([name, value]) => (
                <div className="list-row" key={name}>
                  <div>
                    <strong>{name}</strong>
                    <DetailRows value={value} />
                  </div>
                </div>
              ))
            ) : (
              <p style={{ opacity: 0.5, fontSize: 13 }}>No context diagnostics available</p>
            )}
          </div>
        </section>
      </div>
    </>
  );
}

