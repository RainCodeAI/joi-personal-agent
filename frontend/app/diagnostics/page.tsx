import { fetchDiagnostics } from "@/lib/api";

export const dynamic = "force-dynamic";

function readBoolean(value: unknown) {
  return typeof value === "boolean" ? value : false;
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
        <div>
          <p className="eyebrow">Phase 2.1</p>
          <h1 className="page-title">Diagnostics</h1>
          <p className="page-copy">
            Runtime truth panel for providers, storage mode, and media capability status.
          </p>
        </div>

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
                  <p>{JSON.stringify(details)}</p>
                </div>
                <span className={`badge ${readBoolean(details["available"]) ? "ok" : "warn"}`}>
                  {readBoolean(details["available"]) ? "up" : "check"}
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
                  <p>{String(value)}</p>
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
                  <p>{JSON.stringify(details)}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
