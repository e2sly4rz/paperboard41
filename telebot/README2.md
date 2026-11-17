# 🎲 Картонный Экспресс — Telegram-бот клуба настольных игр

Бот для клуба настольных игр: расписание игротек, запись на игры, управление игротеками, опросы о времени, вишлист.

**Стек:** Python 3.13, aiogram 3.13, aiosqlite, APScheduler, SQLite.

---

## 📑 Оглавление

- [Общее описание](#общее-описание)
- [Роли и доступ](#роли-и-доступ)
- [Структура проекта](#структура-проекта)
- [Модель данных](#модель-данных)
- [Правила записи](#правила-записи)
- [Пользовательские сценарии](#пользовательские-сценарии)
- [Сценарии организатора](#сценарии-организатора)
- [Уведомления](#уведомления)
- [Фон (scheduler)](#фон-scheduler)
- [Инфраструктура](#инфраструктура)
- [Известные особенности и мёртвый код](#известные-особенности-и-мёртвый-код)
- [Команды](#команды)
- [Быстрый старт](#быстрый-старт)
- [Бэклог](#бэклог)

---

## Общее описание

Бот обслуживает клуб настольных игр. Пользователи смотрят расписание игротек, записываются на игры. Организаторы создают игротеки, добавляют игры, открывают запись, собирают опросы о удобном времени, ведут вишлист.

**Основные сущности:**

- **Игротека** (`game_nights`) — событие: дата, место, хост, платная/бесплатная, флаг открытия записи.
- **Сессия** (`game_sessions`) — игра в игротеке: время, слоты, автор.
- **Игра** (`games`) — каталог игр клуба.
- **Запись** (`registrations`) — пользователь записан на сессию.
- **Опрос** (`availability_polls` + `availability_responses`) — сбор удобного времени.
- **Вишлист** (`wishlist_items`) — игры, которые проводник/хост хочет видеть в клубе.

---

## Роли и доступ

| Уровень | `subscriber_level` | Что может |
|---|---|---|
| Гость | `guest` | Смотреть расписание, записываться на **бесплатные** игротеки, отвечать на опросы (бесплатные), отменять свои записи. **Не может** на платные, в меню организатора, в вишлист. |
| Пассажир | `passenger` | Всё, что гость, плюс запись на **платные** — за 8 ч до игры или когда все проводники записались (и прошло 15 мин). |
| Проводник | `provodnik` | Всё, что пассажир, плюс запись на платные **сразу** после открытия, доступ к играм `is_subscriber_only`, **вишлист** (свой + сводка). |
| Хост | `host` | Всё, что проводник, плюс **меню организатора**: создание/редактирование/удаление игротек, добавление игр в каталог, открытие записи, опросы, **вишлисты проводников**. |
| Админ | `ADMIN_ID` (env) | Всё, что хост, плюс управление доступом (`/approve`, `/revoke`, `/grant`), `/users`, справка. |

**Модерация:** новый пользователь создаётся с `is_approved=0`, `subscriber_level='guest'`. Доступ — после `/approve` (или кнопки «✅ Одобрить» в заявке). Middleware (`middleware/access.py`) пропускает только одобренных + админа + `/start`.

---

## Структура проекта

.
├── main.py # точка входа: db, bot, dispatcher, scheduler
├── config.py # env: BOT_TOKEN, ADMIN_ID, DB_PATH, CLUB_TIMEZONE
├── club.db # SQLite
├── requirements.txt
├── database/
│ ├── db.py # Database, SCHEMA, миграции
│ └── queries.py # все SQL-запросы
├── handlers/
│ ├── init.py # setup_routers
│ ├── start.py # /start, /approve, /grant, /users, /help, /id
│ ├── schedule.py # расписание, карточка ночи, запись, опросы
│ ├── my_games.py # мои записи, отмена
│ ├── wishlist.py # вишлист (свой, сводка, хостовый)
│ └── host/
│ ├── init.py
│ ├── menu.py # меню организатора, карточка ночи
│ ├── create.py # создание ночи (FSM CreateNight)
│ ├── edit.py # редактирование даты/места
│ ├── sessions.py # управление играми (FSM AddSessionToNight)
│ ├── delete.py # удаление ночи (с уведомлением записанным)
│ ├── poll.py # опросы (создание, результаты, закрытие)
│ ├── game.py # добавление игры в каталог (FSM AddGame)
│ ├── open.py # открытие записи + рассылка
│ └── _helpers.py # can_manage_night, can_delete_session, add_minutes
├── keyboards/
│ └── menus.py # все inline-клавиатуры
├── middleware/
│ └── access.py # AccessMiddleware
├── notifications.py # все уведомления
├── scheduler.py # напоминания + пассажирские рассылки
├── states/
│ └── states.py # FSM-состояния
├── time_utils.py # club_now, session_datetime
└── utils.py # is_admin, is_host_or_admin, fmt_date, safe_edit


---

## Модель данных

### `users`

| Поле | Тип | Описание |
|---|---|---|
| `telegram_id` | INTEGER PK | Telegram ID |
| `username`, `first_name`, `last_name` | TEXT | Профиль |
| `subscriber_level` | TEXT | `host` / `provodnik` / `passenger` / `guest` (дефолт `guest`) |
| `is_approved` | INTEGER | 0/1, доступ |
| `created_at` | TIMESTAMP | |

### `games`

| Поле | Описание |
|---|---|
| `id` | PK |
| `title`, `genre` | Название, жанр |
| `min_players`, `max_players` | Игроки |
| `duration_min`, `duration_max` | Длительность |
| `is_subscriber_only` | 0/1, только для Проводников |
| `owner`, `owner_user_id` | Владелец (снимок имени + FK) |

### `game_nights`

| Поле | Описание |
|---|---|
| `id` | PK |
| `date`, `location` | Дата, место |
| `host_telegram_id` | Хост (FK users) |
| `is_free` | 0/1, бесплатная/платная |
| `registration_open` | 0/1 |
| `registration_opened_at/by` | Когда/кем открыта |
| `passenger_notified_at` | Когда разослано пассажирам |

### `game_sessions`

| Поле | Описание |
|---|---|
| `id` | PK |
| `game_night_id` (FK CASCADE), `game_id` (FK) | Ночь, игра |
| `time_start`, `time_end` | Время |
| `max_slots`, `slots_taken` | Слоты |
| `created_by_user_id` | Автор сессии |
| `registration_min_level` | `passenger` / `provodnik` (мёртвое в UI) |
| `registration_approved` | 0/1 (мёртвое) |

### `registrations`

`id`, `session_id` (FK CASCADE), `user_telegram_id` (FK), `registered_at`. UNIQUE(session_id, user).

### `notifications_log`

`id`, `user_id`, `date`, `kind`, `sent_at`. UNIQUE(user, date, kind) — защита от повторных напоминаний.

### `availability_polls` / `availability_responses`

- Опрос: `id`, `game_night_id` (FK CASCADE), `created_by_user_id`, `status` (`open`/`closed`), `closes_at` (не используется), `created_at`.
- Ответ: `id`, `poll_id` (FK CASCADE), `user_id` (FK), `status` (`available`/`unavailable`), `time_from`, `time_to`, UNIQUE(poll_id, user_id).

### `wishlist_items`

| Поле | Описание |
|---|---|
| `id` | PK |
| `user_id` (FK users), `game_id` (FK games) | Кто и какую игру |
| `status` | `active` / `fulfilled` / `removed` |
| `created_at` | |
| `closed_at`, `closed_by`, `close_reason` | Когда/кем/почему закрыт (`played`, `irrelevant`, `self`; без CHECK — расширяемо) |

**Индексы:** `idx_session_user`, `idx_sessions_night`, `idx_games_owner`, `idx_notif_unique`, `idx_avail_poll`, `idx_sessions_created_by`, `idx_wishlist_user`, `idx_wishlist_game`.

**Миграции** (`database/db.py: _run_migrations`): добавляют недостающие колонки (`is_approved`, `owner_user_id`, `created_by_user_id`, `registration_*`, `registration_open`, `is_free`), пересоздают `availability_responses` под `status`, создают индексы.

---

## Правила записи

**`can_register_for_night(night_id, user_id)`** (`database/queries.py`):

1. Админ или `host` — **всегда**.
2. **Бесплатная** (`is_free=1`): если `registration_open=1` — **всем уровням** (guest/passenger/provodnik/host/админ). Без 8 часов/проводников/таймаутов.
3. **Платная** (`is_free=0`):
   - `guest` — **нельзя** («только для участников клуба»).
   - `provodnik` — **сразу** после `registration_open=1`.
   - `passenger` — если `delta <= 8 ч` до самой ранней игры **или** `can_passengers_register_early` = True.
   - `registration_open=0` — **никому**, кроме админа/хоста (они могут всегда).

**`can_passengers_register_early(night_id)`** — эвристика «проводники закончились»:

- Запись открыта, есть свободные места.
- Берутся **не записанные** проводники (в этой ночи).
- Если есть **последний опрос** (открытый или закрытый) — исключаются ответившие `unavailable`; для ответивших `available` игра должна попадать в окно `time_from–time_to`.
- Если у **любого** доступного проводника есть свободная сессия без конфликта — `False` (пассажиры ждут).
- Иначе — проверка таймаута: последняя запись проводника/хоста в ночи **≥ 15 минут** назад. Если да — `True`.

**`register_for_session`** — в транзакции:

- `can_register_for_night` → отказ.
- `is_subscriber_only` и уровень не provodnik/host → отказ.
- `registration_min_level=provodnik` и passenger — **только для платных** (на бесплатных не применяется).
- Свободные места, дубль, конфликт по времени в пределах **даты**.
- INSERT + `slots_taken+1`.

**Отмена** — `cancel_registration(reg_id, user_id)` (только своя), декремент, уведомление автору сессии.

---

## Пользовательские сценарии

### `/start`

- `ensure_user` (upsert профиля, `is_approved` не трогает).
- **Админ:** приветствие + число заявок, меню с «❓ Справка».
- **Не одобрен:** «заявка отправлена» + пуш админу с кнопкой «✅ Одобрить».
- **Гость:** «Вы гость… бесплатные игротеки 🆓».
- **Хост:** «Вы организатор…».
- **Проводник/пассажир:** приветствие + пометка про «Проводник» (для проводника).

### Главное меню

`main_menu(is_host, user_id, is_provodnik)`:

- 📅 Расписание
- 🎲 Мои записи
- ⭐ Вишлист (если `is_provodnik or is_host`)
- 🎩 Меню организатора (если `is_host`)
- ❓ Справка (если админ)

### Расписание

- `schedule` → список ночей: `🔒` (закрыта) / `🆓`/`💰` (бесплатная/платная).
- `night:<id>` → карточка:
  - шапка: дата, тип (🆓/💰), место, «Игр: N • Записей: M», причина блокировки (`ℹ️ …`), «📊 опрос».
  - список игр: **номер + жирное время** (`18:00–20:00`), на следующей строке — **название (полное) + занятость + ⭐/⛔**, пустая строка между играми.
  - кнопки: `[1]…[N]` в 5 колонок, `⏰ Указать удобное время` / `❌ Не смогу прийти` (если опрос), `⬅️ К расписанию`.
- `session:<id>` → карточка сессии: игра, дата, время, место, тип, занятость; `⭐` если subscriber-only; кнопка «✅ Записаться» (если можно).
- `reg:<id>` → запись, алерт, уведомление автору.

### Мои записи

`my_games` → список «❌ дата время — игра» (кнопка отмены) или «нет записей».
`cancel:<reg_id>` → отмена, уведомление автору.

### Опрос о времени

`poll_answer:<night_id>` → FSM `PollTime.picking_from` (сетка 10:00–23:00 + «❌ Не смогу»).
`pollfrom:HH:00` → `PollTime.picking_to` (сетка после выбранного).
`pollto:HH:00` → проверка `to > from`, `upsert_availability_response`.
`poll_unavailable` (FSM) / `poll_unavailable_notify:<night_id>` (из уведомления) → `unavailable`.

### Вишлист (проводник/хост)

- `wishlist` → «Мой вишлист (N из 5)», список, кнопки: «➕ Добавить», «🗑 Название» (на каждый), «📊 Сводка», «⬅️ Назад».
- `wishlist_add` → FSM `Wishlist.searching_game` → поиск по каталогу → `Wishlist.picking_game` → `wishlist_pick:<game_id>` → добавлено.
- `wishlist_remove:<item_id>` → удалить свой пункт (`status='removed'`).
- `wishlist_summary` → «Чего хотят проводники»: игра → N чел. (имена).

---

## Сценарии организатора

### Меню

`host_menu` (только `is_host_or_admin`):

- ➕ Создать игротеку
- 📚 Добавить игру в каталог
- ⭐ Вишлисты проводников
- список ночей (🎩 свои / 👀 чужие)
- ⬅️ Назад

### Карточка ночи (`hn:<id>`)

- дата, место, 🆓/💰, игр/записей, статус записи, активный опрос.
- участники по сессиям (имя + @username).
- кнопки: ➕ Добавить игру, 🎲 Управление играми, 🔓 Открыть запись (если хозяин и не открыта), 📊 Результаты/Закрыть опрос/Создать опрос, 📅 Изменить дату, 📍 Изменить место, 🗑 Удалить игротеку, ⬅️ К списку.

### Создание ночи (`CreateNight`)

`host_create` → календарь (`SimpleCalendar`, ru_RU, today..+365) → `date` → место → **«💰 Платная / 🆓 Бесплатная»** → поиск игры (≥2 символа) → выбор → время начала (сетка 10–23 или вручную) → длительность (1–6 ч с ✓ по `duration_min/max`, или вручную) → слоты (авто `max_players`, или `min..max`, или вручную) → `_finalize_session`.

- `_finalize_session`: `find_host_conflict` по `user_id` и дате → создать ночь при необходимости (`is_free` из FSM) → `add_session` → «➕ Ещё / ✅ Завершить / ❌ Отмена».
- `host_finish`: есть `night_id` → карточка; есть дата+место → создать пустую ночь; иначе — ошибка.
- `host_add_more`, `host_cancel`, `host_create_search_again`.

### Редактирование (`EditNight`)

`hn_date:<id>` (ДД.ММ.ГГГГ), `hn_loc:<id>` (≥3 символа), обе через `can_manage_night`.

### Управление играми (`hn_sessions:<id>`)

- Список: «🗑 время — игра (занято/всего)» для тех, кого можно удалять (`can_delete_all` для хоста ночи/админа, иначе только свои), «•» для чужих (callback `noop`).
- `hs_del:<session_id>` → подтверждение (с предупреждением о записанных, о чужой ночи) → `hs_del_yes` → `delete_session` + уведомления: хосту ночи (`notify_session_deleted`), записанным (`notify_registrants_deleted`), владельцу игры (`notify_game_owner_deleted`).
- `hn_add:<night_id>` → `AddSessionToNight` (поиск → выбор → время → длительность → слоты) → `_finalize_add_session` (конфликт по `user_id`, `created_by_user_id=user_id`).

### Удаление ночи (`delete.py`)

`hn_del:<id>` → подтверждение («…придёт уведомление») → `hn_del_yes`:

- до удаления: собрать записанных (`get_all_night_registrations`), сгруппировать по `telegram_id` (`registrants_map`, `games_by_user`).
- `delete_night` (каскад).
- `notify_night_deleted` (каждому записанному — «❌ Игротека отменена» + список их игр).
- возврат в меню организатора.

### Каталог (`AddGame`)

`host_add_game` → title (≥2, уникальность `game_title_exists`) → players «min-max» → duration «min-max» → subscriber_only (кнопки) → `create_game` c `owner_user_id` и `owner_label`. `game_cancel`.

### Открытие записи (`open.py`)

`night_open:<id>` → только `can_manage_night`, идемпотентно → `open_night_registration` → рассылка:

- **платная:** `provodnik`+`host` (`target_level="provodnik"`, `early=False`).
- **бесплатная:** `passenger`+`provodnik`+`guest` (кроме хостов; `target_level="passenger"`, `early=True`).
- `notify_registration_opened` (кнопка «📅 Открыть расписание»).
- карточка с «Запись открыта», «Уведомлено: N».

### Опросы (`poll.py`)

- `poll_create:<id>` — только `is_host_or_admin`, один активный на ночь, `create_availability_poll` (без `closes_at`), рассылка всем, кроме хоста ночи (`notify_poll_created`, 2 кнопки; на платной — гости исключены).
- `poll_results:<id>` — гистограмма по часам 10–23 (available, `from ≤ h < to`), списки available/unavailable, обрезка 4000.
- `poll_close:<id>` — `close_availability_poll`.

### Вишлисты проводников (`wishlist.py`)

- `host_wishlists` → «Вишлисты проводников», группировка по пользователю (имя + @username), пункты.
- `host_wishlist_close:<item_id>` → выбор причины (`✅ Поиграл` / `🚫 Неактуально`).
- `wishlist_close:<item_id>:<reason>` → `close_wishlist_item` → уведомление проводнику (`notify_wishlist_closed`) → перерисовать список.

---

## Уведомления

| # | Событие | Кому | Кнопки |
|---|---|---|---|
| 1 | Новая заявка | Админ | «✅ Одобрить» (`approve_user:{id}`) |
| 2 | Доступ открыт | Пользователь | — |
| 3 | Запись открыта (платная, `night_open`) | `provodnik`+`host` | «📅 Открыть расписание» |
| 4 | Запись открыта (бесплатная, `night_open`) | `passenger`+`provodnik`+`guest` (кроме хостов) | «📅 Открыть расписание» |
| 5 | Запись открыта (фон, платная ≤ 8 ч) | `passenger` | «📅 Открыть расписание» |
| 6 | Запись открыта раньше (фон, платная, проводники закончились) | `passenger` | «📅 Открыть расписание» |
| 7 | Опрос создан | все, кроме хоста ночи (на платной — кроме гостей) | «⏰ Указать время» / «❌ Не смогу» |
| 8 | Новая запись на вашу игру | автор сессии | — |
| 9 | Игрок отменил запись | автор сессии | — |
| 10 | Игра удалена из игротеки | хосту ночи | — |
| 11 | Игра отменена | записанным | — |
| 12 | Ваша игра удалена из игротеки | владельцу игры | — |
| 13 | Напоминание «завтра» / «через час» | записанным | — |
| 14 | Игротека отменена | записанным | — |
| 15 | Вишлист обновлён | проводнику | — |

**Тексты:** `notifications.py` — `notify_*`. Отправка — `_safe_send` (Forbidden/RetryAfter → лог, не падает), рассылки — `_send_with_delay` (1 сек между).

---

## Фон (scheduler)

`scheduler.py`, каждые 10 минут.

**`check_and_send_reminders`:**

- Записи на сегодня и завтра (`get_user_day_registrations`), группировка по (user, date).
- Если до первой игры `23 ≤ Δ ≤ 25 ч` → `day_before`; `50 ≤ Δ ≤ 70 мин` → `hour_before`.
- Защита от повтора через `notifications_log` (UNIQUE user+date+kind).
- Текст: «Напоминание: игра завтра/через час», дата, место, список игр.

**`check_passenger_registration_notifications`:**

- `get_nights_for_passenger_notification`: `registration_open=1`, `passenger_notified_at IS NULL`, дата ≥ сегодня, и:
  - бесплатная → `early=True` сразу;
  - платная → `0 ≤ Δ ≤ 8 ч` (`early=False`) или `can_passengers_register_early` (`early=True`).
- Для бесплатной: получатели `passenger`+`provodnik`+`guest` (кроме хостов). Для платной: `passenger`.
- `notify_registration_opened` → `mark_passenger_notified` (даже если 0 получателей).

**Авто-закрытия опросов нет** — только вручную. `closes_at` не заполняется.

---

## Инфраструктура

- **`main.py`:** `db.connect` → `init_db` → `Bot` (proxy из env, `DefaultBotProperties(HTML)`) → `Dispatcher` + `AccessMiddleware` на `dp.update` → `include_router(setup_routers())` → `start_scheduler(bot)` → `dp.start_polling(bot, polling_timeout=20)`.
- **`config.py`:** `BOT_TOKEN`, `ADMIN_ID`, `DB_PATH`, `CLUB_TIMEZONE` (env, дефолт `Europe/Moscow`).
- **`middleware/access.py`:** пропускает одобренных + админа + `/start`; кладёт `data["user"]`.
- **`utils.py`:** `is_admin`, `is_host`, `is_host_or_admin`, `is_provodnik_or_higher`, `fmt_date`, `safe_edit` (глотает «message is not modified»).
- **`time_utils.py`:** `club_now()`, `session_datetime(iso_date, time_str)`.
- **`requirements.txt`:** `aiogram==3.13.1`, `aiosqlite==0.20.0`, `python-dotenv==1.0.1`, `aiohttp-socks==0.9.0`, `apscheduler==3.10.4`, `aiogram_calendar>=0.6`.
- **Запуск:** `systemctl restart club-bot`, логи `journalctl -u club-bot -f`.

---

## Известные особенности и мёртвый код

- **`game_sessions.registration_opens_at`** — не используется.
- **`game_sessions.registration_approved`** — не используется.
- **`game_sessions.registration_min_level`** — проверяется только для платных (на бесплатных не применяется), UI не выставляет.
- **`availability_polls.closes_at`** — не заполняется, авто-закрытия нет.
- **`games.genre`** — UI не спрашивает, всегда `NULL` (но выводится в карточке сессии, если есть).
- **`games.owner` (TEXT)** — снимок имени, дублирует `owner_user_id`.
- **`sessions_list`** и **`_short_title`** в `keyboards/menus.py` — **удалены** (мёртвый код).
- **Хост/админ могут записываться до `night_open`** — осознанно (не баг).
- **Правило А (проводники закончились)** — учитывает **последний** опрос (открытый или закрытый), ответы `unavailable` исключают проводника, `available` ограничивает окном.
- **Уже записанный проводник не блокирует** пассажиров (вариант A, осознанно).
- **Таймаут 15 минут** — после последней записи проводника/хоста, перед открытием пассажирам.

---

## Команды

| Команда | Кто | Что |
|---|---|---|
| `/start` | все | главное меню / заявка |
| `/id` | все | свой Telegram ID |
| `/help` | админ | справка по командам |
| `/pending` | админ | список заявок |
| `/approve <id>` | админ | одобрить |
| `/revoke <id>` | админ | отозвать доступ |
| `/grant <id> host\|provodnik\|passenger\|guest` | админ | сменить уровень |
| `/users` | админ | все пользователи по группам |

---

## Быстрый старт

```bash
cd /home/bot/telebot
source venv/bin/activate

# зависимости
pip install -r requirements.txt

# .env
BOT_TOKEN=...
ADMIN_ID=...
DB_PATH=club.db
CLUB_TIMEZONE=Europe/Moscow

# бэкап БД (обязательно перед миграциями)
cp club.db club.db.bak-$(date +%F)

# запуск
python main.py
# или
sudo systemctl restart club-bot
sudo journalctl -u club-bot -f