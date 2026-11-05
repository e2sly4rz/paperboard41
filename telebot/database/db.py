import aiosqlite
from config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id      INTEGER PRIMARY KEY,
    username         TEXT,
    first_name       TEXT,
    last_name        TEXT,
    subscriber_level TEXT NOT NULL DEFAULT 'passenger'
        CHECK (subscriber_level IN ('host', 'provodnik', 'passenger')),
    is_approved      INTEGER DEFAULT 0,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS games (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    title              TEXT NOT NULL,
    genre              TEXT,
    min_players        INTEGER,
    max_players        INTEGER,
    owner              TEXT,
    owner_user_id      INTEGER,
    duration_min       INTEGER,
    duration_max       INTEGER,
    is_subscriber_only INTEGER DEFAULT 0,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_user_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS game_nights (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    date             DATE NOT NULL,
    location         TEXT NOT NULL,
    host_telegram_id INTEGER,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (host_telegram_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS game_sessions (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    game_night_id            INTEGER NOT NULL,
    game_id                  INTEGER NOT NULL,
    time_start               TEXT NOT NULL,
    time_end                 TEXT,
    max_slots                INTEGER NOT NULL,
    slots_taken              INTEGER DEFAULT 0,
    created_by_user_id       INTEGER,
    registration_opens_at    TIMESTAMP,
    registration_min_level   TEXT NOT NULL DEFAULT 'passenger'
        CHECK (registration_min_level IN ('provodnik', 'passenger')),
    registration_approved    INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (game_night_id)      REFERENCES game_nights(id) ON DELETE CASCADE,
    FOREIGN KEY (game_id)            REFERENCES games(id),
    FOREIGN KEY (created_by_user_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS registrations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       INTEGER NOT NULL,
    user_telegram_id INTEGER NOT NULL,
    registered_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id)       REFERENCES game_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (user_telegram_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS notifications_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    date       DATE NOT NULL,
    kind       TEXT NOT NULL,
    sent_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS availability_polls (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    game_night_id      INTEGER NOT NULL,
    created_by_user_id INTEGER NOT NULL,
    status             TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed')),
    closes_at          TIMESTAMP,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_night_id)      REFERENCES game_nights(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by_user_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS availability_responses (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_id    INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    time_from  TEXT NOT NULL,
    time_to    TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (poll_id, user_id),
    FOREIGN KEY (poll_id) REFERENCES availability_polls(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_session_user
    ON registrations(session_id, user_telegram_id);

CREATE INDEX IF NOT EXISTS idx_sessions_night
    ON game_sessions(game_night_id);

CREATE INDEX IF NOT EXISTS idx_games_owner
    ON games(owner_user_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_notif_unique
    ON notifications_log(user_id, date, kind);

CREATE INDEX IF NOT EXISTS idx_avail_poll
    ON availability_responses(poll_id);
"""


async def _column_exists(db: aiosqlite.Connection, table: str, column: str) -> bool:
    cur = await db.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in await cur.fetchall()]
    return column in columns


async def _run_migrations(db: aiosqlite.Connection) -> None:
    # users.is_approved
    if not await _column_exists(db, "users", "is_approved"):
        await db.execute(
            "ALTER TABLE users ADD COLUMN is_approved INTEGER DEFAULT 0"
        )

    # users.subscriber_level: guest → passenger
    await db.execute(
        "UPDATE users SET subscriber_level = 'passenger' "
        "WHERE subscriber_level = 'guest'"
    )

    # games.owner_user_id
    if not await _column_exists(db, "games", "owner_user_id"):
        await db.execute(
            "ALTER TABLE games ADD COLUMN owner_user_id INTEGER"
        )

    # game_sessions.created_by_user_id
    if not await _column_exists(db, "game_sessions", "created_by_user_id"):
        await db.execute(
            "ALTER TABLE game_sessions ADD COLUMN created_by_user_id INTEGER"
        )

    # game_sessions.registration_opens_at
    if not await _column_exists(db, "game_sessions", "registration_opens_at"):
        await db.execute(
            "ALTER TABLE game_sessions ADD COLUMN registration_opens_at TIMESTAMP"
        )

    # game_sessions.registration_min_level
    if not await _column_exists(db, "game_sessions", "registration_min_level"):
        await db.execute(
            "ALTER TABLE game_sessions ADD COLUMN registration_min_level "
            "TEXT NOT NULL DEFAULT 'passenger'"
        )

    # game_sessions.registration_approved
    if not await _column_exists(db, "game_sessions", "registration_approved"):
        await db.execute(
            "ALTER TABLE game_sessions ADD COLUMN registration_approved "
            "INTEGER NOT NULL DEFAULT 1"
        )

    # Индексы, которые нельзя ставить в SCHEMA до миграции колонок
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_created_by "
        "ON game_sessions(created_by_user_id)"
    )

    await db.commit()


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()
        await _run_migrations(db)