import logging
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Priority, Project, Task, TaskStatus

logger = logging.getLogger(__name__)


class ProjectService:
    """Business logic for project management."""

    @staticmethod
    async def create_project(
        session: AsyncSession,
        user_id: int,
        name: str,
        description: str | None = None,
        color_emoji: str = "📁",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> Project:
        """Create a new project."""
        project = Project(
            user_id=user_id,
            name=name,
            description=description,
            color_emoji=color_emoji,
            start_date=start_date,
            end_date=end_date,
        )
        session.add(project)
        await session.flush()
        logger.info("Project created: id=%d user=%d name=%s", project.project_id, user_id, name)
        return project

    @staticmethod
    async def get_project(session: AsyncSession, project_id: int, user_id: int) -> Project | None:
        """Get a project by ID for a specific user."""
        result = await session.execute(
            select(Project)
            .options(selectinload(Project.tasks))
            .where(Project.project_id == project_id, Project.user_id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_projects(session: AsyncSession, user_id: int) -> list[Project]:
        """List all projects for a user."""
        result = await session.execute(
            select(Project)
            .options(selectinload(Project.tasks))
            .where(Project.user_id == user_id)
            .order_by(Project.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def update_project(
        session: AsyncSession,
        project_id: int,
        user_id: int,
        **kwargs,
    ) -> Project | None:
        """Update project fields."""
        project = await ProjectService.get_project(session, project_id, user_id)
        if project is None:
            return None
        for key, value in kwargs.items():
            if hasattr(project, key) and value is not None:
                setattr(project, key, value)
        project.updated_at = datetime.utcnow()
        logger.info("Project updated: id=%d fields=%s", project_id, list(kwargs.keys()))
        return project

    @staticmethod
    async def delete_project(
        session: AsyncSession,
        project_id: int,
        user_id: int,
        delete_tasks: bool = False,
    ) -> bool:
        """Delete a project. Optionally delete its tasks or just unlink them."""
        project = await ProjectService.get_project(session, project_id, user_id)
        if project is None:
            return False

        if not delete_tasks:
            # Unlink tasks from project
            for task in project.tasks:
                task.project_id = None
            await session.flush()

        await session.delete(project)
        logger.info("Project deleted: id=%d user=%d delete_tasks=%s", project_id, user_id, delete_tasks)
        return True

    @staticmethod
    async def get_project_stats(
        session: AsyncSession,
        project_id: int,
        user_id: int,
    ) -> dict | None:
        """Calculate statistics for a project."""
        project = await ProjectService.get_project(session, project_id, user_id)
        if project is None:
            return None

        tasks = project.tasks
        total = len(tasks)
        if total == 0:
            return {
                "project": project,
                "total": 0,
                "active": 0,
                "completed": 0,
                "cancelled": 0,
                "overdue": 0,
                "progress": 0,
                "by_priority": {Priority.HIGH: 0, Priority.MEDIUM: 0, Priority.LOW: 0},
            }

        now = datetime.utcnow()
        active = sum(1 for t in tasks if t.status == TaskStatus.ACTIVE)
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        cancelled = sum(1 for t in tasks if t.status == TaskStatus.CANCELLED)
        overdue = sum(
            1 for t in tasks
            if t.status == TaskStatus.ACTIVE and t.due_date and t.due_date < now
        )

        by_priority = {p: 0 for p in Priority}
        for t in tasks:
            by_priority[t.priority] += 1

        progress = round((completed / total) * 100) if total > 0 else 0

        return {
            "project": project,
            "total": total,
            "active": active,
            "completed": completed,
            "cancelled": cancelled,
            "overdue": overdue,
            "progress": progress,
            "by_priority": by_priority,
        }
