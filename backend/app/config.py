from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR.parent / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    elevenlabs_api_key: str
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    elevenlabs_voice_ids: str = ""

    gemini_api_key: str
    gemini_model: str = "gemini-flash-latest"

    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "podcast-generator"
    # LangSmith data region endpoint. Leave blank for the US default; set to
    # https://eu.api.smith.langchain.com if your LangSmith account is in the EU region
    # (an EU key returns 403 against the US endpoint).
    langchain_endpoint: str = ""

    session_secret: str
    admin_token: str

    database_url: str = "sqlite:///./storage/db.sqlite3"
    chroma_dir: str = "./storage/chroma"
    scripts_dir: str = "./storage/scripts"
    audio_dir: str = "./storage/audio"

    # Optional: where `python -m app.ingest` reads course material from. Accepts a
    # local/network path (bare path or file:// URI) or an S3-compatible URI
    # (s3://bucket/prefix — credentials come from the standard AWS env vars).
    # Leave blank to skip this feature entirely (seed script / admin upload still work).
    source_root: str = ""
    # Manifest listing topics to ingest, same shape as seed/data/topics.json. Defaults
    # to "<source_root>/topics.json" when left blank.
    source_manifest: str = ""
    # Only needed for S3-compatible-but-not-AWS storage (e.g. Cloudflare R2).
    s3_endpoint_url: str = ""

    cors_origins: str = "http://localhost:5173"

    @property
    def voice_id_list(self) -> list[str]:
        return [v.strip() for v in self.elevenlabs_voice_ids.split(",") if v.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def resolved_path(self, relative: str) -> Path:
        p = Path(relative)
        return p if p.is_absolute() else (BACKEND_DIR / relative).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()


def apply_langsmith_env() -> None:
    """LangChain/LangSmith read tracing config from process env vars, not our
    Settings object — propagate them once at startup."""
    import os

    settings = get_settings()
    os.environ["LANGCHAIN_TRACING_V2"] = "true" if settings.langchain_tracing_v2 else "false"
    if settings.langchain_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    if settings.langchain_endpoint:
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint
