from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_ID: int
    DATABASE_URL: str = "sqlite+aiosqlite:///bot.db"
    PAYMENT_RATE: float = 10.0  # per conversion
    CRYPTOBOT_TOKEN: Optional[str] = None
    WEBAPP_URL: Optional[str] = None  # Your Railway app public URL for mini-apps

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
