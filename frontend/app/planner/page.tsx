import { PlannerForm } from "@/components/planner-form";
import { fetchPlannerContext } from "@/lib/api";

export const dynamic = "force-dynamic";

function readString(value: unknown, fallback: string) {
  return typeof value === "string" ? value : fallback;
}

function readNumber(value: unknown, fallback: number) {
  return typeof value === "number" ? value : fallback;
}

export default async function PlannerPage() {
  const context = await fetchPlannerContext().catch(() => ({
    snapshot: {
      user_id: "default",
      latest_mood: 5,
      mood_trend: {},
      health_correlation: {},
      overdue_contacts: [],
      active_goals: [],
      habits: [],
    },
  }));
  const moodTrend = context.snapshot.mood_trend as Record<string, unknown>;
  const healthCorrelation = context.snapshot.health_correlation as Record<string, unknown>;

  return (
    <>
      <header className="page-header">
        <div>
          <p className="eyebrow">Phase 2.1</p>
          <h1 className="page-title">Planner Surface</h1>
          <p className="page-copy">
            Planning context now comes from dedicated backend APIs instead of a page-local Ollama
            call.
          </p>
        </div>

        <div className="status-strip">
          <div className="status-card">
            <span>Latest Mood</span>
            <strong>{context.snapshot.latest_mood}/10</strong>
          </div>
          <div className="status-card">
            <span>Goals</span>
            <strong>{context.snapshot.active_goals.length}</strong>
          </div>
          <div className="status-card">
            <span>Habits</span>
            <strong>{context.snapshot.habits.length}</strong>
          </div>
        </div>
      </header>

      <div className="page-body grid">
        <div className="grid three">
          <section className="metric-card">
            <span>Mood Direction</span>
            <strong>{readString(moodTrend["direction"], "flat")}</strong>
          </section>
          <section className="metric-card">
            <span>Overdue Contacts</span>
            <strong>{context.snapshot.overdue_contacts.length}</strong>
          </section>
          <section className="metric-card">
            <span>Health Delta</span>
            <strong>{readNumber(healthCorrelation["sleep_delta"], 0)}</strong>
          </section>
        </div>

        <PlannerForm />
      </div>
    </>
  );
}
