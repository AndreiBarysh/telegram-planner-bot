import logging
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Priority, Task, TaskStatus

logger = logging.getLogger(__name__)


class StatsService:
    """Business logic for statistics and analytics."""

    @staticmethod
    async def get_basic_stats(session: AsyncSession, user_id: int) -> dict:
        """Get basic statistics for the user."""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)

        # Total tasks
        total_result = await session.execute(
            select(func.count(Task.task_id)).where(Task.user_id == user_id)
        )
        total = total_result.scalar() or 0

        # Active tasks
        active_result = await session.execute(
            select(func.count(Task.task_id)).where(
                Task.user_id == user_id, Task.status == TaskStatus.ACTIVE
            )
        )
        active = active_result.scalar() or 0

        # Completed tasks
        completed_result = await session.execute(
            select(func.count(Task.task_id)).where(
                Task.user_id == user_id, Task.status == TaskStatus.COMPLETED
            )
        )
        completed = completed_result.scalar() or 0

        # Completed today
        completed_today_result = await session.execute(
            select(func.count(Task.task_id)).where(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED,
                Task.completed_at >= today_start,
                Task.completed_at < today_end,
            )
        )
        completed_today = completed_today_result.scalar() or 0

        # Tasks due today
        due_today_result = await session.execute(
            select(func.count(Task.task_id)).where(
                Task.user_id == user_id,
                Task.due_date >= today_start,
                Task.due_date < today_end,
            )
        )
        due_today = due_today_result.scalar() or 0

        # Completed this week
        completed_week_result = await session.execute(
            select(func.count(Task.task_id)).where(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED,
                Task.completed_at >= week_start,
            )
        )
        completed_week = completed_week_result.scalar() or 0

        # Completed this month
        completed_month_result = await session.execute(
            select(func.count(Task.task_id)).where(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED,
                Task.completed_at >= month_start,
            )
        )
        completed_month = completed_month_result.scalar() or 0

        # Overdue
        overdue_result = await session.execute(
            select(func.count(Task.task_id)).where(
                Task.user_id == user_id,
                Task.status == TaskStatus.ACTIVE,
                Task.due_date < now,
                Task.due_date.isnot(None),
            )
        )
        overdue = overdue_result.scalar() or 0

        # Average completion time (hours)
        avg_time = await StatsService._avg_completion_time(session, user_id)

        return {
            "total": total,
            "active": active,
            "completed": completed,
            "completed_today": completed_today,
            "due_today": due_today,
            "completed_week": completed_week,
            "completed_month": completed_month,
            "overdue": overdue,
            "avg_completion_hours": avg_time,
        }

    @staticmethod
    async def get_detailed_stats(session: AsyncSession, user_id: int) -> dict:
        """Get detailed analytics for the last 30 days."""
        now = datetime.utcnow()
        thirty_days_ago = now - timedelta(days=30)

        # Daily completion counts for chart
        result = await session.execute(
            select(Task).where(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED,
                Task.completed_at >= thirty_days_ago,
            )
        )
        completed_tasks = result.scalars().all()

        daily_counts: dict[str, int] = defaultdict(int)
        for task in completed_tasks:
            if task.completed_at:
                day_key = task.completed_at.strftime("%Y-%m-%d")
                daily_counts[day_key] += 1

        # Fill in missing days with 0
        daily_chart: list[tuple[str, int]] = []
        for i in range(30):
            day = (thirty_days_ago + timedelta(days=i)).strftime("%Y-%m-%d")
            daily_chart.append((day, daily_counts.get(day, 0)))

        # By priority distribution
        priority_result = await session.execute(
            select(Task.priority, func.count(Task.task_id))
            .where(Task.user_id == user_id)
            .group_by(Task.priority)
        )
        by_priority = {row[0]: row[1] for row in priority_result.all()}

        # Most productive day of week
        weekday_counts: dict[int, int] = defaultdict(int)
        for task in completed_tasks:
            if task.completed_at:
                weekday_counts[task.completed_at.weekday()] += 1

        most_productive_day = None
        if weekday_counts:
            best_day = max(weekday_counts, key=weekday_counts.get)
            day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
            most_productive_day = day_names[best_day]

        # Completed vs overdue ratio
        all_with_due = await session.execute(
            select(Task).where(
                Task.user_id == user_id,
                Task.due_date.isnot(None),
                Task.status.in_([TaskStatus.COMPLETED, TaskStatus.ACTIVE]),
            )
        )
        tasks_with_due = all_with_due.scalars().all()
        on_time = sum(
            1 for t in tasks_with_due
            if t.status == TaskStatus.COMPLETED and t.completed_at and t.due_date and t.completed_at <= t.due_date
        )
        late = sum(
            1 for t in tasks_with_due
            if t.status == TaskStatus.COMPLETED and t.completed_at and t.due_date and t.completed_at > t.due_date
        )

        return {
            "daily_chart": daily_chart,
            "by_priority": by_priority,
            "most_productive_day": most_productive_day,
            "on_time": on_time,
            "late": late,
            "weekday_counts": dict(weekday_counts),
        }

    @staticmethod
    async def get_productivity_report(
        session: AsyncSession,
        user_id: int,
        period: str = "week",
    ) -> dict:
        """Generate productivity report for a given period."""
        now = datetime.utcnow()
        if period == "day":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start = now - timedelta(days=7)
        elif period == "month":
            start = now - timedelta(days=30)
        elif period == "quarter":
            start = now - timedelta(days=90)
        else:
            start = now - timedelta(days=7)

        # Previous period for trend comparison
        period_length = (now - start).days
        prev_start = start - timedelta(days=period_length)

        # Current period completed
        current_result = await session.execute(
            select(func.count(Task.task_id)).where(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED,
                Task.completed_at >= start,
            )
        )
        current_completed = current_result.scalar() or 0

        # Previous period completed
        prev_result = await session.execute(
            select(func.count(Task.task_id)).where(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED,
                Task.completed_at >= prev_start,
                Task.completed_at < start,
            )
        )
        prev_completed = prev_result.scalar() or 0

        # Trend
        if prev_completed > 0:
            trend_pct = round(((current_completed - prev_completed) / prev_completed) * 100)
        else:
            trend_pct = 100 if current_completed > 0 else 0

        avg_time = await StatsService._avg_completion_time(session, user_id, since=start)

        return {
            "period": period,
            "start": start,
            "end": now,
            "completed": current_completed,
            "prev_completed": prev_completed,
            "trend_pct": trend_pct,
            "avg_completion_hours": avg_time,
        }

    @staticmethod
    async def _avg_completion_time(
        session: AsyncSession,
        user_id: int,
        since: datetime | None = None,
    ) -> float:
        """Calculate average task completion time in hours."""
        query = select(Task).where(
            Task.user_id == user_id,
            Task.status == TaskStatus.COMPLETED,
            Task.completed_at.isnot(None),
        )
        if since:
            query = query.where(Task.completed_at >= since)

        result = await session.execute(query)
        tasks = result.scalars().all()

        if not tasks:
            return 0.0

        total_hours = 0.0
        count = 0
        for task in tasks:
            if task.completed_at and task.created_at:
                delta = task.completed_at - task.created_at
                total_hours += delta.total_seconds() / 3600
                count += 1

        return round(total_hours / count, 1) if count > 0 else 0.0
