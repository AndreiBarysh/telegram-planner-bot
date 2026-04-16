"""Telegram command handlers (/start, /add_task, /list_tasks, etc.)."""

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from database.db import get_session
from database.models import (
    Priority,
    TaskStatus,
    User,
    UserSettings,
)
from services.task_service import TaskService
from services.project_service import ProjectService
from services.reminder_service import ReminderService
from services.stats_service import StatsService
from utils.formatters import (
    format_basic_stats,
    format_calendar,
    format_detailed_stats,
    format_productivity_report,
    format_project_list,
    format_project_stats,
    format_reminder_list,
    format_task_detail,
    format_task_list,
)
from utils.keyboards import (
    main_menu_keyboard,
    pagination_keyboard,
    reply_main_keyboard,
    stats_keyboard,
    task_actions_keyboard,
    task_list_filter_keyboard,
)
from utils.validators import (
    parse_task_id,
    validate_date,
    validate_priority,
    validate_reminder_time,
    validate_tags,
    validate_title,
)

logger = logging.getLogger(__name__)


async def _ensure_user(session, update: Update) -> User:
    """Ensure user exists in DB, create if not."""
    from sqlalchemy import select

    tg_user = update.effective_user
    result = await session.execute(select(User).where(User.user_id == tg_user.id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            user_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name or "",
        )
        session.add(user)
        settings = UserSettings(user_id=tg_user.id)
        session.add(settings)
        await session.flush()
    return user


# ─── /start ───────────────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — greet user and show main menu."""
    async with get_session() as session:
        user = await _ensure_user(session, update)

    text = (
        f"👋 Привет, {update.effective_user.first_name}!\n\n"
        "Я — твой персональный планировщик задач.\n"
        "Выбери действие из меню ниже или используй команды.\n\n"
        "Введи /help для списка всех команд."
    )
    await update.message.reply_text(
        text,
        reply_markup=main_menu_keyboard(),
    )
    await update.message.reply_text("⌨️ Быстрый доступ:", reply_markup=reply_main_keyboard())


# ─── /help ────────────────────────────────────────────────────────────────────

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help — show all available commands."""
    text = (
        "📖 ДОСТУПНЫЕ КОМАНДЫ\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 Задачи:\n"
        "  /add_task <название> — создать задачу\n"
        "  /list_tasks — список задач\n"
        "  /edit_task <id> — редактировать задачу\n"
        "  /complete_task <id> — выполнить задачу\n"
        "  /delete_task <id> — удалить задачу\n"
        "  /task_details <id> — детали задачи\n"
        "  /search <запрос> — поиск задач\n\n"
        "📁 Проекты:\n"
        "  /add_project <название> — создать проект\n"
        "  /list_projects — список проектов\n"
        "  /project_stats <id> — статистика проекта\n"
        "  /edit_project <id> — редактировать проект\n"
        "  /delete_project <id> — удалить проект\n\n"
        "⏰ Напоминания:\n"
        "  /set_reminder <task_id> <время> — установить\n"
        "  /list_reminders — активные напоминания\n"
        "  /cancel_reminder <id> — отменить\n\n"
        "📅 Календарь:\n"
        "  /calendar — календарь на текущий месяц\n"
        "  /tasks_for_day <ДД.ММ.ГГГГ> — задачи на день\n\n"
        "📊 Статистика:\n"
        "  /stats — основная статистика\n"
        "  /stats_detailed — расширенная\n"
        "  /productivity_report <период> — отчёт\n\n"
        "📤 Экспорт:\n"
        "  /export_csv — экспорт задач в CSV\n"
        "  /export_pdf — экспорт задач в PDF\n\n"
        "📅 Google Calendar:\n"
        "  /gcal_connect — подключить Google Calendar\n"
        "  /gcal_sync — синхронизировать задачи\n"
        "  /gcal_events — ближайшие события\n\n"
        "🏆 Профиль:\n"
        "  /profile — уровень и достижения\n"
        "  /achievements — все достижения\n"
        "  /share_task <id> — поделиться задачей\n\n"
        "⚙️ Прочее:\n"
        "  /menu — главное меню\n"
        "  /help — эта справка"
    )
    await update.message.reply_text(text)


# ─── /menu ────────────────────────────────────────────────────────────────────

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /menu — show main menu."""
    await update.message.reply_text("📌 Главное меню:", reply_markup=main_menu_keyboard())


# ─── TASKS ────────────────────────────────────────────────────────────────────

async def add_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /add_task — create a new task.

    Usage: /add_task Название задачи
    After creation, user can edit details via inline buttons.
    """
    if not context.args:
        await update.message.reply_text(
            "Использование: /add_task <название задачи>\n"
            "Пример: /add_task Написать письмо боссу"
        )
        return

    title = " ".join(context.args)
    valid, result = validate_title(title)
    if not valid:
        await update.message.reply_text(f"❌ {result}")
        return

    async with get_session() as session:
        await _ensure_user(session, update)
        task = await TaskService.create_task(
            session,
            user_id=update.effective_user.id,
            title=result,
        )
        text = (
            f"✅ Задача добавлена!\n\n"
            f"📋 {task.title}\n"
            f"🎯 Приоритет: MEDIUM\n"
            f"📌 ID: {task.task_id}"
        )
        await update.message.reply_text(
            text, reply_markup=task_actions_keyboard(task.task_id)
        )


async def list_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /list_tasks — show active tasks with filter buttons."""
    async with get_session() as session:
        await _ensure_user(session, update)
        tasks, total = await TaskService.list_tasks(
            session,
            user_id=update.effective_user.id,
            status=TaskStatus.ACTIVE,
            page=1,
        )
        text = format_task_list(tasks, total, page=1, page_size=10)
        keyboard = task_list_filter_keyboard()

        if total > 10:
            # Combine filter + pagination
            total_pages = (total + 9) // 10
            pag = pagination_keyboard(1, total_pages, prefix="taskpage")
            keyboard.inline_keyboard.extend(pag.inline_keyboard)

        await update.message.reply_text(text, reply_markup=keyboard)


async def complete_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /complete_task <id>."""
    if not context.args:
        await update.message.reply_text("Использование: /complete_task <id>")
        return

    task_id = parse_task_id(context.args[0])
    if task_id is None:
        await update.message.reply_text("❌ Неверный ID задачи.")
        return

    async with get_session() as session:
        task = await TaskService.complete_task(session, task_id, update.effective_user.id)
        if task is None:
            await update.message.reply_text("❌ Задача не найдена.")
        else:
            await update.message.reply_text(f"✅ Задача «{task.title}» выполнена!")


async def delete_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /delete_task <id>."""
    if not context.args:
        await update.message.reply_text("Использование: /delete_task <id>")
        return

    task_id = parse_task_id(context.args[0])
    if task_id is None:
        await update.message.reply_text("❌ Неверный ID задачи.")
        return

    async with get_session() as session:
        deleted = await TaskService.delete_task(session, task_id, update.effective_user.id)
        if deleted:
            await update.message.reply_text("🗑 Задача удалена.")
        else:
            await update.message.reply_text("❌ Задача не найдена.")


async def task_details_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /task_details <id>."""
    if not context.args:
        await update.message.reply_text("Использование: /task_details <id>")
        return

    task_id = parse_task_id(context.args[0])
    if task_id is None:
        await update.message.reply_text("❌ Неверный ID задачи.")
        return

    async with get_session() as session:
        task = await TaskService.get_task(session, task_id, update.effective_user.id)
        if task is None:
            await update.message.reply_text("❌ Задача не найдена.")
        else:
            text = format_task_detail(task)
            await update.message.reply_text(
                text, reply_markup=task_actions_keyboard(task.task_id)
            )


async def edit_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /edit_task <id> — show edit options."""
    if not context.args:
        await update.message.reply_text("Использование: /edit_task <id>")
        return

    task_id = parse_task_id(context.args[0])
    if task_id is None:
        await update.message.reply_text("❌ Неверный ID задачи.")
        return

    async with get_session() as session:
        task = await TaskService.get_task(session, task_id, update.effective_user.id)
        if task is None:
            await update.message.reply_text("❌ Задача не найдена.")
            return

    from utils.keyboards import task_edit_keyboard
    await update.message.reply_text(
        f"✏️ Редактирование: {task.title}\nВыберите, что изменить:",
        reply_markup=task_edit_keyboard(task_id),
    )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /search <query>."""
    if not context.args:
        await update.message.reply_text("Использование: /search <запрос>")
        return

    query = " ".join(context.args)
    async with get_session() as session:
        tasks, total = await TaskService.search_tasks(
            session, update.effective_user.id, query
        )
        text = format_task_list(tasks, total, page=1, page_size=10, title=f"РЕЗУЛЬТАТЫ ПОИСКА: «{query}»")
        await update.message.reply_text(text)


# ─── PROJECTS ─────────────────────────────────────────────────────────────────

async def add_project_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /add_project <name>."""
    if not context.args:
        await update.message.reply_text(
            "Использование: /add_project <название проекта>\n"
            "Пример: /add_project Работа"
        )
        return

    name = " ".join(context.args)
    valid, result = validate_title(name)
    if not valid:
        await update.message.reply_text(f"❌ {result}")
        return

    async with get_session() as session:
        await _ensure_user(session, update)
        project = await ProjectService.create_project(
            session, update.effective_user.id, result
        )
        await update.message.reply_text(
            f"✅ Проект создан!\n\n"
            f"📁 {project.name}\n"
            f"📌 ID: {project.project_id}"
        )


async def list_projects_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /list_projects."""
    async with get_session() as session:
        await _ensure_user(session, update)
        projects = await ProjectService.list_projects(session, update.effective_user.id)
        text = format_project_list(projects)
        from utils.keyboards import projects_menu_keyboard
        await update.message.reply_text(text, reply_markup=projects_menu_keyboard(projects))


async def project_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /project_stats <id>."""
    if not context.args:
        await update.message.reply_text("Использование: /project_stats <id>")
        return

    project_id = parse_task_id(context.args[0])
    if project_id is None:
        await update.message.reply_text("❌ Неверный ID проекта.")
        return

    async with get_session() as session:
        stats = await ProjectService.get_project_stats(
            session, project_id, update.effective_user.id
        )
        if stats is None:
            await update.message.reply_text("❌ Проект не найден.")
        else:
            text = format_project_stats(stats)
            await update.message.reply_text(text)


async def edit_project_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /edit_project <id> — enter conversation for editing project fields."""
    if not context.args:
        await update.message.reply_text("Использование: /edit_project <id>")
        return

    project_id = parse_task_id(context.args[0])
    if project_id is None:
        await update.message.reply_text("❌ Неверный ID проекта.")
        return

    # Store in user_data for conversation flow
    context.user_data["editing_project"] = project_id
    context.user_data["awaiting"] = "project_field"

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = [
        [
            InlineKeyboardButton("📝 Название", callback_data=f"editproj:name:{project_id}"),
            InlineKeyboardButton("📄 Описание", callback_data=f"editproj:desc:{project_id}"),
        ],
        [
            InlineKeyboardButton("🎨 Эмодзи", callback_data=f"editproj:emoji:{project_id}"),
        ],
    ]
    await update.message.reply_text(
        "✏️ Выберите, что изменить:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def delete_project_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /delete_project <id>."""
    if not context.args:
        await update.message.reply_text("Использование: /delete_project <id>")
        return

    project_id = parse_task_id(context.args[0])
    if project_id is None:
        await update.message.reply_text("❌ Неверный ID проекта.")
        return

    from utils.keyboards import project_delete_keyboard
    await update.message.reply_text(
        "⚠️ Как удалить проект?",
        reply_markup=project_delete_keyboard(project_id),
    )


# ─── REMINDERS ────────────────────────────────────────────────────────────────

async def set_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /set_reminder <task_id> <time>."""
    if len(context.args) < 2:
        await update.message.reply_text(
            "Использование: /set_reminder <task_id> <время>\n"
            'Примеры:\n  /set_reminder 1 завтра в 14:00\n  /set_reminder 1 через 2 часа\n  /set_reminder 1 16.04.2026 18:00'
        )
        return

    task_id = parse_task_id(context.args[0])
    if task_id is None:
        await update.message.reply_text("❌ Неверный ID задачи.")
        return

    time_str = " ".join(context.args[1:])
    valid, result = validate_reminder_time(time_str)
    if not valid:
        await update.message.reply_text(f"❌ {result}")
        return

    async with get_session() as session:
        reminder = await ReminderService.create_reminder(
            session, update.effective_user.id, task_id, result
        )
        if reminder is None:
            await update.message.reply_text("❌ Задача не найдена.")
        else:
            await update.message.reply_text(
                f"✅ Напоминание установлено!\n"
                f"⏰ {result.strftime('%d.%m.%Y %H:%M')}"
            )


async def list_reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /list_reminders."""
    async with get_session() as session:
        reminders = await ReminderService.list_reminders(
            session, update.effective_user.id
        )
        text = format_reminder_list(reminders)
        await update.message.reply_text(text)


async def cancel_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel_reminder <id>."""
    if not context.args:
        await update.message.reply_text("Использование: /cancel_reminder <id>")
        return

    reminder_id = parse_task_id(context.args[0])
    if reminder_id is None:
        await update.message.reply_text("❌ Неверный ID напоминания.")
        return

    async with get_session() as session:
        cancelled = await ReminderService.cancel_reminder(
            session, reminder_id, update.effective_user.id
        )
        if cancelled:
            await update.message.reply_text("✅ Напоминание отменено.")
        else:
            await update.message.reply_text("❌ Напоминание не найдено.")


# ─── CALENDAR ─────────────────────────────────────────────────────────────────

async def calendar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /calendar — show current month calendar."""
    now = datetime.utcnow()
    await _send_calendar(update, context, now.year, now.month)


async def _send_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE, year: int, month: int) -> str:
    """Build and return calendar text for given month."""
    from utils.date_utils import get_month_bounds

    start, end = get_month_bounds(year, month)

    async with get_session() as session:
        from sqlalchemy import select
        from database.models import Task, TaskStatus

        # All tasks in this month
        result = await session.execute(
            select(Task).where(
                Task.user_id == update.effective_user.id,
                Task.due_date >= start,
                Task.due_date <= end,
            )
        )
        tasks = result.scalars().all()

    task_days = set()
    deadline_days = set()
    completed_days = set()

    for t in tasks:
        if t.due_date:
            day = t.due_date.day
            if t.status == TaskStatus.COMPLETED:
                completed_days.add(day)
            elif t.status == TaskStatus.ACTIVE and t.due_date < datetime.utcnow():
                deadline_days.add(day)
            else:
                task_days.add(day)

    text = format_calendar(year, month, task_days, deadline_days, completed_days)

    from utils.keyboards import calendar_keyboard
    msg = update.message or update.callback_query.message
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=calendar_keyboard(year, month)
        )
    else:
        await msg.reply_text(text, reply_markup=calendar_keyboard(year, month))
    return text


