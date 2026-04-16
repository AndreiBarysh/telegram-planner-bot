"""Initial migration — create all tables.

Revision ID: 001
Revises: None
Create Date: 2026-04-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("first_name", sa.String(255), server_default=""),
        sa.Column("timezone", sa.String(50), server_default="Europe/Moscow"),
        sa.Column("language", sa.String(10), server_default="ru"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Projects
    op.create_table(
        "projects",
        sa.Column("project_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color_emoji", sa.String(10), server_default="📁"),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])

    # Tasks
    priority_enum = sa.Enum("HIGH", "MEDIUM", "LOW", name="priority")
    status_enum = sa.Enum("active", "completed", "cancelled", name="taskstatus")

    op.create_table(
        "tasks",
        sa.Column("task_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.project_id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", priority_enum, server_default="MEDIUM"),
        sa.Column("status", status_enum, server_default="active"),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])
    op.create_index("ix_tasks_user_status", "tasks", ["user_id", "status"])
    op.create_index("ix_tasks_user_due", "tasks", ["user_id", "due_date"])
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])

    # Task tags
    op.create_table(
        "task_tags",
        sa.Column("tag_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag_name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_task_tags_user_id", "task_tags", ["user_id"])
    op.create_index("ix_task_tags_task_id", "task_tags", ["task_id"])

    # Reminders
    reminder_type_enum = sa.Enum("before_due", "custom", "daily_morning", name="remindertype")

    op.create_table(
        "reminders",
        sa.Column("reminder_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False),
        sa.Column("reminder_time", sa.DateTime(), nullable=False),
        sa.Column("reminder_type", reminder_type_enum, server_default="custom"),
        sa.Column("is_sent", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_reminders_user_id", "reminders", ["user_id"])
    op.create_index("ix_reminders_time_sent", "reminders", ["reminder_time", "is_sent"])

    # User settings
    op.create_table(
        "user_settings",
        sa.Column("setting_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.user_id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("notifications_enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("morning_reminder_time", sa.String(5), server_default="08:00"),
        sa.Column("default_priority", priority_enum, server_default="MEDIUM"),
        sa.Column("language", sa.String(10), server_default="ru"),
        sa.Column("date_format", sa.String(20), server_default="DD.MM.YYYY"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_user_settings_user_id", "user_settings", ["user_id"])


def downgrade() -> None:
    op.drop_table("user_settings")
    op.drop_table("reminders")
    op.drop_table("task_tags")
    op.drop_table("tasks")
    op.drop_table("projects")
    op.drop_table("users")

    # Drop enums
    sa.Enum(name="priority").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="taskstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="remindertype").drop(op.get_bind(), checkfirst=True)
