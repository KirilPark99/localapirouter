from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr, model_validator
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = BASE_DIR / "myairouter.db"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{DEFAULT_DB_PATH}"))

    # Security & Encryption. These values are intentionally required: silently
    # deriving encryption/JWT keys from each other makes a leaked token a data
    # decryption key as well.
    ROUTER_MASTER_KEY: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # Admin Credentials. There is no safe default password.
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str

    # Native OAuth application credentials are deployment-local.
    ANTIGRAVITY_OAUTH_CLIENT_ID: str = ""
    ANTIGRAVITY_OAUTH_CLIENT_SECRET: SecretStr = SecretStr("")

    # Privacy & Logging
    LOG_REQUEST_CONTENT: bool = False
    DEFAULT_TIMEOUT_SECONDS: float = 60.0
    FUSION_TIMEOUT_SECONDS: float = 120.0
    MAX_FALLBACK_ATTEMPTS: int = 5

    # Fingerprint Salt. This must be unique per installation.
    FINGERPRINT_SALT: str

    # Browser security
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    COOKIE_SECURE: bool = True

    @model_validator(mode="after")
    def validate_security_settings(self):
        if len(self.ROUTER_MASTER_KEY.strip()) < 32:
            raise ValueError("ROUTER_MASTER_KEY must be a generated Fernet key")
        if len(self.JWT_SECRET.strip()) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters")
        if len(self.ADMIN_PASSWORD) < 12:
            raise ValueError("ADMIN_PASSWORD must contain at least 12 characters")
        if len(self.FINGERPRINT_SALT.strip()) < 16:
            raise ValueError("FINGERPRINT_SALT must contain at least 16 characters")
        return self

settings = Settings()
