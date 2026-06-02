import os
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    app_name: str = "Insurance Claim Backend"
    api_prefix: str = "/api"
    cookie_name: str = "user_id"
    cookie_max_age: int = 60 * 60 * 24 * 30  # 30 days
    cors_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5175",
            "http://127.0.0.1:5175",
        ]
    )
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    # lru_cache to reuse settings across requests
    return Settings(_env_file=os.getenv("ENV_FILE", ".env"))
