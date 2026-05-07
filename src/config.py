import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str
    google_proxy_url: str

    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    boris_token: str
    maria_token: str
    daniela_token: str

    audio_storage_path: str = "/app/audio_storage"
    openclaw_notify_url: str = "http://localhost:18789/api/notify"

    environment: str = "production"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "case_sensitive": False}


settings = Settings()

# Устанавливаем прокси для всех Google API вызовов (обязательно!)
os.environ["HTTPS_PROXY"] = settings.google_proxy_url
os.environ["HTTP_PROXY"] = settings.google_proxy_url
