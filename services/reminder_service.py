import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Reminder, ReminderType, Task, TaskStatus

logger = logging.getLogger(__name__)


class ReminderService:
    """Business logic for reminder management."""

    @staticmethod
    async def create_reminder(
        session: AsyncSession,
        user_id: int,
        task_id: int,
        reminder_time: datetime,
        reminder_type: ReminderType = ReminderType.CUSTOM,
    ) -> Reminder | None:
        """Create a custom reminder for a task."""
        # Verify task belongs to user
        result = await session.execute(
            select(Task).where(Task.task_id == task_id, Task.user_id == user_id)
        )
        task = result.scalar_one_or_none()
        if task is None:
            return None

        reminder = Reminder(
            user_id=user_id,
            task_id=task_id,
            reminder_time=reminder_time,
            reminder_type=reminder_type,
        )
        session.add(reminder)
        await session.flush()
        logger.info(
            "Reminder created: id=%d user=%d task=%d at=%s",
            reminder.reminder_id, user_id, task_id, reminder_time,
        )
        return reminder

    @staticmethod
    async def list_reminders(
        session: AsyncSession,
        user_id: int,
        only_pending: bool = True,
    ) -> list[Reminder]:
        """List reminders for a user."""
        query = (
            select(Reminder)
            .options(selectinload(Reminder.task))
            .where(Reminder.user_id == user_id)
        )
        if only_pending:
            query = query.where(Reminder.is_sent == False)
        query = query.order_by(Reminder.reminder_time.asc())
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def cancel_reminder(
        session: AsyncSession,
        reminder_id: int,
        user_id: int,
    ) -> bool:
        """Cancel (delete) a reminder."""
        result = await session.execute(
            select(Reminder).where(
                Reminder.reminder_id == reminder_id,
                Reminder.user_id == user_id,
            )
        )
        reminder = result.scalar_one_or_none()
        if reminder is None:
            return False
        await session.delete(reminder)
        logger.info("Reminder cancelled: id=%d user=%d", reminder_id, user_id)
        return True

    @staticmethod
    async def get_due_reminders(session: AsyncSession) -> list[Reminder]:
        """Get all reminders that are due and not yet sent."""
        now = datetime.utcnow()
        result = await session.execute(
            select(Reminder)
            .options(selectinload(Reminder.task), selectinload(Reminder.user))
            .where(
                Reminder.reminder_time <= now,
                Reminder.is_sent == False,
            )
            .order_by(Reminder.reminder_time.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def mark_sent(session: AsyncSession, reminder_id: int) -> None:
        """Mark a reminder as sent."""
        result = await session.execute(
            select(Reminder).where(Reminder.reminder_id == reminder_id)
        )
        reminder = result.scalar_one_or_none()
        if reminder:
            reminder.is_sent = True
            logger.info("Reminder marked as sent: id=%d", reminder_id)

    @staticmethod
    async def get_morning_tasks(
        session: AsyncSession,
        user_id: int,
    ) -> list[Task]:
        """Get active tasks due today for morning reminder."""
        now = datetime.utcnow()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta
        end = start + timedelta(days=1)

        result = await session.execute(
            select(Task)
            .options(selectinload(Task.project))
            .where(
                Task.user_id == user_id,
                Task.status == TaskStatus.ACTIVE,
                Task.due_date >= start,
                Task.due_date < end,
            )
            .order_by(Task.priority.asc(), Task.due_date.asc())
        )
        return list(result.scalars().all())