async def tasks_for_day_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tasks_for_day <DD.MM.YYYY>."""
    if not context.args:
        await update.message.reply_text("Использование: /tasks_for_day <ДД.ММ.ГГГГ>")
        return

    valid, result = validate_date(context.args[0])
    if not valid:
        await update.message.reply_text(f"❌ {result}")
        return

    async with get_session() as session:
        tasks = await TaskService.get_tasks_for_date(
            session, update.effective_user.id, result
        )
        if not tasks:
            await update.message.reply_text(
                f"📅 {result.strftime('%d.%m.%Y')}: задач нет."
            )
        else:
            text = format_task_list(
                tasks, len(tasks), page=1, page_size=len(tasks),
                title=f"ЗАДАЧИ НА {result.strftime('%d.%m.%Y')}",
            )
            await update.message.reply_text(text)


# ─── STATS ────────────────────────────────────────────────────────────────────

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats — show basic statistics."""
    async with get_session() as session:
        stats = await StatsService.get_basic_stats(session, update.effective_user.id)
        text = format_basic_stats(stats)
        await update.message.reply_text(text, reply_markup=stats_keyboard())


async def stats_detailed_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats_detailed — extended statistics."""
    async with get_session() as session:
        basic = await StatsService.get_basic_stats(session, update.effective_user.id)
        detailed = await StatsService.get_detailed_stats(session, update.effective_user.id)
        text = format_detailed_stats(basic, detailed)
        await update.message.reply_text(text, reply_markup=stats_keyboard())


async def productivity_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /productivity_report <period>."""
    period = "week"
    if context.args:
        p = context.args[0].lower()
        if p in ("day", "week", "month", "quarter", "день", "неделя", "месяц", "квартал"):
            mapping = {"день": "day", "неделя": "week", "месяц": "month", "квартал": "quarter"}
            period = mapping.get(p, p)

    async with get_session() as session:
        report = await StatsService.get_productivity_report(
            session, update.effective_user.id, period
        )
        text = format_productivity_report(report)
        await update.message.reply_text(text)


