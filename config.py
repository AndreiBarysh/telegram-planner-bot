import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


class Config:
    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    USE_WEBHOOK: bool = os.getenv("USE_WEBHOOK", "false").lower() == "true"
    WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", "8443"))

    # Database (SQLite by default, set DATABASE_URL for PostgreSQL)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{BASE_DIR / 'planner_bot.db'}",
    )
    DATABASE_URL_SYNC: str = os.getenv(
        "DATABASE_URL_SYNC",
        f"sqlite:///{BASE_DIR / 'planner_bot.db'}",
    )

    # Redis (optional)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    USE_REDIS: bool = os.getenv("USE_REDIS", "false").lower() == "true"

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: Path = BASE_DIR / "logs"

    # Scheduler
    MORNING_REMINDER_DEFAULT: str = "08:00"
    REMINDER_BEFORE_DUE_HOURS: list[int] = [24, 1]

    # Pagination
    PAGE_SIZE: int = 10

    # Timezone
    DEFAULT_TIMEZONE: str = "Europe/Moscow"
