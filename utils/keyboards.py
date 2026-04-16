"""Telegram keyboard construction utilities."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from database.models import Priority, TaskStatus
from utils.date_utils import next_month, prev_month


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Build the main menu inline keyboard."""
    buttons = [
        [InlineKeyboardButton("📋 Мои Задачи", callback_data="menu:tasks")],
        [InlineKeyboardButton("📁 Проекты", callback_data="menu:projects")],
        [InlineKeyboardButton("📊 Статистика", callback_data="menu:stats")],
        [InlineKeyboardButton("⏰ Напоминания", callback_data="menu:reminders")],
        [InlineKeyboardButton("📅 Календарь", callback_data="menu:calendar")],
        [
            InlineKeyboardButton("🏆 Профиль", callback_data="menu:profile"),
            InlineKeyboardButton("📤 Экспорт", callback_data="menu:export"),
        ],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="menu:settings")],
    ]
    return InlineKeyboardMarkup(buttons)


def reply_main_keyboard() -> ReplyKeyboardMarkup:
    """Build a persistent reply keyboard for quick access."""
    keyboard = [
        ["📋 Задачи", "📁 Проекты"],
        ["📊 Статистика", "📅 Календарь"],
        ["➕ Новая задача", "⚙️ Настройки"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def task_actions_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Inline buttons for quick task actions."""
    buttons = [
        [
            InlineKeyboardButton("✅ Выполнено", callback_data=f"task:complete:{task_id}"),
            InlineKeyboardButton("✏️ Изменить", callback_data=f"task:edit:{task_id}"),
            InlineKeyboardButton("🗑 Удалить", callback_data=f"task:delete:{task_id}"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def task_edit_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Inline buttons for editing task fields."""
    buttons = [
        [
            InlineKeyboardButton("📝 Название", callback_data=f"edit:title:{task_id}"),
            InlineKeyboardButton("📄 Описание", callback_data=f"edit:desc:{task_id}"),
        ],
        [
            InlineKeyboardButton("🎯 Приоритет", callback_data=f"edit:priority:{task_id}"),
            InlineKeyboardButton("⏰ Дедлайн", callback_data=f"edit:due:{task_id}"),
        ],
        [
            InlineKeyboardButton("📁 Проект", callback_data=f"edit:project:{task_id}"),
            InlineKeyboardButton("🏷 Теги", callback_data=f"edit:tags:{task_id}"),
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data=f"task:detail:{task_id}")],
    ]
    return InlineKeyboardMarkup(buttons)


def priority_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Priority selection keyboard."""
    buttons = [
        [
            InlineKeyboardButton("🔴 HIGH", callback_data=f"setpriority:HIGH:{task_id}"),
            InlineKeyboardButton("🟡 MEDIUM", callback_data=f"setpriority:MEDIUM:{task_id}"),
            InlineKeyboardButton("🟢 LOW", callback_data=f"setpriority:LOW:{task_id}"),
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data=f"task:edit:{task_id}")],
    ]
    return InlineKeyboardMarkup(buttons)


def task_list_filter_keyboard() -> InlineKeyboardMarkup:
    """Filter options for task list."""
    buttons = [
        [
            InlineKeyboardButton("📌 Активные", callback_data="filter:status:active"),
            InlineKeyboardButton("✅ Завершённые", callback_data="filter:status:completed"),
            InlineKeyboardButton("📋 Все", callback_data="filter:status:all"),
        ],
        [
            InlineKeyboardButton("🔴 HIGH", callback_data="filter:priority:HIGH"),
            InlineKeyboardButton("🟡 MEDIUM", callback_data="filter:priority:MEDIUM"),
            InlineKeyboardButton("🟢 LOW", callback_data="filter:priority:LOW"),
        ],
        [
            InlineKeyboardButton("📅 Сегодня", callback_data="filter:period:today"),
            InlineKeyboardButton("📅 Неделя", callback_data="filter:period:week"),
            InlineKeyboardButton("📅 Месяц", callback_data="filter:period:month"),
        ],
        [
            InlineKeyboardButton("🔽 По дедлайну", callback_data="filter:sort:due_date"),
            InlineKeyboardButton("🔽 По приоритету", callback_data="filter:sort:priority"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def pagination_keyboard(page: int, total_pages: int, prefix: str = "page") -> InlineKeyboardMarkup:
    """Pagination buttons."""
    buttons = []
    row = []
    if page > 1:
        row.append(InlineKeyboardButton("◀️ Назад", callback_data=f"{prefix}:{page - 1}"))
    row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        row.append(InlineKeyboardButton("Вперёд ▶️", callback_data=f"{prefix}:{page + 1}"))
    buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def projects_menu_keyboard(projects: list) -> InlineKeyboardMarkup:
    """Projects list with action buttons."""
    buttons = []
    for p in projects:
        buttons.append([
            InlineKeyboardButton(
                f"{p.color_emoji} {p.name}",
                callback_data=f"project:view:{p.project_id}",
            )
        ])
    buttons.append([InlineKeyboardButton("➕ Создать проект", callback_data="project:create")])
    buttons.append([InlineKeyboardButton("◀️ Меню", callback_data="menu:main")])
    return InlineKeyboardMarkup(buttons)


def project_view_keyboard(project_id: int) -> InlineKeyboardMarkup:
    """Actions for a single project."""
    buttons = [
        [InlineKeyboardButton("📋 Задачи проекта", callback_data=f"project:tasks:{project_id}")],
        [InlineKeyboardButton("📊 Статистика", callback_data=f"project:stats:{project_id}")],
        [
            InlineKeyboardButton("✏️ Изменить", callback_data=f"project:edit:{project_id}"),
            InlineKeyboardButton("🗑 Удалить", callback_data=f"project:delete:{project_id}"),
        ],
        [InlineKeyboardButton("◀️ Проекты", callback_data="menu:projects")],
    ]
    return InlineKeyboardMarkup(buttons)


def project_select_keyboard(projects: list, task_id: int) -> InlineKeyboardMarkup:
    """Select a project to assign to a task."""
    buttons = []
    for p in projects:
        buttons.append([
            InlineKeyboardButton(
                f"{p.color_emoji} {p.name}",
                callback_data=f"setproject:{p.project_id}:{task_id}",
            )
        ])
    buttons.append([
        InlineKeyboardButton("❌ Без проекта", callback_data=f"setproject:none:{task_id}")
    ])
    buttons.append([
        InlineKeyboardButton("◀️ Назад", callback_data=f"task:edit:{task_id}")
    ])
    return InlineKeyboardMarkup(buttons)


def delete_confirm_keyboard(entity: str, entity_id: int) -> InlineKeyboardMarkup:
    """Confirmation dialog for deletion."""
    buttons = [
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete:{entity}:{entity_id}"),
            InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_delete:{entity}:{entity_id}"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def project_delete_keyboard(project_id: int) -> InlineKeyboardMarkup:
    """Delete project options."""
    buttons = [
        [InlineKeyboardButton("🗑 Только проект", callback_data=f"delproj:keep:{project_id}")],
        [InlineKeyboardButton("🗑 Проект и задачи", callback_data=f"delproj:all:{project_id}")],
        [InlineKeyboardButton("❌ Отмена", callback_data="menu:projects")],
    ]
    return InlineKeyboardMarkup(buttons)


def calendar_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    """Navigation keyboard for calendar view."""
    py, pm = prev_month(year, month)
    ny, nm = next_month(year, month)
    buttons = [
        [
            InlineKeyboardButton("◀️", callback_data=f"cal:{py}:{pm}"),
            InlineKeyboardButton(f"{month:02d}.{year}", callback_data="noop"),
            InlineKeyboardButton("▶️", callback_data=f"cal:{ny}:{nm}"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def stats_keyboard() -> InlineKeyboardMarkup:
    """Statistics view selector."""
    buttons = [
        [
            InlineKeyboardButton("📊 Базовая", callback_data="stats:basic"),
            InlineKeyboardButton("📈 Расширенная", callback_data="stats:detailed"),
        ],
        [
            InlineKeyboardButton("📅 День", callback_data="report:day"),
            InlineKeyboardButton("📅 Неделя", callback_data="report:week"),
            InlineKeyboardButton("📅 Месяц", callback_data="report:month"),
            InlineKeyboardButton("📅 Квартал", callback_data="report:quarter"),
        ],
        [InlineKeyboardButton("◀️ Меню", callback_data="menu:main")],
    ]
    return InlineKeyboardMarkup(buttons)


def settings_keyboard(settings) -> InlineKeyboardMarkup:
    """User settings keyboard."""
    notif_label = "🔔 Уведомления: ВКЛ" if settings.notifications_enabled else "🔕 Уведомления: ВЫКЛ"
    buttons = [
        [InlineKeyboardButton(notif_label, callback_data="setting:toggle_notif")],
        [InlineKeyboardButton(f"⏰ Утреннее: {settings.morning_reminder_time}", callback_data="setting:morning_time")],
        [InlineKeyboardButton(f"🎯 Приоритет: {settings.default_priority.value}", callback_data="setting:default_priority")],
        [InlineKeyboardButton("◀️ Меню", callback_data="menu:main")],
    ]
    return InlineKeyboardMarkup(buttons)


def reminder_done_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Reminder notification with quick complete button."""
    buttons = [
        [InlineKeyboardButton("✅ Выполнено", callback_data=f"task:complete:{task_id}")],
    ]
    return InlineKeyboardMarkup(buttons)