# ─── PHASE 3: EXPORT ─────────────────────────────────────────────────────────

async def export_csv_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /export_csv — export all tasks to CSV."""
    async with get_session() as session:
        await _ensure_user(session, update)
        tasks, _ = await TaskService.list_tasks(
            session, update.effective_user.id, page=1, page_size=9999
        )
        if not tasks:
            await update.message.reply_text("📋 Нет задач для экспорта.")
            return

        from services.export_service import export_tasks_csv
        buf = export_tasks_csv(tasks)
        await update.message.reply_document(
            document=buf,
            filename=f"tasks_{datetime.utcnow().strftime('%Y%m%d')}.csv",
            caption=f"📊 Экспорт: {len(tasks)} задач",
        )


async def export_pdf_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /export_pdf — export all tasks to PDF."""
    async with get_session() as session:
        await _ensure_user(session, update)
        tasks, _ = await TaskService.list_tasks(
            session, update.effective_user.id, page=1, page_size=9999
        )
        if not tasks:
            await update.message.reply_text("📋 Нет задач для экспорта.")
            return

        from services.export_service import export_tasks_pdf
        buf = export_tasks_pdf(tasks, title="Мои задачи")
        await update.message.reply_document(
            document=buf,
            filename=f"tasks_{datetime.utcnow().strftime('%Y%m%d')}.pdf",
            caption=f"📊 Экспорт: {len(tasks)} задач",
        )


