import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Aegis Assistant Backend"
    app_version: str = "1.0.0"
    port: int = 25530
    host: str = "0.0.0.0"
    
    # Gemini AI configuration
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    
    # Database
    database_url: str = "sqlite:///./aegis.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
