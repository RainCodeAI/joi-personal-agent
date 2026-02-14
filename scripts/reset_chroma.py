#!/usr/bin/env python3
"""Reset the local Chroma collection to the configured embedding dimension."""

import os
import shutil
from pathlib import Path

import chromadb
from dotenv import load_dotenv


def main():
    load_dotenv()

    persist_path = (
        os.getenv("CHROMA_DIR")
        or os.getenv("CHROMA_PATH")
        or "./data/index"
    )
    persist_dir = Path(persist_path).resolve()
    collection_name = os.getenv("CHROMA_COLLECTION", "memories")
    embed_dim = int(os.getenv("EMBED_DIM", "768"))

    if persist_dir.exists():
        shutil.rmtree(persist_dir)
        print(f"Removed existing Chroma directory: {persist_dir}")

    client = chromadb.PersistentClient(path=str(persist_dir))
    metadata = {"embed_dim": str(embed_dim), "hnsw:space": "cosine"}
    client.create_collection(name=collection_name, metadata=metadata)
    print(
        f"Created collection '{collection_name}' with embed_dim={embed_dim} at {persist_dir}"
    )

    # Add a dummy embedding to lock the dimension in Chroma
    collection = client.get_collection(name=collection_name)
    dummy_embedding = [0.0] * embed_dim  # Zero vector of correct length
    collection.add(
        ids=["dummy_init"],
        documents=["Initialization placeholder"],
        embeddings=[dummy_embedding],
        metadatas=[{"purpose": "dim_lock"}]
    )
    print(f"Added dummy embedding to lock dim={embed_dim}")


if __name__ == "__main__":
    main()