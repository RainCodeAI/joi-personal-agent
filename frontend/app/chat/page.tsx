import { ChatClient } from "@/components/chat-client";

export const dynamic = "force-dynamic";

export default function ChatPage() {
  return (
    <>
      <header className="page-header">
        <span className="page-breadcrumb-label">Chat</span>
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
