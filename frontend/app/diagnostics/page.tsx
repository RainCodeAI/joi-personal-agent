import { fetchDiagnostics } from "@/lib/api";

export const dynamic = "force-dynamic";

function readBoolean(value: unknown) {
  return typeof value === "boolean" ? value : false;
}

function DetailRows({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="diag-value">—</span>;
  if (typeof value !== "object" || Array.isArray(value))
    return <span className="diag-value">{String(value)}</span>;
  const entries = Object.entries(value as Record<string, unknown>);
  if (entries.length === 0) return <span className="diag-value">—</span>;
  return (
    <div className="diag-rows">
      {entries.map(([k, v]) => (
        <div className="diag-row" key={k}>
          <span className="diag-key">{k}</span>
          <span className="diag-value">{String(v)}</span>
        </div>
      ))}
    </div>
  );
}

export default async function DiagnosticsPage() {
  const diagnostics = await fetchDiagnostics().catch(() => ({
    status: "error",
    providers: {},
    storage: {},
    media: {},
  }));

  const providerEntries = Object.entries(diagnostics.providers);
  const storageEntries = Object.entries(diagnostics.storage);
  const mediaEntries = Object.entries(diagnostics.media);

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
            <span>Providers</span>
            <strong>{providerEntries.length}</strong>
          </div>
          <div className="status-card">
            <span>Media</span>
            <strong>{mediaEntries.length}</strong>
          </div>
        </div>
      </header>

      <div className="page-body grid three">
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
                <span className={`badge ${readBoolean((details as Record<string, unknown>)["available"]) ? "ok" : "warn"}`}>
                  {readBoolean((details as Record<string, unknown>)["available"]) ? "up" : "check"}
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
      </div>
    </>
  );
}
