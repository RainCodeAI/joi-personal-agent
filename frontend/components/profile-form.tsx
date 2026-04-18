"use client";

import { FormEvent, useState } from "react";

import { patchProfile } from "@/lib/api";
import { ProfileBundle } from "@/lib/types";

type ProfileFormProps = {
  profile: ProfileBundle["profile"];
};

export function ProfileForm({ profile }: ProfileFormProps) {
  const [form, setForm] = useState({
    name: profile.name ?? "",
    email: profile.email ?? "",
    hobbies: profile.hobbies ?? "",
    relationships: profile.relationships ?? "",
    notes: profile.notes ?? "",
    personality: profile.personality ?? "",
    humor_level: profile.humor_level,
  });
  const [status, setStatus] = useState("Ready");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("Saving profile");
    try {
      await patchProfile(form);
      setStatus("Profile saved");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to save profile");
    }
  }

  return (
    <form className="panel" onSubmit={onSubmit}>
      <p className="eyebrow">Editable Identity</p>
      <h3>Profile patch</h3>
      <div className="field-grid">
        <div className="field">
          <label htmlFor="profile-name">Name</label>
          <input
            id="profile-name"
            className="input"
            value={form.name}
            onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
          />
        </div>
        <div className="field">
          <label htmlFor="profile-email">Email</label>
          <input
            id="profile-email"
            className="input"
            value={form.email}
            onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
          />
        </div>
        <div className="field">
          <label htmlFor="profile-personality">Personality</label>
          <input
            id="profile-personality"
            className="input"
            value={form.personality}
            onChange={(event) => setForm((current) => ({ ...current, personality: event.target.value }))}
          />
        </div>
        <div className="field">
          <label htmlFor="profile-humor">Humor Level</label>
          <input
            id="profile-humor"
            className="input"
            max={10}
            min={1}
            type="number"
            value={form.humor_level}
            onChange={(event) =>
              setForm((current) => ({ ...current, humor_level: Number(event.target.value || 1) }))
            }
          />
        </div>
      </div>

      <div className="field" style={{ marginTop: 14 }}>
        <label htmlFor="profile-hobbies">Hobbies</label>
        <textarea
          id="profile-hobbies"
          className="textarea"
          value={form.hobbies}
          onChange={(event) => setForm((current) => ({ ...current, hobbies: event.target.value }))}
        />
      </div>

      <div className="field" style={{ marginTop: 14 }}>
        <label htmlFor="profile-relationships">Relationships</label>
        <textarea
          id="profile-relationships"
          className="textarea"
          value={form.relationships}
          onChange={(event) => setForm((current) => ({ ...current, relationships: event.target.value }))}
        />
      </div>

      <div className="field" style={{ marginTop: 14 }}>
        <label htmlFor="profile-notes">Notes</label>
        <textarea
          id="profile-notes"
          className="textarea"
          value={form.notes}
          onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
        />
      </div>

      <div className="button-row">
        <button className="button primary" type="submit">
          Save profile
        </button>
        <span className="badge">{status}</span>
      </div>
    </form>
  );
}
