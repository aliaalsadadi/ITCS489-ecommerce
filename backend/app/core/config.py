import json
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Souq Al Artisan API"
    api_v1_prefix: str = "/api/v1"
    debug: bool = True

    database_url: str

    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str | None = None

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:5173" , "http://127.0.0.1:5173"])

    # Allows wildcard origins for dev tunnels (e.g. ngrok) without having to keep updating cors_origins.
    # If set, CORSMiddleware will allow any Origin matching this regex.
    cors_origin_regex: str | None = r"^https?://.*\\.(ngrok-free\\.app|ngrok\\.io)$"

    auto_create_tables: bool = True
    default_currency: str = "BHD"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        url = value.strip()
        if "sslmode=require" in url:
            url = url.replace("sslmode=require", "ssl=require")
        if "supabase.co" in url and "ssl=" not in url:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}ssl=require"
        return url

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            maybe_json = value.strip()
            if maybe_json.startswith("["):
                try:
                    parsed = json.loads(maybe_json)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
