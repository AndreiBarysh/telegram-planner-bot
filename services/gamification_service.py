"""Gamification system — levels, achievements, streaks."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Task, TaskStatus

logger = logging.getLogger(__name__)

# ─── LEVEL SYSTEM ─────────────────────────────────────────────────────────────

LEVELS = [
    (0, "🌱 Новичок"),
    (5, "📝 Планировщик"),
    (15, "⚡ Продуктивный"),
    (30, "🔥 Мастер задач"),
    (50, "💎 Эксперт"),
    (100, "🏆 Легенда"),
    (200, "👑 Гранд-мастер"),
]

XP_PER_TASK = 10
XP_PER_HIGH_PRIORITY = 5  # bonus
XP_PER_ON_TIME = 3  # bonus for completing before deadline
XP_PER_STREAK_DAY = 2  # bonus per day of streak


def get_level(total_completed: int) -> tuple[int, str, int, int]:
    """Get current level info. Returns (level_index, level_name, current_xp, next_level_xp)."""
    level_idx = 0
    level_name = LEVELS[0][1]

    for i, (threshold, name) in enumerate(LEVELS):
        if total_completed >= threshold:
            level_idx = i
            level_name = name

    # Next level threshold
    if level_idx + 1 < len(LEVELS):
        next_threshold = LEVELS[level_idx + 1][0]
    else:
        next_threshold = total_completed  # max level

    current_threshold = LEVELS[level_idx][0]
    return level_idx, level_name, total_completed - current_threshold, next_threshold - current_threshold


# ─── ACHIEVEMENTS ─────────────────────────────────────────────────────────────

ACHIEVEMENTS = [
    {
        "id": "first_task",
        "name": "🎯 Первый шаг",
        "desc": "Завершите первую задачу",
        "check": lambda stats: stats["total_completed"] >= 1,
    },
    {
        "id": "five_tasks",
        "name": "✋ Пятёрка",
        "desc": "Завершите 5 задач",
        "check": lambda stats: stats["total_completed"] >= 5,
    },
    {
        "id": "ten_tasks",
        "name": "🔟 Десятка",
        "desc": "Завершите 10 задач",
        "check": lambda stats: stats["total_completed"] >= 10,
    },
    {
        "id": "fifty_tasks",
        "name": "🌟 Полтинник",
        "desc": "Завершите 50 задач",
        "check": lambda stats: stats["total_completed"] >= 50,
    },
    {
        "id": "hundred_tasks",
        "name": "💯 Сотня",
        "desc": "Завершите 100 задач",
        "check": lambda stats: stats["total_completed"] >= 100,
    },
    {
        "id": "streak_3",
        "name": "🔥 3 дня подряд",
        "desc": "Выполняйте задачи 3 дня подряд",
        "check": lambda stats: stats["streak"] >= 3,
    },
    {
        "id": "streak_7",
        "name": "🔥🔥 Неделя огня",
        "desc": "Выполняйте задачи 7 дней подряд",
        "check": lambda stats: stats["streak"] >= 7,
    },
    {
        "id": "streak_30",
        "name": "🔥🔥🔥 Месяц в деле",
        "desc": "Выполняйте задачи 30 дней подряд",
        "check": lambda stats: stats["streak"] >= 30,
    },
    {
        "id": "five_in_day",
        "name": "⚡ Молния",
        "desc": "Завершите 5 задач за один день",
        "check": lambda stats: stats["max_per_day"] >= 5,
    },
    {
        "id": "all_high",
        "name": "🎖 Боец",
        "desc": "Завершите 10 задач с приоритетом HIGH",
        "check": lambda stats: stats["high_completed"] >= 10,
    },
    {
        "id": "on_time_10",
        "name": "⏰ Пунктуальный",
        "desc": "Завершите 10 задач до дедлайна",
        "check": lambda stats: stats["on_time"] >= 10,
    },
    {
        "id": "first_project",
        "name": "📁 Организатор",
        "desc": "Создайте первый проект",
        "check": lambda stats: stats["projects"] >= 1,
    },
]


class GamificationService:
    """Business logic for gamification features."""

    @staticmethod
    async def get_user_stats(session: AsyncSession, user_id: int) -> dict:
        """Calculate all gamification-relevant stats for a user."""
        from database.models import Priority, Project

        # Total completed
        result = await session.execute(
            select(func.count(Task.task_id)).where(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED,
            )
        )
        total_completed = result.scalar() or 0

        # High priority completed
        result = await session.execute(
            select(func.count(Task.task_id)).where(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED,
                Task.priority == Priority.HIGH,
            )
        )
        high_completed = result.scalar() or 0

        # On time completed (before deadline)
        result = await session.execute(
            select(Task).where(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED,
                Task.due_date.isnot(None),
                Task.completed_at.isnot(None),
            )
        )
        tasks_with_due = result.scalars().all()
        on_time = sum(1 for t in tasks_with_due if t.completed_at <= t.due_date)

        # Streak calculation
        streak = await GamificationService._calculate_streak(session, user_id)

        # Max tasks per day
        max_per_day = await GamificationService._max_tasks_per_day(session, user_id)

        # Projects count
        result = await session.execute(
            select(func.count(Project.project_id)).where(Project.user_id == user_id)
        )
        projects = result.scalar() or 0

        return {
            "total_completed": total_completed,
            "high_completed": high_completed,
            "on_time": on_time,
            "streak": streak,
            "max_per_day": max_per_day,
            "projects": projects,
        }

    @staticmethod
    async def _calculate_streak(session: AsyncSession, user_id: int) -> int:
        """Calculate current streak of consecutive days with completed tasks."""
        result = await session.execute(
            select(Task.completed_at).where(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED,
                Task.completed_at.isnot(None),
            ).order_by(Task.completed_at.desc())
        )
        dates = result.scalars().all()
        if not dates:
            return 0

        # Get unique days
        unique_days = sorted(set(d.date() for d in dates), reverse=True)
        if not unique_days:
            return 0

        today = datetime.utcnow().date()
        # Streak must include today or yesterday
        if unique_days[0] < today - timedelta(days=1):
            return 0

        streak = 1
        for i in range(1, len(unique_days)):
            if unique_days[i - 1] - unique_days[i] == timedelta(days=1):
                streak += 1
            else:
                break

        return streak

    @staticmethod
    async def _max_tasks_per_day(session: AsyncSession, user_id: int) -> int:
        """Find the maximum number of tasks completed in a single day."""
        result = await session.execute(
            select(Task.completed_at).where(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED,
                Task.completed_at.isnot(None),
            )
        )
        dates = result.scalars().all()
        if not dates:
            return 0

        from collections import Counter
        day_counts = Counter(d.date() for d in dates)
        return max(day_counts.values()) if day_counts else 0

    @staticmethod
    async def get_profile(session: AsyncSession, user_id: int) -> dict:
        """Get full gamification profile."""
        stats = await GamificationService.get_user_stats(session, user_id)

        level_idx, level_name, current_xp, needed_xp = get_level(stats["total_completed"])

        unlocked = []
        locked = []
        for ach in ACHIEVEMENTS:
            if ach["check"](stats):
                unlocked.append(ach)
            else:
                locked.append(ach)

        return {
            "level_idx": level_idx,
            "level_name": level_name,
            "current_xp": current_xp,
            "needed_xp": needed_xp,
            "total_completed": stats["total_completed"],
            "streak": stats["streak"],
            "unlocked": unlocked,
            "locked": locked,
            "stats": stats,
        }

    @staticmethod
    async def check_new_achievements(session: AsyncSession, user_id: int, old_stats: dict | None = None) -> list[dict]:
        """Check if user earned new achievements since last check."""
        stats = await GamificationService.get_user_stats(session, user_id)
        new_achievements = []

        for ach in ACHIEVEMENTS:
            is_unlocked = ach["check"](stats)
            was_unlocked = ach["check"](old_stats) if old_stats else False
            if is_unlocked and not was_unlocked:
                new_achievements.append(ach)

        return new_achievements
