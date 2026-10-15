import aiosqlite
from config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id      INTEGER PRIMARY KEY,
    username         TEXT,
    first_name       TEXT,
    last_name        TEXT,
    subscriber_level TEXT DEFAULT 'guest',
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
    duration_min       INTEGER,
    duration_max       INTEGER,
    is_subscriber_only INTEGER DEFAULT 0,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game_night_id INTEGER NOT NULL,
    game_id       INTEGER NOT NULL,
    time_start    TEXT NOT NULL,
    time_end      TEXT,
    max_slots     INTEGER NOT NULL,
    slots_taken   INTEGER DEFAULT 0,
    FOREIGN KEY (game_night_id) REFERENCES game_nights(id) ON DELETE CASCADE,
    FOREIGN KEY (game_id)       REFERENCES games(id)
);

CREATE TABLE IF NOT EXISTS registrations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       INTEGER NOT NULL,
    user_telegram_id INTEGER NOT NULL,
    registered_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id)       REFERENCES game_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (user_telegram_id) REFERENCES users(telegram_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_session_user
    ON registrations(session_id, user_telegram_id);

CREATE INDEX IF NOT EXISTS idx_sessions_night
    ON game_sessions(game_night_id);
"""


async def _migrate_add_is_approved(db: aiosqlite.Connection) -> None:
    """Добавляет колонку is_approved, если её нет.

    Нужно, потому что CREATE TABLE IF NOT EXISTS не меняет структуру
    существующей таблицы. Для старых БД поле добавляется через ALTER.
    """
    cur = await db.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in await cur.fetchall()]
    if "is_approved" not in columns:
        await db.execute(
            "ALTER TABLE users ADD COLUMN is_approved INTEGER DEFAULT 0"
        )
        await db.commit()


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()
        await _migrate_add_is_approved(db)