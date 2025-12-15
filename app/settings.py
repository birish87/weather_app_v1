from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized configuration.

    Why:
    - Keeps secrets (API keys) out of source code
    - Makes local/dev/prod configuration consistent
    - Allows easy evaluation by reviewers: they just set env vars

    Loaded from:
    - environment variables
    - .env file (if present)
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Required key (the app should fail fast if missing)
    openweather_api_key: str

    # Non-secret cosmetics
    app_name: str = "Weather App (PMA Tech Assessment)"
    candidate_name: str = "Your Name Here"

    # SQLite file path (simple local persistence)
    sqlite_path: str = "weather_app.sqlite3"


settings = Settings()
