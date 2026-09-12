from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # GitHub
    github_webhook_secret: str
    github_token: Optional[str] = None
    
    # Slack
    slack_webhook_url: str
    slack_channel: str = "#notifications"
    
    # Security
    secret_key: str = "change-this-in-production"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
