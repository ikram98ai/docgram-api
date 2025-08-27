from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    debug: bool
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"

    gemini_api_key: str

    # dynamodb_endpoint_url: str

    class Config:
        env_file = ".env"


settings = Settings()