# ─── PHASE 3: GOOGLE CALENDAR ────────────────────────────────────────────────

async def gcal_connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /gcal_connect — start Google Calendar OAuth."""
    from services.google_calendar_service import is_configured, get_auth_url, is_user_connected

    if not is_configured():
        await update.message.reply_text(
            "⚠️ Google Calendar не настроен.\n\n"
            "Для настройки:\n"
            "1. Создайте проект в Google Cloud Console\n"
            "2. Включите Calendar API\n"
            "3. Создайте OAuth2 credentials (Desktop app)\n"
            "4. Скачайте client_secret.json в папку credentials/"
        )
        return

    if is_user_connected(update.effective_user.id):
        await update.message.reply_text("✅ Google Calendar уже подключён!")
        return

    auth_url = get_auth_url(update.effective_user.id)
    if auth_url:
        context.user_data["awaiting"] = "gcal_auth_code"
        await update.message.reply_text(
            "🔗 Для подключения Google Calendar:\n\n"
            f"1. Перейдите по ссылке:\n{auth_url}\n\n"
            "2. Авторизуйтесь и скопируйте код\n"
            "3. Отправьте код мне в ответ"
        )


async def gcal_sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /gcal_sync — sync tasks with deadlines to Google Calendar."""
    from services.google_calendar_service import is_user_connected, sync_task_to_calendar

    if not is_user_connected(update.effective_user.id):
        await update.message.reply_text("❌ Google Calendar не подключён. Используйте /gcal_connect")
        return

    async with get_session() as session:
        tasks, _ = await TaskService.list_tasks(
            session, update.effective_user.id, status=TaskStatus.ACTIVE, page=1, page_size=9999
        )
        synced = 0
        for task in tasks:
            if task.due_date:
                event_id = sync_task_to_calendar(update.effective_user.id, task)
                if event_id:
                    synced += 1

        await update.message.reply_text(f"✅ Синхронизировано {synced} задач с Google Calendar")


