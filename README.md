# Telegram Planner Bot

Персональный бот-планировщик для Telegram: управление задачами, проектами, напоминаниями и статистикой продуктивности.

## Возможности

- **Задачи** — создание, редактирование, приоритеты (HIGH/MEDIUM/LOW), дедлайны, теги, поиск
- **Проекты** — группировка задач, статистика по проекту, прогресс-бар
- **Напоминания** — автоматические (за 24ч и 1ч до дедлайна), утренний дайджест, кастомные
- **Календарь** — интерактивный месячный вид с отметками задач
- **Статистика** — базовая и расширенная аналитика, отчёты о продуктивности, ASCII-графики
- **Inline-кнопки** — удобное управление без ввода команд

## Технический стек

| Компонент | Технология |
|-----------|------------|
| Язык | Python 3.11+ |
| Telegram API | python-telegram-bot 20.x |
| ORM | SQLAlchemy 2.0 (async) |
| БД | PostgreSQL + asyncpg |
| Миграции | Alembic |
| Планировщик | APScheduler |
| Кэш | Redis (опционально) |

## Структура проекта

```
telegram_planner_bot/
├── main.py                          # Точка входа
├── config.py                        # Конфигурация
├── alembic.ini                      # Настройки Alembic
├── requirements.txt
├── .env.example
├── database/
│   ├── models.py                    # SQLAlchemy модели
│   ├── db.py                        # Подключение и сессии
│   └── migrations/                  # Alembic миграции
├── handlers/
│   ├── commands.py                  # Обработчики /команд
│   ├── callbacks.py                 # Обработчики inline-кнопок
│   └── messages.py                  # Обработчики текстовых сообщений
├── services/
│   ├── task_service.py              # Бизнес-логика задач
│   ├── project_service.py           # Бизнес-логика проектов
│   ├── reminder_service.py          # Управление напоминаниями
│   └── stats_service.py             # Расчёт статистики
├── utils/
│   ├── formatters.py                # Форматирование вывода
│   ├── validators.py                # Валидация данных
│   ├── date_utils.py                # Работа с датами
│   └── keyboards.py                 # Конструирование клавиатур
├── scheduler/
│   └── reminders_scheduler.py       # APScheduler для напоминаний
└── logs/                            # Логи (ротация 5 МБ)
```

## Установка и запуск

### 1. Клонирование и зависимости

```bash
cd telegram_planner_bot
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### 2. Настройка окружения

```bash
cp .env.example .env
```

Отредактируйте `.env`:
- `BOT_TOKEN` — токен от [@BotFather](https://t.me/BotFather)
- `DATABASE_URL` — строка подключения PostgreSQL
- `DATABASE_URL_SYNC` — синхронная строка (для Alembic)

### 3. Создание базы данных

```bash
# Создайте БД в PostgreSQL
createdb planner_bot

# Выполните миграции
alembic upgrade head
```

### 4. Запуск бота

```bash
python main.py
```

Бот запустится в режиме long polling. Для webhook добавьте в `.env`:
```
USE_WEBHOOK=true
WEBHOOK_URL=https://yourdomain.com
WEBHOOK_PORT=8443
```

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Инициализация и главное меню |
| `/help` | Список всех команд |
| `/add_task <название>` | Создать задачу |
| `/list_tasks` | Список задач с фильтрами |
| `/edit_task <id>` | Редактировать задачу |
| `/complete_task <id>` | Отметить как выполненную |
| `/delete_task <id>` | Удалить задачу |
| `/task_details <id>` | Подробности задачи |
| `/search <запрос>` | Поиск по задачам |
| `/add_project <название>` | Создать проект |
| `/list_projects` | Список проектов |
| `/project_stats <id>` | Статистика проекта |
| `/set_reminder <task_id> <время>` | Установить напоминание |
| `/list_reminders` | Активные напоминания |
| `/calendar` | Календарь на месяц |
| `/stats` | Основная статистика |
| `/stats_detailed` | Расширенная аналитика |
| `/productivity_report <период>` | Отчёт (day/week/month/quarter) |

## Форматы времени для напоминаний

- `завтра в 14:00`
- `через 2 часа`
- `через 30 минут`
- `3 дня 15:30`
- `16.04.2026 18:00`

## Деплой (Production)

1. Используйте webhook вместо polling
2. Настройте PostgreSQL с SSL
3. Запускайте через systemd/supervisor/Docker
4. Включите Redis для кэширования (`USE_REDIS=true`)

### Docker (пример)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

## Лицензия

MIT
