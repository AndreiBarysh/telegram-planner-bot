"""APScheduler-based reminder system."""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application

from database.db import get_session
from database.models import UserSettings
from services.reminder_service import ReminderService
from utils.keyboards import reminder_done_keyboard

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
_app: Application | None = None


def init_scheduler(app: Application) -> None:
    """Initialize and start the reminder scheduler."""
    global _app
    _app = app

    # Check due reminders every 60 seconds
    scheduler.add_job(
        _check_due_reminders,
        trigger=IntervalTrigger(seconds=60),
        id="check_due_reminders",
        replace_existing=True,
    )

    # Morning reminders — check every minute around morning hours
    scheduler.add_job(
        _send_morning_reminders,
        trigger=CronTrigger(minute="*/1", hour="5-12"),
        id="morning_reminders",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Reminder scheduler started")


def stop_scheduler() -> None:
    """Gracefully stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Reminder scheduler stopped")


async def _check_due_reminders() -> None:
    """Check for reminders that are due and send them."""
    try:
        async with get_session() as session:
            reminders = await ReminderService.get_due_reminders(session)

            for reminder in reminders:
                try:
                    task = reminder.task
                    if task is None:
                        await ReminderService.mark_sent(session, reminder.reminder_id)
                        continue

                    text = (
                        f"🔔 Напоминание!\n\n"
                        f"📋 {task.title}\n"
                    )
                    if task.due_date:
                        remaining = task.due_date - datetime.utcnow()
                        if remaining.total_seconds() > 0:
                            hours = int(remaining.total_seconds() // 3600)
                            text += f"⏰ До дедлайна: {hours} ч.\n"
                        else:
                            text += "🔴 Дедлайн просрочен!\n"

                    if task.description:
                        text += f"📝 {task.description[:100]}\n"

                    await _app.bot.send_message(
                        chat_id=reminder.user_id,
                        text=text,
                        reply_markup=reminder_done_keyboard(task.task_id),
                    )
                    await ReminderService.mark_sent(session, reminder.reminder_id)
                    logger.info(
                        "Reminder sent: id=%d user=%d task=%d",
                        reminder.reminder_id, reminder.user_id, reminder.task_id,
                    )

                except Exception as e:
                    logger.error(
                        "Failed to send reminder %d: %s",
                        reminder.reminder_id, e, exc_info=True,
                    )

    except Exception as e:
        logger.error("Error checking due reminders: %s", e, exc_info=True)


async def _send_morning_reminders() -> None:
    """Send morning digest of today's tasks to users who have it enabled."""
    try:
        now = datetime.utcnow()
        current_time = f"{now.hour:02d}:{now.minute:02d}"

        from sqlalchemy import select
        async with get_session() as session:
            # Find users whose morning reminder time matches current minute
            result = await session.execute(
                select(UserSettings).where(
                    UserSettings.notifications_enabled == True,
                    UserSettings.morning_reminder_time == current_time,
                )
            )
            settings_list = result.scalars().all()

            for settings in settings_list:
                try:
                    tasks = await ReminderService.get_morning_tasks(
                        session, settings.user_id
                    )
                    if not tasks:
                        continue

                    text = f"☀️ Доброе утро! Задачи на сегодня ({len(tasks)}):\n\n"
                    for i, task in enumerate(tasks, 1):
                        from utils.formatters import PRIORITY_EMOJI
                        emoji = PRIORITY_EMOJI.get(task.priority, "🟡")
                        time_str = task.due_date.strftime("%H:%M") if task.due_date else ""
                        text += f"{emoji} {i}. {task.title}"
                        if time_str:
                            text += f" ⏰ {time_str}"
                        text += "\n"

                    text += "\nУдачного дня! 💪"

                    await _app.bot.send_message(
                        chat_id=settings.user_id,
                        text=text,
                    )
                    logger.info("Morning reminder sent to user %d", settings.user_id)

                except Exception as e:
                    logger.error(
                        "Failed to send morning reminder to %d: %s",
                        settings.user_id, e, exc_info=True,
                    )

    except Exception as e:
        logger.error("Error sending morning reminders: %s", e, exc_info=True)
