import { PerceptionPolicyForm } from "@/components/perception-policy-form";
import { SettingsForm } from "@/components/settings-form";
import { fetchPerceptionPolicy, fetchSettings } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const [settingsResponse, policyResponse] = await Promise.all([
    fetchSettings(),
    fetchPerceptionPolicy(),
  ]);

  return (
    <>
      <header className="page-header">
        <span className="page-breadcrumb-label">Settings</span>
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
          <div className="status-card">
            <span>Camera</span>
            <strong>{policyResponse.policy.camera_enabled ? "On" : "Off"}</strong>
          </div>
          <div className="status-card">
            <span>Hardware Bridge</span>
            <strong>{settingsResponse.settings.enable_hardware_nodes ? "On" : "Off"}</strong>
          </div>
          <div className="status-card">
            <span>Initiatives</span>
            <strong>{settingsResponse.settings.initiative_enabled ? "On" : "Off"}</strong>
          </div>
          <div className="status-card">
            <span>Daily limit</span>
            <strong>{settingsResponse.settings.initiative_daily_limit}</strong>
          </div>
        </div>
      </header>

      <div className="page-body">
        <SettingsForm settings={settingsResponse.settings} />
        <div style={{ marginTop: 32 }}>
          <PerceptionPolicyForm policy={policyResponse.policy} />
        </div>
      </div>
    </>
  );
}
