#!/usr/bin/env python3
import os
import sys
from pathlib import Path

def check_env():
    if not Path(".env").exists():
        print("Warning: .env file not found. Copy from .env.example")
    else:
        print("✓ .env found")

def check_ollama():
    try:
        import httpx
        with httpx.Client() as client:
            response = client.get("http://127.0.0.1:11434/api/tags")
            if response.status_code == 200:
                print("✓ Ollama running")
            else:
                print("✗ Ollama not responding")
    except:
        print("✗ Ollama not accessible")

def check_dirs():
    dirs = ["data/vault", "data/index"]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    print("✓ Directories created")

def main():
    print("Bootstrapping Joi...")
    check_env()
    check_ollama()
    check_dirs()
    print("Bootstrap complete!")

if __name__ == "__main__":
    main()
