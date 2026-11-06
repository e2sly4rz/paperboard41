# Картонный Экспресс — Telegram-бот клуба настольных игр

Бот для управления игротеками: расписание, запись на игры, опросы о времени, напоминания, роли пользователей.

## Стек

- Python 3.13
- aiogram 3.13.1
- aiosqlite 0.20.0
- APScheduler 3.11.3
- aiogram_calendar 0.6.0
- python-dotenv 1.0.1

## Быстрый старт

1. Скопировать `.env.example` в `.env` и заполнить:
   - `BOT_TOKEN` — токен от @BotFather
   - `ADMIN_ID` — Telegram ID администратора
   - `DB_PATH` — путь к SQLite (по умолчанию `club.db`)
   - `CLUB_TIMEZONE` — часовой пояс (по умолчанию `Europe/Moscow`)

2. Установить зависимости:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

3. Запустить:
   ```bash
   python main.py
   ```

4. В production systemd-сервис (см. docs/DEPLOY.md).

## Структура проекта

```
club_bot/
├── main.py                  # точка входа
├── config.py                # чтение .env
├── utils.py                 # is_admin, is_host, fmt_date
├── notifications.py         # уведомления
├── scheduler.py             # напоминания (APScheduler)
├── database/
│   ├── db.py                # Database класс, схема, миграции
│   └── queries.py           # все SQL-запросы
├── handlers/
│   ├── start.py             # /start, /grant, /approve, /users
│   ├── schedule.py          # расписание, запись, опросы
│   ├── my_games.py          # мои записи
│   └── host/                # меню организатора
│       ├── menu.py          # карточка игротеки, участники
│       ├── create.py        # создание игротеки
│       ├── edit.py          # редактирование
│       ├── sessions.py      # управление играми
│       ├── delete.py        # удаление игротеки
│       ├── poll.py          # опросы о времени
│       └── _helpers.py      # can_manage_night, can_delete_session
├── keyboards/
│   └── menus.py             # все клавиатуры
├── middleware/
│   └── access.py            # AccessMiddleware
└── states/
    └── states.py            # FSM-состояния
```

## Документация

* docs/ARCHITECTURE.md — архитектура и решения
* docs/DATABASE.md — схема БД
* docs/USER_GUIDE.md — руководство пользователя
* docs/ADMIN_GUIDE.md — руководство администратора
* docs/DEPLOY.md — развёртывание и эксплуатация
* docs/CHANGELOG.md — история изменений
* docs/BACKLOG.md — что отложено на будущее