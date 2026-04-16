import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Priority, Task, TaskStatus, TaskTag, Reminder, ReminderType

logger = logging.getLogger(__name__)


class TaskService:
    """Business logic for task management."""

    @staticmethod
    async def create_task(
        session: AsyncSession,
        user_id: int,
        title: str,
        description: str | None = None,
        priority: Priority = Priority.MEDIUM,
        due_date: datetime | None = None,
        project_id: int | None = None,
        tags: list[str] | None = None,
    ) -> Task:
        """Create a new task and auto-create deadline reminders."""
        task = Task(
            user_id=user_id,
            title=title,
            description=description,
            priority=priority,
            status=TaskStatus.ACTIVE,
            due_date=due_date,
            project_id=project_id,
        )
        session.add(task)
        await session.flush()

        if tags:
            for tag_name in tags:
                tag = TaskTag(user_id=user_id, task_id=task.task_id, tag_name=tag_name.strip())
                session.add(tag)

        # Auto-create reminders for tasks with due dates
        if due_date:
            now = datetime.utcnow()
            for hours_before in [24, 1]:
                reminder_time = due_date - timedelta(hours=hours_before)
                if reminder_time > now:
                    reminder = Reminder(
                        user_id=user_id,
                        task_id=task.task_id,
                        reminder_time=reminder_time,
                        reminder_type=ReminderType.BEFORE_DUE,
                    )
                    session.add(reminder)

        logger.info("Task created: id=%d user=%d title=%s", task.task_id, user_id, title)
        return task

    @staticmethod
    async def get_task(session: AsyncSession, task_id: int, user_id: int) -> Task | None:
        """Get a single task by ID ensuring it belongs to the user."""
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.tags), selectinload(Task.project))
            .where(Task.task_id == task_id, Task.user_id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_tasks(
        session: AsyncSession,
        user_id: int,
        status: TaskStatus | None = None,
        priority: Priority | None = None,
        project_id: int | None = None,
        due_today: bool = False,
        due_this_week: bool = False,
        due_this_month: bool = False,
        sort_by: str = "due_date",
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[Task], int]:
        """List tasks with filters, sorting, and pagination. Returns (tasks, total_count)."""
        query = (
            select(Task)
            .options(selectinload(Task.tags), selectinload(Task.project))
            .where(Task.user_id == user_id)
        )
        count_query = select(func.count(Task.task_id)).where(Task.user_id == user_id)

        if status is not None:
            query = query.where(Task.status == status)
            count_query = count_query.where(Task.status == status)

        if priority is not None:
            query = query.where(Task.priority == priority)
            count_query = count_query.where(Task.priority == priority)

        if project_id is not None:
            query = query.where(Task.project_id == project_id)
            count_query = count_query.where(Task.project_id == project_id)

        now = datetime.utcnow()
        if due_today:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            query = query.where(Task.due_date >= start, Task.due_date < end)
            count_query = count_query.where(Task.due_date >= start, Task.due_date < end)
        elif due_this_week:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
            query = query.where(Task.due_date >= start, Task.due_date < end)
            count_query = count_query.where(Task.due_date >= start, Task.due_date < end)
        elif due_this_month:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=30)
            query = query.where(Task.due_date >= start, Task.due_date < end)
            count_query = count_query.where(Task.due_date >= start, Task.due_date < end)

        # Sorting
        if sort_by == "priority":
            query = query.order_by(Task.priority.asc(), Task.due_date.asc().nullslast())
        elif sort_by == "created":
            query = query.order_by(Task.created_at.desc())
        else:
            query = query.order_by(Task.due_date.asc().nullslast(), Task.priority.asc())

        # Total count
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        # Pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await session.execute(query)
        tasks = list(result.scalars().all())

        return tasks, total

    @staticmethod
    async def complete_task(session: AsyncSession, task_id: int, user_id: int) -> Task | None:
        """Mark a task as completed."""
        task = await TaskService.get_task(session, task_id, user_id)
        if task is None:
            return None
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()

        # Mark unsent reminders as sent
        result = await session.execute(
            select(Reminder).where(
                Reminder.task_id == task_id,
                Reminder.is_sent == False,
            )
        )
        for reminder in result.scalars().all():
            reminder.is_sent = True

        logger.info("Task completed: id=%d user=%d", task_id, user_id)
        return task

    @staticmethod
    async def delete_task(session: AsyncSession, task_id: int, user_id: int) -> bool:
        """Delete a task."""
        task = await TaskService.get_task(session, task_id, user_id)
        if task is None:
            return False
        await session.delete(task)
        logger.info("Task deleted: id=%d user=%d", task_id, user_id)
        return True

    @staticmethod
    async def update_task(
        session: AsyncSession,
        task_id: int,
        user_id: int,
        **kwargs,
    ) -> Task | None:
        """Update task fields."""
        task = await TaskService.get_task(session, task_id, user_id)
        if task is None:
            return None
        for key, value in kwargs.items():
            if hasattr(task, key) and value is not None:
                setattr(task, key, value)
        task.updated_at = datetime.utcnow()
        logger.info("Task updated: id=%d fields=%s", task_id, list(kwargs.keys()))
        return task

    @staticmethod
    async def search_tasks(
        session: AsyncSession,
        user_id: int,
        query: str,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[Task], int]:
        """Full-text search across task titles and descriptions."""
        pattern = f"%{query}%"
        base = select(Task).where(
            Task.user_id == user_id,
            or_(
                Task.title.ilike(pattern),
                Task.description.ilike(pattern),
            ),
        )
        count_q = select(func.count(Task.task_id)).where(
            Task.user_id == user_id,
            or_(
                Task.title.ilike(pattern),
                Task.description.ilike(pattern),
            ),
        )

        total_result = await session.execute(count_q)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await session.execute(
            base.options(selectinload(Task.tags), selectinload(Task.project))
            .order_by(Task.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        tasks = list(result.scalars().all())
        return tasks, total

    @staticmethod
    async def get_tasks_for_date(
        session: AsyncSession,
        user_id: int,
        date: datetime,
    ) -> list[Task]:
        """Get all tasks for a specific date."""
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.tags), selectinload(Task.project))
            .where(
                Task.user_id == user_id,
                Task.due_date >= start,
                Task.due_date < end,
            )
            .order_by(Task.priority.asc(), Task.due_date.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_overdue_tasks(session: AsyncSession, user_id: int) -> list[Task]:
        """Get all overdue active tasks."""
        now = datetime.utcnow()
        result = await session.execute(
            select(Task)
            .options(selectinload(Task.tags), selectinload(Task.project))
            .where(
                Task.user_id == user_id,
                Task.status == TaskStatus.ACTIVE,
                Task.due_date < now,
                Task.due_date.isnot(None),
            )
            .order_by(Task.due_date.asc())
        )
        return list(result.scalars().all())
