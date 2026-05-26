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

    def _allowed_roots(self) -> List[Path]:
        roots = [
            Path(raw.strip()).resolve()
            for raw in settings.file_ingest_roots.split(",")
            if raw.strip()
        ]
        return roots or [Path("./data/ingest").resolve()]

    def _resolve_allowed_path(self, path: str | Path) -> Path:
        resolved = Path(path).resolve()
        if not any(resolved == root or root in resolved.parents for root in self._allowed_roots()):
            raise ValueError(
                "Path is outside configured FILE_INGEST_ROOTS"
            )
        return resolved

    def ingest_file(self, file_path: Path):
        file_path = self._resolve_allowed_path(file_path)
        if not file_path.exists() or not file_path.is_file():
            return
        if file_path.stat().st_size > settings.file_ingest_max_file_bytes:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
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
        path = self._resolve_allowed_path(dir_path)
        if not path.exists() or not path.is_dir():
            raise ValueError("Ingest path is not a directory")
        root_depth = len(path.parts)
        ingested = 0
        for root, dirs, files in os.walk(path):
            current = Path(root)
            depth = len(current.parts) - root_depth
            if depth >= settings.file_ingest_max_depth:
                dirs[:] = []
            dirs[:] = [
                d for d in dirs
                if d not in {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__"}
            ]
            for file in files:
                if ingested >= settings.file_ingest_max_files:
                    return
                file_path = Path(root) / file
                self.ingest_file(file_path)
                ingested += 1

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
