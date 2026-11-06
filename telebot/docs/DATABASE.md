# Схема базы данных

SQLite, файл `club.db`. Все таблицы создаются в `database/db.py` в `SCHEMA`, миграции — в `_run_migrations`.

## users

| Поле | Тип | Описание |
|---|---|---|
| `telegram_id` | INTEGER PK | ID пользователя |
| `username` | TEXT | @username (может быть NULL) |
| `first_name` | TEXT | Имя |
| `last_name` | TEXT | Фамилия |
| `subscriber_level` | TEXT NOT NULL | `host` / `provodnik` / `passenger`, CHECK |
| `is_approved` | INTEGER | 0 — заявка, 1 — одобрен |
| `created_at` | TIMESTAMP | Дата регистрации |

## games

| Поле | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK | |
| `title` | TEXT NOT NULL | Название |
| `genre` | TEXT | Жанр |
| `min_players` | INTEGER | Мин. игроков |
| `max_players` | INTEGER | Макс. игроков |
| `owner` | TEXT | Текстовое имя владельца (для «Клуб») |
| `owner_user_id` | INTEGER FK → users | Владелец-хост (NULL = клуб) |
| `duration_min` | INTEGER | Мин. длительность (мин) |
| `duration_max` | INTEGER | Макс. длительность (мин) |
| `is_subscriber_only` | INTEGER | 1 — только Проводник+ |
| `created_at` | TIMESTAMP | |

## game_nights

| Поле | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK | |
| `date` | DATE NOT NULL | Дата проведения (ISO `YYYY-MM-DD`) |
| `location` | TEXT NOT NULL | Место |
| `host_telegram_id` | INTEGER FK → users | Организатор |
| `created_at` | TIMESTAMP | |

## game_sessions

| Поле | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK | |
| `game_night_id` | INTEGER FK → game_nights | Игротека (ON DELETE CASCADE) |
| `game_id` | INTEGER FK → games | Игра |
| `time_start` | TEXT NOT NULL | Время начала `ЧЧ:ММ` |
| `time_end` | TEXT | Время окончания |
| `max_slots` | INTEGER NOT NULL | Всего мест |
| `slots_taken` | INTEGER DEFAULT 0 | Занято мест |
| `created_by_user_id` | INTEGER FK → users | Кто добавил игру |
| `registration_opens_at` | TIMESTAMP | Когда открывается запись (задел на будущее) |
| `registration_min_level` | TEXT DEFAULT 'passenger' | Мин. уровень для записи |
| `registration_approved` | INTEGER DEFAULT 1 | Флаг «одобрено хостом» (задел) |

## registrations

| Поле | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK | |
| `session_id` | INTEGER FK → game_sessions | Сессия (CASCADE) |
| `user_telegram_id` | INTEGER FK → users | Игрок |
| `registered_at` | TIMESTAMP | |

**Уникальный индекс** `(session_id, user_telegram_id)` — нельзя записаться дважды.

## notifications_log

| Поле | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK | |
| `user_id` | INTEGER FK → users | |
| `date` | DATE | Дата игротеки |
| `kind` | TEXT | `day_before` / `hour_before` |
| `sent_at` | TIMESTAMP | |

**Уникальный индекс** `(user_id, date, kind)` — не дублируются.

## availability_polls

| Поле | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK | |
| `game_night_id` | INTEGER FK → game_nights | Игротека (CASCADE) |
| `created_by_user_id` | INTEGER FK → users | Хост |
| `status` | TEXT DEFAULT 'open' | `open` / `closed`, CHECK |
| `closes_at` | TIMESTAMP | (задел) |
| `created_at` | TIMESTAMP | |

## availability_responses

| Поле | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK | |
| `poll_id` | INTEGER FK → availability_polls | Опрос (CASCADE) |
| `user_id` | INTEGER FK → users | Игрок |
| `time_from` | TEXT NOT NULL | `ЧЧ:ММ` |
| `time_to` | TEXT NOT NULL | `ЧЧ:ММ` |
| `created_at` | TIMESTAMP | |

**Уникальный индекс** `(poll_id, user_id)` — один ответ на пользователя. При повторном ответе — `ON CONFLICT DO UPDATE`.

## Индексы

- `idx_session_user` — уникальный по записям
- `idx_sessions_night` — сессии по игротеке
- `idx_games_owner` — игры по владельцу
- `idx_notif_unique` — уникальный по логу напоминаний
- `idx_avail_poll` — ответы по опросу
- `idx_sessions_created_by` — сессии по автору (создаётся в миграции)

## Миграции

`_run_migrations` в `db.py` идемпотентен. При запуске:
1. Добавляет отсутствующие колонки через `ALTER TABLE`.
2. Обновляет `guest` → `passenger`.
3. Создаёт индексы.

При добавлении новых колонок — добавлять проверку `_column_exists` и `ALTER TABLE` в `_run_migrations`.