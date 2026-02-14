import httpx
from app.memory.store import MemoryStore
from app.config import settings

class Summarizer:
    def __init__(self):
        self.memory_store = MemoryStore()
        self.ollama_host = settings.ollama_host

    def summarize_chat_history(self, session_id: str) -> str:
        messages = self.memory_store.get_chat_history(session_id)
        if not messages:
            return "No chat history to summarize."
        
        # Concatenate messages
        history_text = "\n".join([f"{msg.role}: {msg.content}" for msg in messages])
        prompt = f"Summarize the following conversation:\n{history_text}\n\nSummary:"
        
        with httpx.Client() as client:
            response = client.post(
                f"{self.ollama_host}/api/generate",
                json={"model": "llama3.1", "prompt": prompt, "stream": False}
            )
            response.raise_for_status()
            data = response.json()
            summary = data["response"]
            # Add to memory
            self.memory_store.add_summary(session_id, summary)
            return summary
