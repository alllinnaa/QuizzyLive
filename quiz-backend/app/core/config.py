from __future__ import annotations

from typing import List, Any
from pydantic_settings import BaseSettings, SettingsConfigDict 
from pydantic import Field, AnyUrl, AliasChoices, field_validator


class Settings(BaseSettings):
    # Звідки читати .env і що робити з зайвими ключами
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",  # суворо: невідомі ключі заборонені (допомагає ловити орфографію)
    )

    # Загальні налаштування
    APP_NAME: str = "QuizzyLive Backend"
    API_V1_PREFIX: str = "/api/v1"
    APP_ENV: str = Field(
        "dev",
        validation_alias=AliasChoices("APP_ENV", "app_env"),
        description="Application environment: dev|staging|prod",
    )

    # Порти/хости
    BACKEND_PORT: int = Field(
        8000,
        validation_alias=AliasChoices("BACKEND_PORT", "app_port"),
        description="Backend port to bind",
    )

    # Supabase
    SUPABASE_URL: AnyUrl = Field(
        ...,
        validation_alias=AliasChoices("SUPABASE_URL", "supabase_url"),
        description="Your Supabase project URL",
    )
    SUPABASE_SERVICE_ROLE_KEY: str = Field(
        ...,
        validation_alias=AliasChoices("SUPABASE_SERVICE_ROLE_KEY", "supabase_service_role_key"),
        description="Service role key (server-side)",
    )
    SUPABASE_ANON_KEY: str | None = Field(
        None,
        validation_alias=AliasChoices("SUPABASE_ANON_KEY", "supabase_anon_key"),
        description="Public anon key (optional for server-side, but корисно для CORS/інтеграцій)",
    )
    SUPABASE_SCHEMA: str = Field(
        "public",
        validation_alias=AliasChoices("SUPABASE_SCHEMA", "supabase_schema"),
        description="Supabase schema name",
    )
   

    # CORS origins
    FRONTEND_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    @field_validator("FRONTEND_ORIGINS", mode="before")
    @classmethod
    def _parse_origins(cls, v: Any) -> Any:
        """
        Дозволяє задавати FRONTEND_ORIGINS у .env як:
        - JSON-масив: ["http://localhost:5173","http://localhost:3000"]
        - або як рядок: http://localhost:5173,http://localhost:3000
        - або з ; як роздільником
        """
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("[") and s.endswith("]"):
                # Спроба розпарсити JSON-масив
                import json
                try:
                    return json.loads(s)
                except Exception:
                    # якщо JSON кривий — fallback на split
                    pass
            # Розбір рядка зі списком
            return [item.strip() for item in s.replace(";", ",").split(",") if item.strip()]
        return v


settings = Settings()
