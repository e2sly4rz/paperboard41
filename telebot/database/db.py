import aiosqlite
from config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id      INTEGER PRIMARY KEY,
    username         TEXT,
    first_name       TEXT,
    last_name        TEXT,
    subscriber_level TEXT DEFAULT 'guest',
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


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()

        cur = await db.execute("SELECT COUNT(*) FROM games")
        (count,) = await cur.fetchone()
        if count == 0:
            await db.executemany(
                """INSERT INTO games
                   (title, genre, min_players, max_players, owner,
                    duration_min, duration_max, is_subscriber_only)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    ("Catan", "Стратегия", 3, 4, "Клуб", 60, 120, 0),
                    ("Codenames", "Вечеринка", 4, 8, "Клуб", 15, 30, 0),
                    ("Gloomhaven", "Кооперативная", 1, 4, "Клуб", 90, 180, 1),
                    ("Ticket to Ride", "Семейная", 2, 5, "Клуб", 45, 75, 0),
                ],
            )
            await db.commit()