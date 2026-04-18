import { ProfileForm } from "@/components/profile-form";
import { fetchProfile } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ProfilePage() {
  const profile = await fetchProfile();

  return (
    <>
      <header className="page-header">
        <div>
          <p className="eyebrow">Phase 2.1</p>
          <h1 className="page-title">Profile Surface</h1>
          <p className="page-copy">
            User profile, habits, goals, CBT support, activity traces, health logs, and contacts,
            all served from FastAPI.
          </p>
        </div>

        <div className="status-strip">
          <div className="status-card">
            <span>Habits</span>
            <strong>{profile.habits.length}</strong>
          </div>
          <div className="status-card">
            <span>Goals</span>
            <strong>{profile.goals.length}</strong>
          </div>
          <div className="status-card">
            <span>Contacts</span>
            <strong>{profile.contacts.length}</strong>
          </div>
        </div>
      </header>

      <div className="page-body grid two">
        <ProfileForm profile={profile.profile} />

        <div className="grid">
          <section className="panel">
            <p className="eyebrow">Habits & Goals</p>
            <h3>Behavior loops</h3>
            <div className="list">
              {profile.habits.map((habit) => (
                <div className="list-row" key={`habit-${habit.id}`}>
                  <div>
                    <strong>{habit.name}</strong>
                    <p>Streak: {habit.streak}</p>
                  </div>
                  <span className="badge">{habit.last_done ? "active" : "idle"}</span>
                </div>
              ))}
              {profile.goals.map((goal) => (
                <div className="list-row" key={`goal-${goal.id}`}>
                  <div>
                    <strong>{goal.name}</strong>
                    <p>{goal.description ?? "No description"}</p>
                  </div>
                  <span className={`badge ${goal.status === "completed" ? "ok" : "warn"}`}>
                    {goal.status}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="panel">
            <p className="eyebrow">Health & Contact</p>
            <h3>Care signals</h3>
            <div className="list">
              {profile.moods.slice(0, 4).map((mood) => (
                <div className="list-row" key={`mood-${mood.id}`}>
                  <div>
                    <strong>Mood</strong>
                    <p>{new Date(mood.date).toLocaleDateString()}</p>
                  </div>
                  <span className="badge">{mood.mood}/10</span>
                </div>
              ))}
              {profile.contacts.slice(0, 4).map((contact) => (
                <div className="list-row" key={`contact-${contact.id}`}>
                  <div>
                    <strong>{contact.name}</strong>
                    <p>Last contact: {contact.last_contact}</p>
                  </div>
                  <span className="badge">{contact.strength}/10</span>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
