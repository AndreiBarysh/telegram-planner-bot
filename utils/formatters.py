"""Formatting utilities for Telegram message output."""

from datetime import datetime, timedelta

from database.models import Priority, Task, TaskStatus, Project


PRIORITY_EMOJI = {
    Priority.HIGH: "🔴",
    Priority.MEDIUM: "🟡",
    Priority.LOW: "🟢",
}

PRIORITY_LABELS = {
    Priority.HIGH: "HIGH",
    Priority.MEDIUM: "MEDIUM",
    Priority.LOW: "LOW",
}

STATUS_EMOJI = {
    TaskStatus.ACTIVE: "📌",
    TaskStatus.COMPLETED: "✅",
    TaskStatus.CANCELLED: "❌",
}


def format_task_short(task: Task, index: int | None = None) -> str:
    """Format a task for list display."""
    prefix = f"{index}. " if index is not None else ""
    emoji = PRIORITY_EMOJI.get(task.priority, "🟡")
    status_mark = "✅ " if task.status == TaskStatus.COMPLETED else ""

    overdue = ""
    if (
        task.status == TaskStatus.ACTIVE
        and task.due_date
        and task.due_date < datetime.utcnow()
    ):
        overdue = " 🔴 ПРОСРОЧЕНО"

    lines = [f"{emoji} {status_mark}{prefix}{task.title} [{PRIORITY_LABELS[task.priority]}]{overdue}"]

    if task.project:
        lines.append(f"   📁 Проект: {task.project.color_emoji} {task.project.name}")

    if task.due_date:
        lines.append(f"   ⏰ Дедлайн: {task.due_date.strftime('%d.%m.%Y %H:%M')}")
        if task.status == TaskStatus.ACTIVE:
            remaining = format_time_remaining(task.due_date)
            lines.append(f"   ⏳ Осталось: {remaining}")

    if task.tags:
        tag_str = ", ".join(f"#{t.tag_name}" for t in task.tags)
        lines.append(f"   🏷 {tag_str}")

    return "\n".join(lines)


def format_task_detail(task: Task) -> str:
    """Format a task for detailed view."""
    emoji = PRIORITY_EMOJI.get(task.priority, "🟡")
    status = STATUS_EMOJI.get(task.status, "📌")

    lines = [
        f"{status} Задача #{task.task_id}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"{emoji} {task.title}",
    ]

    if task.description:
        lines.append(f"\n📝 {task.description}")

    lines.append(f"\n📊 Приоритет: {PRIORITY_LABELS[task.priority]}")
    lines.append(f"📌 Статус: {task.status.value}")

    if task.project:
        lines.append(f"📁 Проект: {task.project.color_emoji} {task.project.name}")

    if task.due_date:
        lines.append(f"⏰ Дедлайн: {task.due_date.strftime('%d.%m.%Y %H:%M')}")
        if task.status == TaskStatus.ACTIVE:
            remaining = format_time_remaining(task.due_date)
            lines.append(f"⏳ Осталось: {remaining}")

    if task.tags:
        tag_str = ", ".join(f"#{t.tag_name}" for t in task.tags)
        lines.append(f"🏷 Теги: {tag_str}")

    lines.append(f"\n📅 Создано: {task.created_at.strftime('%d.%m.%Y %H:%M')}")
    if task.completed_at:
        lines.append(f"✅ Завершено: {task.completed_at.strftime('%d.%m.%Y %H:%M')}")

    return "\n".join(lines)


