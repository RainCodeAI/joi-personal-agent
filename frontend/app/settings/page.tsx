import { SettingsForm } from "@/components/settings-form";
import { fetchSettings } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const settingsResponse = await fetchSettings();

  return (
    <>
      <header className="page-header">
        <div>
          <p className="eyebrow">Phase 2.1</p>
          <h1 className="page-title">Settings</h1>
          <p className="page-copy">
            Mutable runtime controls exposed through the backend contract for the migration window.
          </p>
        </div>

        <div className="status-strip">
          <div className="status-card">
            <span>Autonomy</span>
            <strong>{settingsResponse.settings.autonomy_level}</strong>
          </div>
          <div className="status-card">
            <span>Chat Model</span>
            <strong>{settingsResponse.settings.model_chat}</strong>
          </div>
          <div className="status-card">
            <span>Airgap</span>
            <strong>{settingsResponse.settings.airgap ? "On" : "Off"}</strong>
          </div>
        </div>
      </header>

      <div className="page-body">
        <SettingsForm settings={settingsResponse.settings} />
      </div>
    </>
  );
}
