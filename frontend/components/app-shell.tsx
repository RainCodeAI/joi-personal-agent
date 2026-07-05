"use client";

import { ReactNode, useEffect, useState } from "react";

import { NavLink } from "@/components/nav-link";
import {
  PerceptionServicePanel,
  PerceptionServiceProvider,
} from "@/components/perception-service-provider";
import { AmbientListenerProvider } from "@/components/ambient-listener-provider";

const NAV_ITEMS = [
  { href: "/chat",        label: "Chat",        copy: "Realtime conversation and presence." },
  { href: "/memory",      label: "Memory",      copy: "Search, recall, and semantic traces." },
  { href: "/user-model",  label: "User Model",  copy: "What Joi knows about you." },
  { href: "/planner",     label: "Planner",     copy: "Context-aware day shaping." },
  { href: "/diagnostics", label: "Diagnostics", copy: "Provider, storage, and runtime truth." },
  { href: "/settings",    label: "Settings",    copy: "Mutable runtime controls." },
  { href: "/profile",     label: "Profile",     copy: "User context, habits, goals, and care loops." },
];

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem("joi-nav-collapsed") === "true");
    } catch {
      // localStorage unavailable
    }
  }, []);

  function toggle() {
    setCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem("joi-nav-collapsed", String(next)); } catch { /* ignore */ }
      return next;
    });
  }

  return (
    <PerceptionServiceProvider>
      <AmbientListenerProvider>
      <div className={`app-shell${collapsed ? " nav-collapsed" : ""}`}>
        <aside className="app-nav">
          <div className="brand-chip">
            {collapsed ? "J" : "Joi v2 Surface"}
          </div>

          {!collapsed && (
            <>
              <h1 className="brand-title">Joi</h1>
              <p className="brand-copy">
                I&apos;m here. Always on, always listening for you.
              </p>
            </>
          )}

          <nav className="nav-group" aria-label="Primary">
            {NAV_ITEMS.map((item) => (
              <NavLink key={item.href} {...item} collapsed={collapsed} />
            ))}
          </nav>

          <details
            className="aside-accordion app-nav-perception"
            aria-hidden={collapsed}
            inert={collapsed ? true : undefined}
          >
            <summary>
              <span>Presence sensing</span>
            </summary>
            <div className="aside-accordion-body">
              <PerceptionServicePanel />
            </div>
          </details>

          <button
            className="nav-collapse-btn"
            onClick={toggle}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? "›" : "‹"}
          </button>
        </aside>

        <main className="content-shell">
          <div className="content-frame">{children}</div>
        </main>
      </div>
      </AmbientListenerProvider>
    </PerceptionServiceProvider>
  );
}
