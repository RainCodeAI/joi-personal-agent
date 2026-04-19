import { fetchRecentMemories } from "@/lib/api";

import { MemorySearchPanel } from "./search-panel";

export const dynamic = "force-dynamic";

export default async function MemoryPage() {
  const recent = await fetchRecentMemories().catch(() => ({ memories: [] }));

  return (
    <>
      <header className="page-header">
        <span className="page-breadcrumb-label">Memory</span>
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
