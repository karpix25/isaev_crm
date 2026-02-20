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
        if not v:
            return v
        
        # Aggressively strip any whitespace, newlines, or hidden control characters
        v = "".join(v.split()).strip()
        
        try:
            # First, handle the most common scheme issues manually before passing to make_url
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql://", 1)
            
            from sqlalchemy.engine.url import make_url
            url = make_url(v)
            
            # Ensure we use asyncpg
            if url.drivername == "postgresql":
                url = url.set(drivername="postgresql+asyncpg")
                
            # Strip problematic parameters for asyncpg
            query = dict(url.query)
            query.pop("sslmode", None)
            url = url.set(query=query)
            
            final_url = url.render_as_string(hide_password=False)
            
            # Diagnostic log (mask password but show crucial info)
            pwd = url.password or ""
            pwd_info = f"len={len(pwd)}"
            if pwd:
                # Show first and last char and total length to catch invisible chars
                pwd_info += f", first='{pwd[0]}', last='{pwd[-1]}'"
            
            masked_url = str(url.set(password="***"))
            host_info = f"{url.host}:{url.port}"
            print(f"📦 Database URL normalized: {masked_url} (Host: {host_info}, Pwd info: {pwd_info})")
            
            return final_url
        except Exception as e:
            print(f"⚠️ Error normalizing database_url: {e}")
            return v
    
    # Redis
    redis_url: str

    @field_validator("redis_url")
    @classmethod
    def fix_redis_url(cls, v: str) -> str:
        if v:
            v = v.strip()
            try:
                # Simple mask for logging
                if "@" in v:
                    part1, part2 = v.split("@", 1)
                    scheme_user = part1.split(":", 1)[0] + "://***"
                    masked_url = f"{scheme_user}@{part2}"
                else:
                    masked_url = v
                print(f"📦 Redis URL configured: {masked_url}")
            except Exception:
                pass
        return v
    
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
    openrouter_embedding_model: str = "voyageai/voyage-3"
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



    def __init__(self, **data):
        super().__init__(**data)
        self._validate_config()
    
    def _validate_config(self):
        """Validate critical configuration"""
        missing = []
        if not self.openrouter_api_key:
            missing.append("OPENROUTER_API_KEY")
        if not self.s3_access_key or not self.s3_secret_key:
            missing.append("S3_ACCESS_KEY/S3_SECRET_KEY")
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
            
        if missing:
            print(f"⚠️  WARNING: Missing critical environment variables: {', '.join(missing)}")
            print("   Please add them to your .env file or deployment configuration (Easypanel).")
        else:
            print("✅ Configuration loaded successfully.")

# Global settings instance
settings = Settings()
