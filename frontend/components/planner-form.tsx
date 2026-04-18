"use client";

import { FormEvent, useState } from "react";

import { generatePlan } from "@/lib/api";
import { PlannerResponse } from "@/lib/types";

type PlannerFormProps = {
  initialPlan?: PlannerResponse | null;
};

export function PlannerForm({ initialPlan = null }: PlannerFormProps) {
  const [tasks, setTasks] = useState("Build Next.js shell\nWire approvals\nPort avatar renderer");
  const [focusAreas, setFocusAreas] = useState("Work, Product");
  const [energyLevel, setEnergyLevel] = useState(7);
  const [status, setStatus] = useState("Ready");
  const [plan, setPlan] = useState<PlannerResponse | null>(initialPlan);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("Generating plan");
    try {
      const response = await generatePlan({
        key_tasks: tasks.split("\n").map((task) => task.trim()).filter(Boolean),
        focus_areas: focusAreas.split(",").map((area) => area.trim()).filter(Boolean),
        energy_level: energyLevel,
      });
      setPlan(response);
      setStatus(`Plan ready via ${response.provider}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to generate plan");
    }
  }

  return (
    <div className="grid two">
      <form className="panel" onSubmit={onSubmit}>
        <p className="eyebrow">Day Shaping</p>
        <h3>Generate planner output</h3>
        <div className="field">
          <label htmlFor="planner-tasks">Key Tasks</label>
          <textarea
            id="planner-tasks"
            className="textarea"
            value={tasks}
            onChange={(event) => setTasks(event.target.value)}
          />
        </div>

        <div className="field-grid" style={{ marginTop: 14 }}>
          <div className="field">
            <label htmlFor="planner-focus">Focus Areas</label>
            <input
              id="planner-focus"
              className="input"
              value={focusAreas}
              onChange={(event) => setFocusAreas(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="planner-energy">Energy Level</label>
            <input
              id="planner-energy"
              className="input"
              max={10}
              min={1}
              type="number"
              value={energyLevel}
              onChange={(event) => setEnergyLevel(Number(event.target.value || 1))}
            />
          </div>
        </div>

        <div className="button-row">
          <button className="button primary" type="submit">
            Generate plan
          </button>
          <span className="badge">{status}</span>
        </div>
      </form>

      <section className="panel">
        <p className="eyebrow">Plan Output</p>
        <h3>Time blocks</h3>
        <div className="list">
          {plan?.blocks.length ? (
            plan.blocks.map((block) => (
              <div className="list-row" key={`${block.time}-${block.activity}`}>
                <div>
                  <strong>{block.activity}</strong>
                  <p>{block.time}</p>
                </div>
                <span className="badge">{plan.provider}</span>
              </div>
            ))
          ) : (
            <div className="empty-state">No generated plan yet.</div>
          )}
        </div>
      </section>
    </div>
  );
}
