"""Callback query handlers for inline keyboard buttons."""

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from database.db import get_session
from database.models import Priority, TaskStatus
from services.task_service import TaskService
from services.project_service import ProjectService
from services.reminder_service import ReminderService
from services.stats_service import StatsService
from utils.formatters import (
    format_basic_stats,
    format_detailed_stats,
    format_productivity_report,
    format_project_list,
    format_reminder_list,
    format_task_detail,
    format_task_list,
)
from utils.keyboards import (
    calendar_keyboard,
    main_menu_keyboard,
    pagination_keyboard,
    priority_keyboard,
    project_select_keyboard,
    settings_keyboard,
    stats_keyboard,
    task_actions_keyboard,
    task_edit_keyboard,
    task_list_filter_keyboard,
)

logger = logging.getLogger(__name__)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route all callback queries to appropriate handlers."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data or data == "noop":
        return

    user_id = update.effective_user.id

    try:
        if data.startswith("menu:"):
            await _handle_menu(query, context, data, user_id)
        elif data.startswith("export:"):
            await _handle_export(query, context, data, user_id)
        elif data.startswith("task:"):
            await _handle_task_action(query, context, data, user_id)
        elif data.startswith("edit:"):
            await _handle_edit_field(query, context, data, user_id)
        elif data.startswith("setpriority:"):
            await _handle_set_priority(query, context, data, user_id)
        elif data.startswith("setproject:"):
            await _handle_set_project(query, context, data, user_id)
        elif data.startswith("filter:"):
            await _handle_filter(query, context, data, user_id)
        elif data.startswith("taskpage:"):
            await _handle_task_page(query, context, data, user_id)
        elif data.startswith("confirm_delete:"):
            await _handle_confirm_delete(query, context, data, user_id)
        elif data.startswith("cancel_delete:"):
            await query.edit_message_text("❌ Удаление отменено.")
        elif data.startswith("project:"):
            await _handle_project_action(query, context, data, user_id)
        elif data.startswith("delproj:"):
            await _handle_delete_project(query, context, data, user_id)
        elif data.startswith("editproj:"):
            await _handle_edit_project_field(query, context, data, user_id)
        elif data.startswith("cal:"):
            await _handle_calendar_nav(query, context, data, user_id)
        elif data.startswith("stats:"):
            await _handle_stats(query, context, data, user_id)
        elif data.startswith("report:"):
            await _handle_report(query, context, data, user_id)
        elif data.startswith("setting:"):
            await _handle_setting(query, context, data, user_id)
    except Exception as e:
        logger.error("Callback error: %s data=%s", e, data, exc_info=True)
        await query.edit_message_text("❌ Произошла ошибка. Попробуйте ещё раз.")


# ─── MENU ─────────────────────────────────────────────────────────────────────

