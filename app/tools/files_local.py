import os
from pathlib import Path
from typing import List, Dict, Any
import chromadb
from app.config import settings
from app.memory.store import MemoryStore

class FileIngester:
    def __init__(self):
        self.memory_store = MemoryStore()
        self.chroma_client = chromadb.PersistentClient(path=str(settings.chroma_path_abs))
        self.collection = self.chroma_client.get_or_create_collection(name="files")

    def chunk_text(self, text: str, chunk_size: int = 1000) -> List[str]:
        # Simple chunking by words
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i+chunk_size])
            chunks.append(chunk)
        return chunks

    def ingest_file(self, file_path: Path):
        if not file_path.exists() or not file_path.is_file():
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            return  # Skip non-text files
        
        chunks = self.chunk_text(content)
        for i, chunk in enumerate(chunks):
            embedding = self.memory_store.embed_text(chunk)
            self.collection.add(
                documents=[chunk],
                metadatas=[{"source": str(file_path), "chunk": i}],
                ids=[f"{file_path}_{i}"]
            )

    def ingest_directory(self, dir_path: str):
        path = Path(dir_path)
        for root, dirs, files in os.walk(path):
            for file in files:
                file_path = Path(root) / file
                self.ingest_file(file_path)

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        query_embedding = self.memory_store.embed_text(query)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k
        )
        docs = []
        for doc, meta, dist in zip(results['documents'][0], results['metadatas'][0], results['distances'][0]):
            docs.append({
                "text": doc,
                "source": meta["source"],
                "chunk": meta["chunk"],
                "distance": dist
            })
        return docs
