import { fetchDiagnostics } from "@/lib/api";
import { DiagnosticsResponse, ReadinessState } from "@/lib/types";

export const dynamic = "force-dynamic";

const FALLBACK_DIAGNOSTICS: DiagnosticsResponse = {
  status: "error",
  readiness: {},
  providers: {},
  storage: {},
  media: {},
  realtime: {},
  hardware_bridge: {},
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

export default async function DiagnosticsPage() {
  const diagnostics = await fetchDiagnostics().catch(() => FALLBACK_DIAGNOSTICS);

  const readinessEntries = Object.entries(diagnostics.readiness);
  const providerEntries = Object.entries(diagnostics.providers);
  const storageEntries = Object.entries(diagnostics.storage);
  const mediaEntries = Object.entries(diagnostics.media);
  const realtimeEntries = Object.entries(diagnostics.realtime);
  const hardwareBridgeEntries = Object.entries(diagnostics.hardware_bridge);
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
      </div>
    </>
  );
}
