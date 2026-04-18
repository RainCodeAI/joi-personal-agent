import { fetchRecentMemories } from "@/lib/api";

import { MemorySearchPanel } from "./search-panel";

export const dynamic = "force-dynamic";

export default async function MemoryPage() {
  const recent = await fetchRecentMemories().catch(() => ({ memories: [] }));

  return (
    <>
      <header className="page-header">
        <div>
          <p className="eyebrow">Phase 2.1</p>
          <h1 className="page-title">Memory Surface</h1>
          <p className="page-copy">
            Vector and graph-backed recall now routes through FastAPI rather than a Streamlit page.
          </p>
        </div>
        <div className="status-strip">
          <div className="status-card">
            <span>Recent Items</span>
            <strong>{recent.memories.length}</strong>
          </div>
          <div className="status-card">
            <span>Query Mode</span>
            <strong>Graph</strong>
          </div>
          <div className="status-card">
            <span>Boundary</span>
            <strong>API First</strong>
          </div>
        </div>
      </header>

      <div className="page-body grid two">
        <MemorySearchPanel />

        <section className="panel">
          <p className="eyebrow">Recent Recall</p>
          <h3>Latest memories</h3>
          <div className="list">
            {recent.memories.length ? (
              recent.memories.map((memory) => (
                <div className="list-row" key={memory.id}>
                  <div>
                    <strong>{memory.type}</strong>
                    <p>{memory.text}</p>
                  </div>
                  <span className="badge">{memory.memory_type}</span>
                </div>
              ))
            ) : (
              <div className="empty-state">No recent memories available yet.</div>
            )}
          </div>
        </section>
      </div>
    </>
  );
}