async def _handle_menu(query, context, data: str, user_id: int) -> None:
    section = data.split(":")[1]

    if section == "main":
        await query.edit_message_text("📌 Главное меню:", reply_markup=main_menu_keyboard())

    elif section == "tasks":
        async with get_session() as session:
            tasks, total = await TaskService.list_tasks(
                session, user_id, status=TaskStatus.ACTIVE, page=1
            )
            text = format_task_list(tasks, total, page=1, page_size=10)
            await query.edit_message_text(text, reply_markup=task_list_filter_keyboard())

    elif section == "projects":
        async with get_session() as session:
            from utils.keyboards import projects_menu_keyboard
            projects = await ProjectService.list_projects(session, user_id)
            text = format_project_list(projects)
            await query.edit_message_text(text, reply_markup=projects_menu_keyboard(projects))

    elif section == "stats":
        async with get_session() as session:
            stats = await StatsService.get_basic_stats(session, user_id)
            text = format_basic_stats(stats)
            await query.edit_message_text(text, reply_markup=stats_keyboard())

    elif section == "reminders":
        async with get_session() as session:
            reminders = await ReminderService.list_reminders(session, user_id)
            text = format_reminder_list(reminders)
            await query.edit_message_text(text, reply_markup=main_menu_keyboard())

    elif section == "calendar":
        now = datetime.utcnow()
        from handlers.commands import _send_calendar
        # For callback, we need special handling
        await _handle_calendar_nav(query, context, f"cal:{now.year}:{now.month}", user_id)

    elif section == "profile":
        from services.gamification_service import GamificationService
        from utils.formatters import format_progress_bar
        async with get_session() as session:
            profile = await GamificationService.get_profile(session, user_id)

        lines = [
            f"🏆 ПРОФИЛЬ",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"\n🎖 Уровень: {profile['level_name']}",
            f"📊 {format_progress_bar(profile['current_xp'], profile['needed_xp'])} {profile['current_xp']}/{profile['needed_xp']}",
            f"✅ Выполнено: {profile['total_completed']}",
            f"🔥 Стрик: {profile['streak']} дн.",
            f"\n🏅 Достижений: {len(profile['unlocked'])}/{len(profile['unlocked']) + len(profile['locked'])}",
        ]
        if profile["unlocked"]:
            for ach in profile["unlocked"][-5:]:
                lines.append(f"  ✅ {ach['name']}")

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        buttons = [
            [InlineKeyboardButton("🏅 Все достижения", callback_data="menu:achievements")],
            [InlineKeyboardButton("◀️ Меню", callback_data="menu:main")],
        ]
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))

    elif section == "achievements":
        from services.gamification_service import GamificationService, ACHIEVEMENTS
        async with get_session() as session:
            stats = await GamificationService.get_user_stats(session, user_id)

        lines = ["🏅 ВСЕ ДОСТИЖЕНИЯ", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
        for ach in ACHIEVEMENTS:
            mark = "✅" if ach["check"](stats) else "🔒"
            lines.append(f"\n  {mark} {ach['name']}")
            lines.append(f"     {ach['desc']}")
        await query.edit_message_text("\n".join(lines), reply_markup=main_menu_keyboard())

    elif section == "export":
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        buttons = [
            [InlineKeyboardButton("📄 CSV", callback_data="export:csv")],
            [InlineKeyboardButton("📕 PDF", callback_data="export:pdf")],
            [InlineKeyboardButton("◀️ Меню", callback_data="menu:main")],
        ]
        await query.edit_message_text("📤 Выберите формат экспорта:", reply_markup=InlineKeyboardMarkup(buttons))

    elif section == "settings":
        async with get_session() as session:
            from sqlalchemy import select
            from database.models import UserSettings
            result = await session.execute(
                select(UserSettings).where(UserSettings.user_id == user_id)
            )
            settings = result.scalar_one_or_none()
            if settings:
                await query.edit_message_text(
                    "⚙️ Настройки:", reply_markup=settings_keyboard(settings)
                )


# ─── EXPORT ───────────────────────────────────────────────────────────────────

async def _handle_export(query, context, data: str, user_id: int) -> None:
    fmt = data.split(":")[1]

    async with get_session() as session:
        tasks, _ = await TaskService.list_tasks(session, user_id, page=1, page_size=9999)
        if not tasks:
            await query.edit_message_text("📋 Нет задач для экспорта.")
            return

    from datetime import datetime
    if fmt == "csv":
        from services.export_service import export_tasks_csv
        buf = export_tasks_csv(tasks)
        await query.message.reply_document(
            document=buf,
            filename=f"tasks_{datetime.utcnow().strftime('%Y%m%d')}.csv",
            caption=f"📊 Экспорт: {len(tasks)} задач",
        )
    elif fmt == "pdf":
        from services.export_service import export_tasks_pdf
        buf = export_tasks_pdf(tasks, title="Мои задачи")
        await query.message.reply_document(
            document=buf,
            filename=f"tasks_{datetime.utcnow().strftime('%Y%m%d')}.pdf",
            caption=f"📊 Экспорт: {len(tasks)} задач",
        )

    await query.edit_message_text("✅ Файл отправлен!")


# ─── TASK ACTIONS ─────────────────────────────────────────────────────────────

async def _handle_task_action(query, context, data: str, user_id: int) -> None:
    parts = data.split(":")
    action = parts[1]
    task_id = int(parts[2])

    if action == "complete":
        async with get_session() as session:
            # Save old stats for achievement comparison
            from services.gamification_service import GamificationService
            old_stats = await GamificationService.get_user_stats(session, user_id)

            task = await TaskService.complete_task(session, task_id, user_id)
            if task:
                text = f"✅ Задача «{task.title}» выполнена!"

                # Check new achievements
                new_achs = await GamificationService.check_new_achievements(session, user_id, old_stats)
                for ach in new_achs:
                    text += f"\n\n🏆 Новое достижение: {ach['name']}!\n   {ach['desc']}"

                await query.edit_message_text(text)
            else:
                await query.edit_message_text("❌ Задача не найдена.")

    elif action == "delete":
        from utils.keyboards import delete_confirm_keyboard
        await query.edit_message_text(
            "⚠️ Вы уверены, что хотите удалить эту задачу?",
            reply_markup=delete_confirm_keyboard("task", task_id),
        )

    elif action == "edit":
        await query.edit_message_text(
            "✏️ Выберите, что изменить:",
            reply_markup=task_edit_keyboard(task_id),
        )

    elif action == "detail":
        async with get_session() as session:
            task = await TaskService.get_task(session, task_id, user_id)
            if task:
                text = format_task_detail(task)
                await query.edit_message_text(
                    text, reply_markup=task_actions_keyboard(task_id)
                )
            else:
                await query.edit_message_text("❌ Задача не найдена.")


# ─── PROJECT ACTIONS ──────────────────────────────────────────────────────────

async def _handle_project_action(query, context, data: str, user_id: int) -> None:
    parts = data.split(":")
    action = parts[1]

    if action == "create":
        context.user_data["awaiting"] = "create_project_name"
        await query.edit_message_text("📁 Введите название нового проекта:")

    elif action == "view":
        project_id = int(parts[2])
        async with get_session() as session:
            stats = await ProjectService.get_project_stats(session, project_id, user_id)
            if stats is None:
                await query.edit_message_text("❌ Проект не найден.")
                return
            from utils.formatters import format_project_stats
            from utils.keyboards import project_view_keyboard
            text = format_project_stats(stats)
            await query.edit_message_text(text, reply_markup=project_view_keyboard(project_id))

    elif action == "tasks":
        project_id = int(parts[2])
        async with get_session() as session:
            tasks, total = await TaskService.list_tasks(
                session, user_id, project_id=project_id, page=1
            )
            project = await ProjectService.get_project(session, project_id, user_id)
            title = f"ЗАДАЧИ: {project.color_emoji} {project.name}" if project else "ЗАДАЧИ ПРОЕКТА"
            text = format_task_list(tasks, total, page=1, page_size=10, title=title)
            from utils.keyboards import project_view_keyboard
            await query.edit_message_text(text, reply_markup=project_view_keyboard(project_id))

    elif action == "stats":
        project_id = int(parts[2])
        async with get_session() as session:
            stats = await ProjectService.get_project_stats(session, project_id, user_id)
            if stats:
                from utils.formatters import format_project_stats
                from utils.keyboards import project_view_keyboard
                text = format_project_stats(stats)
                await query.edit_message_text(text, reply_markup=project_view_keyboard(project_id))
            else:
                await query.edit_message_text("❌ Проект не найден.")

    elif action == "edit":
        project_id = int(parts[2])
        context.user_data["editing_project"] = project_id
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        buttons = [
            [
                InlineKeyboardButton("📝 Название", callback_data=f"editproj:name:{project_id}"),
                InlineKeyboardButton("📄 Описание", callback_data=f"editproj:desc:{project_id}"),
            ],
            [
                InlineKeyboardButton("🎨 Эмодзи", callback_data=f"editproj:emoji:{project_id}"),
            ],
            [InlineKeyboardButton("◀️ Назад", callback_data=f"project:view:{project_id}")],
        ]
        await query.edit_message_text(
            "✏️ Выберите, что изменить:", reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif action == "delete":
        project_id = int(parts[2])
        from utils.keyboards import project_delete_keyboard
        await query.edit_message_text(
            "⚠️ Как удалить проект?", reply_markup=project_delete_keyboard(project_id)
        )


# ─── EDIT FIELD ───────────────────────────────────────────────────────────────

async def _handle_edit_field(query, context, data: str, user_id: int) -> None:
    parts = data.split(":")
    field = parts[1]
    task_id = int(parts[2])

    if field == "priority":
        await query.edit_message_text(
            "🎯 Выберите приоритет:", reply_markup=priority_keyboard(task_id)
        )

    elif field == "project":
        async with get_session() as session:
            projects = await ProjectService.list_projects(session, user_id)
            await query.edit_message_text(
                "📁 Выберите проект:",
                reply_markup=project_select_keyboard(projects, task_id),
            )

    elif field in ("title", "desc", "due", "tags"):
        # Store awaiting state for next text message
        context.user_data["awaiting"] = f"edit_{field}"
        context.user_data["editing_task"] = task_id
        prompts = {
            "title": "📝 Введите новое название:",
            "desc": "📄 Введите новое описание (или 'нет' для удаления):",
            "due": "⏰ Введите дедлайн (ДД.ММ.ГГГГ ЧЧ:ММ или 'нет' для удаления):",
            "tags": "🏷 Введите теги через запятую (или 'нет' для удаления):",
        }
        await query.edit_message_text(prompts[field])


# ─── SET PRIORITY ─────────────────────────────────────────────────────────────

async def _handle_set_priority(query, context, data: str, user_id: int) -> None:
    parts = data.split(":")
    priority_str = parts[1]
    task_id = int(parts[2])

    priority = Priority[priority_str]

    async with get_session() as session:
        task = await TaskService.update_task(session, task_id, user_id, priority=priority)
        if task:
            from utils.formatters import PRIORITY_EMOJI
            await query.edit_message_text(
                f"✅ Приоритет изменён на {PRIORITY_EMOJI[priority]} {priority_str}",
                reply_markup=task_actions_keyboard(task_id),
            )
        else:
            await query.edit_message_text("❌ Задача не найдена.")


# ─── SET PROJECT ──────────────────────────────────────────────────────────────

async def _handle_set_project(query, context, data: str, user_id: int) -> None:
    parts = data.split(":")
    project_id_str = parts[1]
    task_id = int(parts[2])

    project_id = None if project_id_str == "none" else int(project_id_str)

    async with get_session() as session:
        task = await TaskService.update_task(session, task_id, user_id, project_id=project_id)
        if task:
            label = "без проекта" if project_id is None else f"проект ID:{project_id}"
            await query.edit_message_text(
                f"✅ Задача назначена: {label}",
                reply_markup=task_actions_keyboard(task_id),
            )
        else:
            await query.edit_message_text("❌ Задача не найдена.")


# ─── FILTERS ──────────────────────────────────────────────────────────────────

async def _handle_filter(query, context, data: str, user_id: int) -> None:
    parts = data.split(":")
    filter_type = parts[1]
    value = parts[2]

    # Build filter params
    kwargs = {"page": 1}

    # Preserve existing filters
    filters = context.user_data.get("task_filters", {})

    if filter_type == "status":
        if value == "all":
            filters.pop("status", None)
        else:
            filters["status"] = TaskStatus(value)
    elif filter_type == "priority":
        filters["priority"] = Priority[value]
    elif filter_type == "period":
        filters.pop("due_today", None)
        filters.pop("due_this_week", None)
        filters.pop("due_this_month", None)
        if value == "today":
            filters["due_today"] = True
        elif value == "week":
            filters["due_this_week"] = True
        elif value == "month":
            filters["due_this_month"] = True
    elif filter_type == "sort":
        filters["sort_by"] = value

    context.user_data["task_filters"] = filters

    async with get_session() as session:
        tasks, total = await TaskService.list_tasks(session, user_id, **filters)
        text = format_task_list(tasks, total, page=1, page_size=10)
        keyboard = task_list_filter_keyboard()
        if total > 10:
            total_pages = (total + 9) // 10
            pag = pagination_keyboard(1, total_pages, prefix="taskpage")
            keyboard.inline_keyboard.extend(pag.inline_keyboard)
        await query.edit_message_text(text, reply_markup=keyboard)


# ─── PAGINATION ───────────────────────────────────────────────────────────────

async def _handle_task_page(query, context, data: str, user_id: int) -> None:
    page = int(data.split(":")[1])
    filters = context.user_data.get("task_filters", {})

    async with get_session() as session:
        tasks, total = await TaskService.list_tasks(session, user_id, page=page, **filters)
        text = format_task_list(tasks, total, page=page, page_size=10)
        keyboard = task_list_filter_keyboard()
        total_pages = (total + 9) // 10
        if total_pages > 1:
            pag = pagination_keyboard(page, total_pages, prefix="taskpage")
            keyboard.inline_keyboard.extend(pag.inline_keyboard)
        await query.edit_message_text(text, reply_markup=keyboard)


# ─── DELETE CONFIRM ───────────────────────────────────────────────────────────

async def _handle_confirm_delete(query, context, data: str, user_id: int) -> None:
    parts = data.split(":")
    entity = parts[1]
    entity_id = int(parts[2])

    if entity == "task":
        async with get_session() as session:
            deleted = await TaskService.delete_task(session, entity_id, user_id)
            if deleted:
                await query.edit_message_text("🗑 Задача удалена.")
            else:
                await query.edit_message_text("❌ Задача не найдена.")


# ─── DELETE PROJECT ───────────────────────────────────────────────────────────

async def _handle_delete_project(query, context, data: str, user_id: int) -> None:
    parts = data.split(":")
    mode = parts[1]  # "keep" or "all"
    project_id = int(parts[2])

    async with get_session() as session:
        deleted = await ProjectService.delete_project(
            session, project_id, user_id, delete_tasks=(mode == "all")
        )
        if deleted:
            msg = "🗑 Проект удалён"
            if mode == "all":
                msg += " вместе с задачами."
            else:
                msg += ". Задачи сохранены."
            await query.edit_message_text(msg)
        else:
            await query.edit_message_text("❌ Проект не найден.")


# ─── EDIT PROJECT FIELD ──────────────────────────────────────────────────────

async def _handle_edit_project_field(query, context, data: str, user_id: int) -> None:
    parts = data.split(":")
    field = parts[1]
    project_id = int(parts[2])

    context.user_data["awaiting"] = f"editproj_{field}"
    context.user_data["editing_project"] = project_id

    prompts = {
        "name": "📝 Введите новое название проекта:",
        "desc": "📄 Введите новое описание:",
        "emoji": "🎨 Введите эмодзи для проекта:",
    }
    await query.edit_message_text(prompts.get(field, "Введите значение:"))


# ─── CALENDAR NAV ────────────────────────────────────────────────────────────

async def _handle_calendar_nav(query, context, data: str, user_id: int) -> None:
    parts = data.split(":")
    year = int(parts[1])
    month = int(parts[2])

    from utils.date_utils import get_month_bounds
    from utils.formatters import format_calendar
    from database.models import Task, TaskStatus

    start, end = get_month_bounds(year, month)

    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(Task).where(
                Task.user_id == user_id,
                Task.due_date >= start,
                Task.due_date <= end,
            )
        )
        tasks = result.scalars().all()

    task_days = set()
    deadline_days = set()
    completed_days = set()
    now = datetime.utcnow()

    for t in tasks:
        if t.due_date:
            day = t.due_date.day
            if t.status == TaskStatus.COMPLETED:
                completed_days.add(day)
            elif t.status == TaskStatus.ACTIVE and t.due_date < now:
                deadline_days.add(day)
            else:
                task_days.add(day)

    text = format_calendar(year, month, task_days, deadline_days, completed_days)
    await query.edit_message_text(text, reply_markup=calendar_keyboard(year, month))


# ─── STATS ────────────────────────────────────────────────────────────────────

async def _handle_stats(query, context, data: str, user_id: int) -> None:
    mode = data.split(":")[1]

    async with get_session() as session:
        if mode == "basic":
            stats = await StatsService.get_basic_stats(session, user_id)
            text = format_basic_stats(stats)
        else:
            basic = await StatsService.get_basic_stats(session, user_id)
            detailed = await StatsService.get_detailed_stats(session, user_id)
            text = format_detailed_stats(basic, detailed)

    await query.edit_message_text(text, reply_markup=stats_keyboard())


async def _handle_report(query, context, data: str, user_id: int) -> None:
    period = data.split(":")[1]

    async with get_session() as session:
        report = await StatsService.get_productivity_report(session, user_id, period)
        text = format_productivity_report(report)

    await query.edit_message_text(text, reply_markup=stats_keyboard())


# ─── SETTINGS ─────────────────────────────────────────────────────────────────

async def _handle_setting(query, context, data: str, user_id: int) -> None:
    setting = data.split(":")[1]

    from sqlalchemy import select
    from database.models import UserSettings

    async with get_session() as session:
        result = await session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()
        if not settings:
            return

        if setting == "toggle_notif":
            settings.notifications_enabled = not settings.notifications_enabled
            await session.flush()
            await query.edit_message_text(
                "⚙️ Настройки:", reply_markup=settings_keyboard(settings)
            )

        elif setting == "morning_time":
            context.user_data["awaiting"] = "setting_morning_time"
            await query.edit_message_text("⏰ Введите время утреннего напоминания (ЧЧ:ММ):")

        elif setting == "default_priority":
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            buttons = [
                [
                    InlineKeyboardButton("🔴 HIGH", callback_data="setdefpriority:HIGH"),
                    InlineKeyboardButton("🟡 MEDIUM", callback_data="setdefpriority:MEDIUM"),
                    InlineKeyboardButton("🟢 LOW", callback_data="setdefpriority:LOW"),
                ],
            ]
            await query.edit_message_text(
                "🎯 Выберите приоритет по умолчанию:",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
