from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from typing import Optional

class Settings(BaseSettings):
    app_env: str = Field(default="dev")
    ollama_host: str = Field(default="http://127.0.0.1:11434")
    db_path: str = Field(default="./data/agent.db")
    chroma_path: str = Field(default="./data/index")
    chroma_collection: str = Field(default="memories")
    airgap: bool = Field(default=False)
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")
    oauth_redirect_uri: str = Field(default="http://localhost:8000/oauth/callback")
    database_url: str = Field(default="")
    model_chat: str = Field(default="microsoft/DialoGPT-medium")
    model_embed: str = Field(default="nomic-embed-text")
    embed_dim: int = Field(default=768)
    openai_api_key: str = Field(default="")
    xai_api_key: str = Field(default="")
    gemini_api_key: str = Field(default="")
    router_timeout: int = Field(default=30)
    autonomy_level: str = Field(default="medium")  # low, medium, high

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = 'ignore'

    @property
    def db_path_abs(self) -> Path:
        return Path(self.db_path).resolve()

    @property
    def chroma_path_abs(self) -> Path:
        return Path(self.chroma_path).resolve()

settings = Settings()