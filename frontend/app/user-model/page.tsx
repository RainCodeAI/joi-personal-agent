import { fetchUserModel, fetchUserModelPromptPreview } from "@/lib/api";
import { UserModelPanel } from "@/components/user-model-panel";

export const dynamic = "force-dynamic";

const EMPTY_SECTIONS = [
  { key: "active_projects", title: "Active Projects", description: "Current projects Joi is aware of.", items: [] },
  { key: "recurring_worries", title: "Recurring Worries", description: "Patterns of concern that have come up across sessions.", items: [] },
  { key: "stated_goals", title: "Stated Goals", description: "Goals you have explicitly mentioned.", items: [] },
  { key: "important_people", title: "Important People", description: "People who matter to you.", items: [] },
  { key: "mood_trend", title: "Mood Trend", description: "Emotional patterns observed over time.", items: [] },
  { key: "communication_preferences", title: "Communication Preferences", description: "How you prefer to be spoken to.", items: [] },
  { key: "recent_wins", title: "Recent Wins", description: "Positive outcomes worth acknowledging.", items: [] },
  { key: "open_loops", title: "Open Loops", description: "Things left unresolved or mentioned but not followed up.", items: [] },
  { key: "character_notes", title: "Character Notes", description: "Joi's current read on you — not facts, but tone and texture.", items: [] },
];

const FALLBACK_MODEL = {
  api_version: "v2" as const,
  user_id: "default",
  status: "contract_only" as const,
  generated_at: new Date().toISOString(),
  policy: {
    inference_enabled: false,
    correction_supported: false,
    initiative_surface_enabled: false,
    min_confidence_to_surface: 0.75,
    stores_raw_files: false,
    stores_raw_presence_streams: false,
  },
  readable_summary: "",
  sections: EMPTY_SECTIONS,
};

export default async function UserModelPage() {
  const [userModel, promptPreview] = await Promise.all([
    fetchUserModel().catch(() => FALLBACK_MODEL),
    fetchUserModelPromptPreview().catch(() => ({ api_version: "v2" as const, user_id: "default", prompt_block: "", line_count: 0 })),
  ]);

  const mergedSections = EMPTY_SECTIONS.map((empty) => {
    const live = userModel.sections.find((s) => s.key === empty.key);
    return live ?? empty;
  });

  return (
    <UserModelPanel
      initialUserModel={{ ...userModel, sections: mergedSections }}
      initialPromptBlock={promptPreview.prompt_block}
    />
  );
}
