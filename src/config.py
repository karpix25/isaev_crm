from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Optional


class Settings(BaseSettings):
    """Application configuration using Pydantic Settings v2"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application metadata
    project_name: str = "Renovation ERP"
    version: str = "1.0.0"
    api_v1_str: str = "/api/v1"
    
    # Database
    database_url: str

    @field_validator("database_url")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        if v and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v
    
    # Redis
    redis_url: str
    
    # S3 Storage (R2/AWS/Cloudinary compatible)
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str = "renovation-media"
    s3_secure: bool = True
    
    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    
    # Telegram
    telegram_bot_token: str
    telegram_webhook_url: str = ""
    manager_telegram_id: Optional[int] = None  # Telegram ID of manager to notify on hot leads
    
    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-3.5-sonnet"
    openrouter_embedding_model: str = "text-embedding-3-small"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    
    # LangFuse Observability
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    
    # Application
    app_env: str = "development"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    
    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    
    @property
    def all_cors_origins(self) -> List[str]:
        """Alias for cors_origins_list for backward compatibility"""
        return self.cors_origins_list
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.cors_origins.split(",")]


# Global settings instance
settings = Settings()