def format_task_list(tasks: list[Task], total: int, page: int, page_size: int, title: str = "АКТИВНЫЕ ЗАДАЧИ") -> str:
    """Format a paginated list of tasks."""
    if not tasks:
        return f"📋 {title}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nЗадач не найдено."

    total_pages = (total + page_size - 1) // page_size
    lines = [
        f"📋 {title} ({total})",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for i, task in enumerate(tasks, start=(page - 1) * page_size + 1):
        lines.append(format_task_short(task, i))
        lines.append("")

    if total_pages > 1:
        lines.append(f"📄 Страница {page}/{total_pages}")

    return "\n".join(lines)


def format_project_list(projects: list[Project]) -> str:
    """Format list of projects."""
    if not projects:
        return "📁 ПРОЕКТЫ\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nПроектов не найдено."

    lines = [
        f"📁 ПРОЕКТЫ ({len(projects)})",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for project in projects:
        tasks = project.tasks
        active = sum(1 for t in tasks if t.status == TaskStatus.ACTIVE)
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        total = len(tasks)

        progress = format_progress_bar(completed, total)
        lines.append(
            f"\n{project.color_emoji} {project.name} (ID: {project.project_id})"
        )
        if project.description:
            lines.append(f"   📝 {project.description[:80]}")
        lines.append(f"   📊 {progress} {completed}/{total}")
        lines.append(f"   📌 Активных: {active} | ✅ Завершённых: {completed}")

    return "\n".join(lines)


def format_project_stats(stats: dict) -> str:
    """Format project statistics."""
    project = stats["project"]
    lines = [
        f"📊 Статистика: {project.color_emoji} {project.name}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"\n📋 Всего задач: {stats['total']}",
        f"📌 Активных: {stats['active']}",
        f"✅ Завершённых: {stats['completed']}",
        f"❌ Отменённых: {stats['cancelled']}",
        f"🔴 Просроченных: {stats['overdue']}",
        f"\n📈 Прогресс: {format_progress_bar(stats['completed'], stats['total'])} {stats['progress']}%",
        "\n📊 По приоритетам:",
    ]

    for priority, count in stats["by_priority"].items():
        lines.append(f"   {PRIORITY_EMOJI[priority]} {PRIORITY_LABELS[priority]}: {count}")

    return "\n".join(lines)


def format_basic_stats(stats: dict) -> str:
    """Format basic statistics."""
    today_progress = format_progress_bar(
        stats["completed_today"], stats["due_today"]
    )
    today_pct = (
        round(stats["completed_today"] / stats["due_today"] * 100)
        if stats["due_today"] > 0
        else 0
    )

    lines = [
        "📊 СТАТИСТИКА",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"✅ Завершено сегодня: {stats['completed_today']}/{stats['due_today']} ({today_pct}%)",
        f"   {today_progress}",
        "",
        f"📈 На неделе: {stats['completed_week']} задач выполнено",
        f"📅 За месяц: {stats['completed_month']} задач выполнено",
        f"📉 Просроченных: {stats['overdue']} задач",
        f"⚡ Средняя скорость: {stats['avg_completion_hours']} ч. на задачу",
        "",
        f"📋 Всего: {stats['total']} | Активных: {stats['active']} | Завершённых: {stats['completed']}",
    ]
    return "\n".join(lines)


def format_detailed_stats(basic: dict, detailed: dict) -> str:
    """Format detailed statistics with chart."""
    lines = [
        "📊 РАСШИРЕННАЯ СТАТИСТИКА (30 дней)",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    # Daily chart (last 14 days for readability)
    chart_data = detailed["daily_chart"][-14:]
    if chart_data:
        max_val = max((c for _, c in chart_data), default=1) or 1
        lines.append("📅 Задач завершено по дням:")
        for day_str, count in chart_data:
            day = datetime.strptime(day_str, "%Y-%m-%d")
            bar_len = round((count / max_val) * 10) if max_val > 0 else 0
            bar = "█" * bar_len + "░" * (10 - bar_len)
            lines.append(f"   {day.strftime('%d.%m')} {bar} {count}")

    # Priority distribution
    lines.append("\n📊 Распределение по приоритетам:")
    total_by_p = sum(detailed["by_priority"].values()) or 1
    for priority, count in detailed["by_priority"].items():
        pct = round(count / total_by_p * 100)
        bar = format_progress_bar(count, total_by_p)
        label = PRIORITY_LABELS.get(priority, str(priority))
        emoji = PRIORITY_EMOJI.get(priority, "⚪")
        lines.append(f"   {emoji} {label}: {bar} {count} ({pct}%)")

    if detailed["most_productive_day"]:
        lines.append(f"\n🏆 Самый продуктивный день: {detailed['most_productive_day']}")

    lines.append(f"\n✅ Вовремя: {detailed['on_time']} | ⏰ С опозданием: {detailed['late']}")

    return "\n".join(lines)


def format_productivity_report(report: dict) -> str:
    """Format productivity report."""
    period_names = {
        "day": "День",
        "week": "Неделя",
        "month": "Месяц",
        "quarter": "Квартал",
    }

    trend_emoji = "📈" if report["trend_pct"] >= 0 else "📉"
    trend_sign = "+" if report["trend_pct"] >= 0 else ""

    lines = [
        f"📊 ОТЧЁТ О ПРОДУКТИВНОСТИ — {period_names.get(report['period'], report['period'])}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📅 Период: {report['start'].strftime('%d.%m.%Y')} — {report['end'].strftime('%d.%m.%Y')}",
        "",
        f"✅ Задач выполнено: {report['completed']}",
        f"📊 За предыдущий период: {report['prev_completed']}",
        f"{trend_emoji} Тренд: {trend_sign}{report['trend_pct']}%",
        f"⚡ Среднее время: {report['avg_completion_hours']} ч.",
    ]
    return "\n".join(lines)


def format_progress_bar(current: int, total: int, length: int = 10) -> str:
    """Create a text progress bar."""
    if total == 0:
        return "░" * length
    ratio = min(current / total, 1.0)
    filled = round(ratio * length)
    return "█" * filled + "░" * (length - filled)


def format_time_remaining(due_date: datetime) -> str:
    """Format time remaining until deadline."""
    now = datetime.utcnow()
    if due_date < now:
        delta = now - due_date
        return f"просрочено на {_format_delta(delta)}"
    delta = due_date - now
    return _format_delta(delta)


def _format_delta(delta: timedelta) -> str:
    """Format timedelta to human-readable Russian string."""
    total_seconds = int(delta.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60

    parts = []
    if days > 0:
        parts.append(f"{days}дн")
    if hours > 0:
        parts.append(f"{hours}ч")
    if minutes > 0 and days == 0:
        parts.append(f"{minutes}мин")
    return " ".join(parts) if parts else "< 1мин"


def format_calendar(year: int, month: int, task_days: set[int], deadline_days: set[int], completed_days: set[int]) -> str:
    """Render a text calendar with task markers."""
    import calendar

    cal = calendar.monthcalendar(year, month)
    month_names = [
        "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
    ]

    lines = [
        f"📅 {month_names[month]} {year}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "Пн  Вт  Ср  Чт  Пт  Сб  Вс",
    ]

    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append("    ")
            else:
                if day in deadline_days:
                    row.append(f"{day:2d}⚠️")
                elif day in completed_days:
                    row.append(f"{day:2d}✅")
                elif day in task_days:
                    row.append(f"{day:2d}📅")
                else:
                    row.append(f"{day:2d}  ")
        lines.append("  ".join(row))

    legend = "\n📅 — задачи  ⚠️ — дедлайн  ✅ — завершённые"
    lines.append(legend)
    return "\n".join(lines)


def format_reminder_list(reminders: list) -> str:
    """Format list of reminders."""
    if not reminders:
        return "⏰ НАПОМИНАНИЯ\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nАктивных напоминаний нет."

    lines = [
        f"⏰ АКТИВНЫЕ НАПОМИНАНИЯ ({len(reminders)})",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for r in reminders:
        task_title = r.task.title if r.task else "Без задачи"
        remaining = format_time_remaining(r.reminder_time)
        lines.append(f"\n🔔 ID: {r.reminder_id}")
        lines.append(f"   📋 {task_title}")
        lines.append(f"   ⏰ {r.reminder_time.strftime('%d.%m.%Y %H:%M')}")
        lines.append(f"   ⏳ Через: {remaining}")

    return "\n".join(lines)