async def gcal_events_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /gcal_events — show upcoming Google Calendar events."""
    from services.google_calendar_service import is_user_connected, get_upcoming_events

    if not is_user_connected(update.effective_user.id):
        await update.message.reply_text("❌ Google Calendar не подключён. Используйте /gcal_connect")
        return

    events = get_upcoming_events(update.effective_user.id)
    if events is None:
        await update.message.reply_text("❌ Не удалось получить события.")
        return

    if not events:
        await update.message.reply_text("📅 Предстоящих событий нет.")
        return

    lines = ["📅 БЛИЖАЙШИЕ СОБЫТИЯ", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    for e in events:
        start = e["start"][:16].replace("T", " ") if e["start"] else ""
        lines.append(f"\n📌 {e['summary']}")
        lines.append(f"   ⏰ {start}")

    await update.message.reply_text("\n".join(lines))


# ─── PHASE 3: GAMIFICATION ───────────────────────────────────────────────────

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /profile — show gamification profile."""
    from services.gamification_service import GamificationService, get_level
    from utils.formatters import format_progress_bar

    async with get_session() as session:
        await _ensure_user(session, update)
        profile = await GamificationService.get_profile(session, update.effective_user.id)

    lines = [
        f"🏆 ПРОФИЛЬ — {update.effective_user.first_name}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"🎖 Уровень: {profile['level_name']}",
        f"📊 Прогресс: {format_progress_bar(profile['current_xp'], profile['needed_xp'])} {profile['current_xp']}/{profile['needed_xp']}",
        f"✅ Всего выполнено: {profile['total_completed']}",
        f"🔥 Текущий стрик: {profile['streak']} дн.",
        "",
        f"🏅 ДОСТИЖЕНИЯ ({len(profile['unlocked'])}/{len(profile['unlocked']) + len(profile['locked'])})",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if profile["unlocked"]:
        for ach in profile["unlocked"]:
            lines.append(f"  ✅ {ach['name']} — {ach['desc']}")
    else:
        lines.append("  Пока нет достижений. Выполняйте задачи!")

    if profile["locked"]:
        lines.append("")
        lines.append("🔒 Следующие:")
        for ach in profile["locked"][:3]:
            lines.append(f"  🔒 {ach['name']} — {ach['desc']}")

    await update.message.reply_text("\n".join(lines))


async def achievements_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /achievements — show all achievements."""
    from services.gamification_service import GamificationService, ACHIEVEMENTS

    async with get_session() as session:
        await _ensure_user(session, update)
        stats = await GamificationService.get_user_stats(session, update.effective_user.id)

    lines = [
        "🏅 ВСЕ ДОСТИЖЕНИЯ",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for ach in ACHIEVEMENTS:
        if ach["check"](stats):
            lines.append(f"\n  ✅ {ach['name']}")
        else:
            lines.append(f"\n  🔒 {ach['name']}")
        lines.append(f"     {ach['desc']}")

    await update.message.reply_text("\n".join(lines))


# ─── PHASE 3: SHARED TASKS ───────────────────────────────────────────────────

async def share_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /share_task <id> — generate shareable link for a task."""
    if not context.args:
        await update.message.reply_text("Использование: /share_task <id>")
        return

    task_id = parse_task_id(context.args[0])
    if task_id is None:
        await update.message.reply_text("❌ Неверный ID задачи.")
        return

    async with get_session() as session:
        task = await TaskService.get_task(session, task_id, update.effective_user.id)
        if task is None:
            await update.message.reply_text("❌ Задача не найдена.")
            return

        # Generate shareable text
        lines = [
            "📋 Общая задача:",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"📌 {task.title}",
        ]
        if task.description:
            lines.append(f"📝 {task.description}")
        if task.due_date:
            lines.append(f"⏰ Дедлайн: {task.due_date.strftime('%d.%m.%Y %H:%M')}")
        if task.project:
            lines.append(f"📁 Проект: {task.project.name}")

        lines.append(f"\n👤 От: {update.effective_user.first_name}")

        text = "\n".join(lines)
        await update.message.reply_text(
            f"📤 Перешлите это сообщение, чтобы поделиться задачей:\n\n{text}"
        )
