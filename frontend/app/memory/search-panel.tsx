"use client";

import { FormEvent, useState } from "react";

import { searchMemories } from "@/lib/api";
import { MemorySearchItem } from "@/lib/types";

export function MemorySearchPanel() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("Ready");
  const [results, setResults] = useState<MemorySearchItem[]>([]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim()) {
      return;
    }

    setStatus("Searching memory graph");
    try {
      const response = await searchMemories(query.trim());
      setResults(response.items);
      setStatus(`${response.items.length} matches`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Search failed");
    }
  }

  return (
    <section className="panel">
      <p className="eyebrow">Search</p>
      <h3>Recall a memory</h3>
      <form onSubmit={onSubmit}>
        <input
          className="input"
          placeholder="Search Bob, planner, health, or a remembered phrase"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <div className="button-row">
          <button className="button primary" type="submit">
            Search
          </button>
          <span className="badge">{status}</span>
        </div>
      </form>

      <div className="list" style={{ marginTop: 18 }}>
        {results.length ? (
          results.map((item, index) => (
            <div className="list-row" key={`${item.text}-${index}`}>
              <div>
                <strong>{item.matched_entity ?? item.source}</strong>
                <p>{item.text}</p>
              </div>
              <span className="badge">{item.distance.toFixed(2)}</span>
            </div>
          ))
        ) : (
          <div className="empty-state">Search results will appear here.</div>
        )}
      </div>
    </section>
  );
}
