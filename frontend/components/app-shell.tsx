import { ReactNode } from "react";

import { NavLink } from "@/components/nav-link";

const NAV_ITEMS = [
  { href: "/chat", label: "Chat", copy: "Realtime conversation and presence." },
  { href: "/memory", label: "Memory", copy: "Search, recall, and semantic traces." },
  { href: "/planner", label: "Planner", copy: "Context-aware day shaping." },
  { href: "/diagnostics", label: "Diagnostics", copy: "Provider, storage, and runtime truth." },
  { href: "/settings", label: "Settings", copy: "Mutable runtime controls." },
  { href: "/profile", label: "Profile", copy: "User context, habits, goals, and care loops." },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <aside className="app-nav">
        <div className="brand-chip">Joi v2 Surface</div>
        <h1 className="brand-title">Joi</h1>
        <p className="brand-copy">
          Blade Runner-inspired control surface for chat, memory, planning, diagnostics, and
          avatar-state orchestration.
        </p>

        <nav className="nav-group" aria-label="Primary">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.href} {...item} />
          ))}
        </nav>

        <div style={{ marginTop: 28 }} className="panel hero-card">
          <p className="eyebrow">Migration Window</p>
          <strong style={{ display: "block", marginBottom: 8, fontFamily: "var(--font-display)" }}>
            Streamlit is now a fallback client.
          </strong>
          <p className="meta-copy" style={{ margin: 0 }}>
            The web shell is wired directly to FastAPI contracts so the UI stops owning product
            logic.
          </p>
        </div>
      </aside>

      <main className="content-shell">
        <div className="content-frame">{children}</div>
      </main>
    </div>
  );
}
