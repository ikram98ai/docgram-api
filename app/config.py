from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"

    gemini_api_key: str

    class Config:
        env_file = ".env"


settings = Settings()
