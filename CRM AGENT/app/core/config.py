"""
Application configuration management with environment variables.
"""
import os
from functools import lru_cache
from typing import List, Optional

from pydantic import validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application settings
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    PORT: int = 8000
    
    # Security settings
    SECRET_KEY: str
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1"]
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # Database settings
    DATABASE_URL: str = "sqlite:///./ai_calling_agent.db"
    POSTGRES_URL: Optional[str] = None  # For LangGraph checkpoints
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Salesforce settings
    SALESFORCE_CLIENT_ID: str
    SALESFORCE_CLIENT_SECRET: str
    SALESFORCE_USERNAME: str
    SALESFORCE_PASSWORD: str
    SALESFORCE_SECURITY_TOKEN: str
    SALESFORCE_DOMAIN: str = "login"  # or "test" for sandbox
    
    # Twilio settings
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_PHONE_NUMBER: str
    TWILIO_WEBHOOK_URL: Optional[str] = None
    
    # ElevenLabs settings
    ELEVENLABS_API_KEY: str
    ELEVENLABS_VOICE_ID: Optional[str] = None
    
    # OpenRouter settings
    OPENROUTER_API_KEY: str
    OPENROUTER_MODEL: str = "mistralai/mistral-nemo:free"
    
    # Monitoring settings
    SENTRY_DSN: Optional[str] = None
    
    # Encryption settings
    ENCRYPTION_KEY: str
    
    # Approval and Notification settings
    SLACK_WEBHOOK_URL: Optional[str] = None
    SMTP_SERVER: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    FROM_EMAIL: Optional[str] = None
    APPROVER_EMAILS: Optional[List[str]] = None
    BASE_URL: str = "http://localhost:8000"
    
    @validator("ALLOWED_HOSTS", pre=True)
    def parse_allowed_hosts(cls, v):
        """Parse comma-separated allowed hosts."""
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v
    
    @validator("ALLOWED_ORIGINS", pre=True)
    def parse_allowed_origins(cls, v):
        """Parse comma-separated allowed origins."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("APPROVER_EMAILS", pre=True)
    def parse_approver_emails(cls, v):
        """Parse comma-separated approver emails."""
        if isinstance(v, str):
            return [email.strip() for email in v.split(",")]
        return v
    
    @validator("SECRET_KEY")
    def validate_secret_key(cls, v):
        """Ensure secret key is provided and sufficiently long."""
        if not v or len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v
    
    @validator("ENCRYPTION_KEY")
    def validate_encryption_key(cls, v):
        """Ensure encryption key is provided."""
        if not v:
            raise ValueError("ENCRYPTION_KEY is required for data encryption")
        return v
    
    @property
    def salesforce_base_url(self) -> str:
        """Get Salesforce base URL based on domain."""
        return f"https://{self.SALESFORCE_DOMAIN}.salesforce.com"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT.lower() == "development"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()