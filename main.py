"""Entry point for the Telegram Planner Bot."""

import asyncio
import logging
import os
import signal
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import Config
from database.db import close_db, init_db
from database.seed_blueprint import seed_blueprint_plan
from handlers.callbacks import callback_handler
from handlers.commands import (
    add_project_command,
    add_task_command,
    calendar_command,
    cancel_reminder_command,
    complete_task_command,
    delete_project_command,
    delete_task_command,
    edit_project_command,
    edit_task_command,
    help_command,
    list_projects_command,
    list_reminders_command,
    list_tasks_command,
    menu_command,
    productivity_report_command,
    project_stats_command,
    search_command,
    set_reminder_command,
    start_command,
    stats_command,
    stats_detailed_command,
    task_details_command,
    tasks_for_day_command,
    # Phase 3
    export_csv_command,
    export_pdf_command,
    gcal_connect_command,
    gcal_sync_command,
    gcal_events_command,
    profile_command,
    achievements_command,
    share_task_command,
)
from handlers.messages import text_message_handler
from scheduler.reminders_scheduler import init_scheduler, stop_scheduler


def setup_logging() -> None:
    """Configure logging with console and file handlers."""
    log_dir = Config.LOG_DIR
    log_dir.mkdir(exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_dir / "bot.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, Config.LOG_LEVEL, logging.INFO))

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Silence noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def build_application() -> Application:
    """Build and configure the Telegram bot application."""
    if not Config.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set. Check your .env file.")

    from telegram.request import HTTPXRequest

    proxy = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")

    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
        proxy=proxy,
    )
    get_updates_request = HTTPXRequest(
        read_timeout=60.0,
        connect_timeout=30.0,
        proxy=proxy,
    )
    app = (
        Application.builder()
        .token(Config.BOT_TOKEN)
        .request(request)
        .get_updates_request(get_updates_request)
        .build()
    )

    # ── Command handlers ──────────────────────────────────────────────────
    commands = [
        ("start", start_command),
        ("help", help_command),
        ("menu", menu_command),
        # Tasks
        ("add_task", add_task_command),
        ("list_tasks", list_tasks_command),
        ("edit_task", edit_task_command),
        ("complete_task", complete_task_command),
        ("delete_task", delete_task_command),
        ("task_details", task_details_command),
        ("search", search_command),
        # Projects
        ("add_project", add_project_command),
        ("list_projects", list_projects_command),
        ("project_stats", project_stats_command),
        ("edit_project", edit_project_command),
        ("delete_project", delete_project_command),
        # Reminders
        ("set_reminder", set_reminder_command),
        ("list_reminders", list_reminders_command),
        ("cancel_reminder", cancel_reminder_command),
        # Calendar
        ("calendar", calendar_command),
        ("tasks_for_day", tasks_for_day_command),
        # Stats
        ("stats", stats_command),
        ("stats_detailed", stats_detailed_command),
        ("productivity_report", productivity_report_command),
        # Phase 3: Export
        ("export_csv", export_csv_command),
        ("export_pdf", export_pdf_command),
        # Phase 3: Google Calendar
        ("gcal_connect", gcal_connect_command),
        ("gcal_sync", gcal_sync_command),
        ("gcal_events", gcal_events_command),
        # Phase 3: Gamification
        ("profile", profile_command),
        ("achievements", achievements_command),
        # Phase 3: Sharing
        ("share_task", share_task_command),
    ]

    for name, handler in commands:
        app.add_handler(CommandHandler(name, handler))

    # ── Callback query handler ────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(callback_handler))

    # ── Text message handler (catch-all) ──────────────────────────────────
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))

    return app


async def on_startup(app: Application) -> None:
    """Run startup tasks."""
    logger = logging.getLogger(__name__)
    await init_db()
    try:
        await seed_blueprint_plan()
    except Exception:
        logger.exception("Blueprint seed failed (continuing startup)")
    init_scheduler(app)
    logger.info("Bot started successfully")


async def on_shutdown(app: Application) -> None:
    """Run shutdown tasks."""
    logger = logging.getLogger(__name__)
    stop_scheduler()
    await close_db()
    logger.info("Bot shut down gracefully")


def main() -> None:
    """Main entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Telegram Planner Bot...")

    app = build_application()

    # Register lifecycle hooks
    app.post_init = on_startup
    app.post_shutdown = on_shutdown

    if Config.USE_WEBHOOK:
        logger.info("Running with webhook on port %d", Config.WEBHOOK_PORT)
        app.run_webhook(
            listen="0.0.0.0",
            port=Config.WEBHOOK_PORT,
            url_path="webhook",
            webhook_url=f"{Config.WEBHOOK_URL}/webhook",
        )
    else:
        logger.info("Running with long polling")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
