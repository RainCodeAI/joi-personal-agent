import { ChatClient } from "@/components/chat-client";

export const dynamic = "force-dynamic";

export default function ChatPage() {
  return (
    <>
      <header className="page-header">
        <div>
          <p className="eyebrow">Phase 2.2</p>
          <h1 className="page-title">Chat Surface</h1>
          <p className="page-copy">
            API-driven conversation shell with event-stream feedback for assistant state, approvals,
            and avatar cues.
          </p>
        </div>

        <div className="status-strip">
          <div className="status-card">
            <span>Transport</span>
            <strong>SSE</strong>
          </div>
          <div className="status-card">
            <span>Source</span>
            <strong>/api/v2</strong>
          </div>
          <div className="status-card">
            <span>Mode</span>
            <strong>Realtime</strong>
          </div>
        </div>
      </header>

      <ChatClient />
    </>
  );
}
