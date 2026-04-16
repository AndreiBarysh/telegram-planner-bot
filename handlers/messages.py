"""Handlers for free-text messages and conversation flows."""

import logging
import re

from telegram import Update
from telegram.ext import ContextTypes

from database.db import get_session
from database.models import Priority
from services.task_service import TaskService
from services.project_service import ProjectService
from utils.formatters import format_task_detail
from utils.keyboards import (
    main_menu_keyboard,
    reply_main_keyboard,
    task_actions_keyboard,
)
from utils.validators import (
    validate_date,
    validate_description,
    validate_emoji,
    validate_tags,
    validate_title,
)

logger = logging.getLogger(__name__)


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text messages — dispatches based on awaiting state or reply keyboard."""
    text = update.message.text.strip()
    user_id = update.effective_user.id

    # Check if we are awaiting input for an edit flow
    awaiting = context.user_data.get("awaiting")
    if awaiting:
        await _handle_awaiting_input(update, context, awaiting, text, user_id)
        return

    # Handle reply keyboard shortcuts
    await _handle_reply_keyboard(update, context, text)


async def _handle_awaiting_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    awaiting: str,
    text: str,
    user_id: int,
) -> None:
    """Process text input when the bot is waiting for a specific value."""
    # Clear awaiting state
    context.user_data.pop("awaiting", None)

    if awaiting == "edit_title":
        task_id = context.user_data.pop("editing_task", None)
        if task_id is None:
            return
        valid, result = validate_title(text)
        if not valid:
            await update.message.reply_text(f"❌ {result}")
            return
        async with get_session() as session:
            task = await TaskService.update_task(session, task_id, user_id, title=result)
            if task:
                await update.message.reply_text(
                    f"✅ Название изменено: {task.title}",
                    reply_markup=task_actions_keyboard(task_id),
                )
            else:
                await update.message.reply_text("❌ Задача не найдена.")

    elif awaiting == "edit_desc":
        task_id = context.user_data.pop("editing_task", None)
        if task_id is None:
            return
        desc = None if text.lower() in ("нет", "no", "-") else text
        if desc:
            valid, desc = validate_description(desc)
            if not valid:
                await update.message.reply_text(f"❌ {desc}")
                return
        async with get_session() as session:
            task = await TaskService.update_task(session, task_id, user_id, description=desc)
            if task:
                await update.message.reply_text(
                    "✅ Описание обновлено.",
                    reply_markup=task_actions_keyboard(task_id),
                )
            else:
                await update.message.reply_text("❌ Задача не найдена.")

    elif awaiting == "edit_due":
        task_id = context.user_data.pop("editing_task", None)
        if task_id is None:
            return
        if text.lower() in ("нет", "no", "-"):
            due_date = None
        else:
            valid, result = validate_date(text)
            if not valid:
                await update.message.reply_text(f"❌ {result}")
                return
            due_date = result

        async with get_session() as session:
            task = await TaskService.update_task(session, task_id, user_id, due_date=due_date)
            if task:
                if due_date:
                    await update.message.reply_text(
                        f"✅ Дедлайн: {due_date.strftime('%d.%m.%Y %H:%M')}",
                        reply_markup=task_actions_keyboard(task_id),
                    )
                else:
                    await update.message.reply_text(
                        "✅ Дедлайн удалён.",
                        reply_markup=task_actions_keyboard(task_id),
                    )
            else:
                await update.message.reply_text("❌ Задача не найдена.")

    elif awaiting == "edit_tags":
        task_id = context.user_data.pop("editing_task", None)
        if task_id is None:
            return
        if text.lower() in ("нет", "no", "-"):
            # Remove all tags
            async with get_session() as session:
                task = await TaskService.get_task(session, task_id, user_id)
                if task:
                    for tag in list(task.tags):
                        await session.delete(tag)
                    await update.message.reply_text(
                        "✅ Теги удалены.",
                        reply_markup=task_actions_keyboard(task_id),
                    )
        else:
            valid, tags = validate_tags(text)
            if not valid:
                await update.message.reply_text(f"❌ {tags}")
                return
            async with get_session() as session:
                task = await TaskService.get_task(session, task_id, user_id)
                if task:
                    # Replace all tags
                    from database.models import TaskTag
                    for tag in list(task.tags):
                        await session.delete(tag)
                    for tag_name in tags:
                        session.add(TaskTag(
                            user_id=user_id,
                            task_id=task_id,
                            tag_name=tag_name,
                        ))
                    await update.message.reply_text(
                        f"✅ Теги обновлены: {', '.join(f'#{t}' for t in tags)}",
                        reply_markup=task_actions_keyboard(task_id),
                    )

    elif awaiting == "gcal_auth_code":
        from services.google_calendar_service import complete_auth
        success = complete_auth(user_id, text.strip())
        if success:
            await update.message.reply_text("✅ Google Calendar подключён! Используйте /gcal_sync для синхронизации.")
        else:
            await update.message.reply_text("❌ Не удалось авторизоваться. Попробуйте /gcal_connect заново.")

    elif awaiting == "create_project_name":
        valid, result = validate_title(text)
        if not valid:
            await update.message.reply_text(f"❌ {result}")
            return
        async with get_session() as session:
            from handlers.commands import _ensure_user
            await _ensure_user(session, update)
            project = await ProjectService.create_project(
                session, user_id, result
            )
            from utils.keyboards import project_view_keyboard
            await update.message.reply_text(
                f"✅ Проект создан!\n\n"
                f"📁 {project.name}\n"
                f"📌 ID: {project.project_id}\n\n"
                f"Теперь вы можете добавлять задачи в этот проект.",
                reply_markup=project_view_keyboard(project.project_id),
            )

    elif awaiting == "editproj_name":
        project_id = context.user_data.pop("editing_project", None)
        if project_id is None:
            return
        valid, result = validate_title(text)
        if not valid:
            await update.message.reply_text(f"❌ {result}")
            return
        async with get_session() as session:
            project = await ProjectService.update_project(session, project_id, user_id, name=result)
            if project:
                await update.message.reply_text(f"✅ Название проекта: {project.name}")
            else:
                await update.message.reply_text("❌ Проект не найден.")

    elif awaiting == "editproj_desc":
        project_id = context.user_data.pop("editing_project", None)
        if project_id is None:
            return
        desc = None if text.lower() in ("нет", "no", "-") else text
        async with get_session() as session:
            project = await ProjectService.update_project(
                session, project_id, user_id, description=desc
            )
            if project:
                await update.message.reply_text("✅ Описание проекта обновлено.")
            else:
                await update.message.reply_text("❌ Проект не найден.")

    elif awaiting == "editproj_emoji":
        project_id = context.user_data.pop("editing_project", None)
        if project_id is None:
            return
        valid, emoji = validate_emoji(text)
        if not valid:
            await update.message.reply_text(f"❌ {emoji}")
            return
        async with get_session() as session:
            project = await ProjectService.update_project(
                session, project_id, user_id, color_emoji=emoji
            )
            if project:
                await update.message.reply_text(f"✅ Эмодзи проекта: {emoji}")
            else:
                await update.message.reply_text("❌ Проект не найден.")

    elif awaiting == "setting_morning_time":
        # Validate HH:MM format
        match = re.match(r"^(\d{1,2}):(\d{2})$", text)
        if not match:
            await update.message.reply_text("❌ Формат: ЧЧ:ММ (например, 08:00)")
            return
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            await update.message.reply_text("❌ Неверное время.")
            return

        async with get_session() as session:
            from sqlalchemy import select
            from database.models import UserSettings
            result = await session.execute(
                select(UserSettings).where(UserSettings.user_id == user_id)
            )
            settings = result.scalar_one_or_none()
            if settings:
                settings.morning_reminder_time = f"{hour:02d}:{minute:02d}"
                await update.message.reply_text(
                    f"✅ Утреннее напоминание: {hour:02d}:{minute:02d}"
                )

    else:
        await update.message.reply_text("Не понял. Используйте /help для справки.")


async def _handle_reply_keyboard(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
) -> None:
    """Handle taps on the persistent reply keyboard."""
    from handlers.commands import (
        list_tasks_command,
        list_projects_command,
        stats_command,
        calendar_command,
    )

    if text == "📋 Задачи":
        await list_tasks_command(update, context)
    elif text == "📁 Проекты":
        await list_projects_command(update, context)
    elif text == "📊 Статистика":
        await stats_command(update, context)
    elif text == "📅 Календарь":
        await calendar_command(update, context)
    elif text == "➕ Новая задача":
        context.user_data["awaiting"] = "quick_add_task"
        await update.message.reply_text("📝 Введите название новой задачи:")
    elif text == "⚙️ Настройки":
        async with get_session() as session:
            from sqlalchemy import select
            from database.models import UserSettings
            from handlers.commands import _ensure_user
            await _ensure_user(session, update)
            result = await session.execute(
                select(UserSettings).where(
                    UserSettings.user_id == update.effective_user.id
                )
            )
            settings = result.scalar_one_or_none()
            if settings:
                from utils.keyboards import settings_keyboard
                await update.message.reply_text(
                    "⚙️ Настройки:", reply_markup=settings_keyboard(settings)
                )
    elif context.user_data.get("awaiting") == "quick_add_task":
        context.user_data.pop("awaiting", None)
        valid, result = validate_title(text)
        if not valid:
            await update.message.reply_text(f"❌ {result}")
            return
        async with get_session() as session:
            from handlers.commands import _ensure_user
            await _ensure_user(session, update)
            task = await TaskService.create_task(
                session,
                user_id=update.effective_user.id,
                title=result,
            )
            await update.message.reply_text(
                f"✅ Задача добавлена!\n\n"
                f"📋 {task.title}\n"
                f"📌 ID: {task.task_id}",
                reply_markup=task_actions_keyboard(task.task_id),
            )
    else:
        await update.message.reply_text(
            "Не понял команду. Используйте /help или меню.",
            reply_markup=reply_main_keyboard(),
        )
