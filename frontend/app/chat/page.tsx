import { ChatClient } from "@/components/chat-client";

export const dynamic = "force-dynamic";

export default function ChatPage() {
  return (
    <>
      <header className="page-header">
        <span className="page-breadcrumb-label">Chat</span>
      </header>

      <ChatClient />
    </>
  );
}
