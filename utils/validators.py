"""Input validation utilities."""

import re
from datetime import datetime

from database.models import Priority, TaskStatus


MAX_TITLE_LENGTH = 500
MAX_DESCRIPTION_LENGTH = 2000
MAX_TAG_LENGTH = 100
MAX_PROJECT_NAME_LENGTH = 255


def validate_title(title: str) -> tuple[bool, str]:
    """Validate task or project title."""
    title = title.strip()
    if not title:
        return False, "Название не может быть пустым."
    if len(title) > MAX_TITLE_LENGTH:
        return False, f"Название слишком длинное (макс. {MAX_TITLE_LENGTH} символов, у вас {len(title)})."
    return True, title


def validate_description(desc: str | None) -> tuple[bool, str | None]:
    """Validate description field."""
    if desc is None or desc.strip() == "":
        return True, None
    desc = desc.strip()
    if len(desc) > MAX_DESCRIPTION_LENGTH:
        return False, f"Описание слишком длинное (макс. {MAX_DESCRIPTION_LENGTH} символов)."
    return True, desc


def validate_priority(priority_str: str) -> tuple[bool, Priority | str]:
    """Validate and parse priority string."""
    mapping = {
        "high": Priority.HIGH,
        "medium": Priority.MEDIUM,
        "low": Priority.LOW,
        "высокий": Priority.HIGH,
        "средний": Priority.MEDIUM,
        "низкий": Priority.LOW,
        "h": Priority.HIGH,
        "m": Priority.MEDIUM,
        "l": Priority.LOW,
    }
    key = priority_str.strip().lower()
    if key in mapping:
        return True, mapping[key]
    return False, "Неверный приоритет. Допустимые: HIGH, MEDIUM, LOW."


def validate_date(date_str: str) -> tuple[bool, datetime | str]:
    """Parse date string in various formats."""
    date_str = date_str.strip()

    formats = [
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            # Default time to 23:59 if only date provided
            if "%H" not in fmt:
                dt = dt.replace(hour=23, minute=59)
            return True, dt
        except ValueError:
            continue

    return False, "Неверный формат даты. Используйте: ДД.ММ.ГГГГ ЧЧ:ММ"


def validate_tags(tags_str: str) -> tuple[bool, list[str] | str]:
    """Parse and validate tags string (comma-separated or space-separated with #)."""
    if not tags_str.strip():
        return True, []

    # Remove # symbols and split
    tags_str = tags_str.replace("#", "")
    if "," in tags_str:
        tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    else:
        tags = [t.strip() for t in tags_str.split() if t.strip()]

    for tag in tags:
        if len(tag) > MAX_TAG_LENGTH:
            return False, f"Тег '{tag}' слишком длинный (макс. {MAX_TAG_LENGTH} символов)."

    return True, tags


def validate_emoji(emoji_str: str) -> tuple[bool, str]:
    """Validate that the string contains a single emoji or short marker."""
    emoji_str = emoji_str.strip()
    if not emoji_str:
        return True, "📁"
    if len(emoji_str) > 10:
        return False, "Эмодзи должно быть коротким (до 10 символов)."
    return True, emoji_str


def parse_task_id(text: str) -> int | None:
    """Extract task ID from command arguments."""
    match = re.search(r"\d+", text.strip())
    if match:
        return int(match.group())
    return None


def validate_reminder_time(time_str: str) -> tuple[bool, datetime | str]:
    """Parse reminder time from various Russian-language formats."""
    time_str = time_str.strip().lower()

    # "завтра в 14:00"
    match = re.match(r"завтра\s+в?\s*(\d{1,2}):(\d{2})", time_str)
    if match:
        from datetime import timedelta
        now = datetime.utcnow()
        tomorrow = now + timedelta(days=1)
        dt = tomorrow.replace(
            hour=int(match.group(1)),
            minute=int(match.group(2)),
            second=0,
            microsecond=0,
        )
        return True, dt

    # "через N часов/минут"
    match = re.match(r"через\s+(\d+)\s+(час|мин|дн)", time_str)
    if match:
        from datetime import timedelta
        amount = int(match.group(1))
        unit = match.group(2)
        now = datetime.utcnow()
        if unit.startswith("час"):
            dt = now + timedelta(hours=amount)
        elif unit.startswith("мин"):
            dt = now + timedelta(minutes=amount)
        elif unit.startswith("дн"):
            dt = now + timedelta(days=amount)
        else:
            return False, "Неизвестная единица времени."
        return True, dt

    # "N дней HH:MM"
    match = re.match(r"(\d+)\s+дн\S*\s+(\d{1,2}):(\d{2})", time_str)
    if match:
        from datetime import timedelta
        days = int(match.group(1))
        hour = int(match.group(2))
        minute = int(match.group(3))
        now = datetime.utcnow()
        dt = (now + timedelta(days=days)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        return True, dt

    # Fallback to standard date format
    return validate_date(time_str)
