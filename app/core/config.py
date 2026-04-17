"""Application configuration using Pydantic Settings."""
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    所有必填字段在启动时会自动校验，缺失时会抛出 ValidationError。
    """

    # Application
    app_name: str = "Storycoe API"
    app_version: str = "1.0.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # PostgreSQL Database
    database_url: str = Field(
        "postgresql://postgres:postgres@localhost:5432/story_db",
        description="PostgreSQL 数据库连接 URL",
    )

    # File Storage
    upload_dir: str = Field(
        "uploads",
        description="文件上传目录",
    )

    # Security
    secret_key: str = Field("dev-secret-key-change-in-production", description="JWT 签名密钥")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Google AI
    google_ai_api_key: Optional[str] = None

    # 阿里百炼 OCR
    aliyun_api_key: str = Field(
        "sk-sp-0670c99fc479444f94dc28be0f84e7bf",
        description="阿里百炼 API Key",
    )

    # 微信小程序
    wechat_appid: str | None = Field(None, description="微信小程序 AppID")
    wechat_secret: str | None = Field(None, description="微信小程序 AppSecret")

    # CORS
    cors_origins: list[str] = ["*"]

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 忽略未定义的环境变量


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    启动时会校验所有必填字段，校验失败会抛出 ValidationError。
    """
    return Settings()


settings = get_settings()