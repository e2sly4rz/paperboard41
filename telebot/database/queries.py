import aiosqlite
from config import DB_PATH


# ---------- Пользователи ----------

async def ensure_user(telegram_id: int, username: str | None,
                      first_name: str | None, last_name: str | None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (telegram_id, username, first_name, last_name)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET
                   username   = excluded.username,
                   first_name = excluded.first_name,
                   last_name  = excluded.last_name""",
            (telegram_id, username, first_name, last_name),
        )
        await db.commit()


async def get_user(telegram_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def set_user_level(telegram_id: int, level: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET subscriber_level = ? WHERE telegram_id = ?",
            (level, telegram_id),
        )
        await db.commit()


# ---------- Каталог игр ----------

async def list_games() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM games ORDER BY title")
        return [dict(r) for r in await cur.fetchall()]


async def get_game(game_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM games WHERE id = ?", (game_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


# ---------- Игротеки и сессии ----------

async def create_game_night(date: str, location: str,
                            host_telegram_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO game_nights (date, location, host_telegram_id)
               VALUES (?, ?, ?)""",
            (date, location, host_telegram_id),
        )
        await db.commit()
        return cur.lastrowid


async def add_session(game_night_id: int, game_id: int, time_start: str,
                      time_end: str | None, max_slots: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO game_sessions
               (game_night_id, game_id, time_start, time_end, max_slots)
               VALUES (?, ?, ?, ?, ?)""",
            (game_night_id, game_id, time_start, time_end, max_slots),
        )
        await db.commit()
        return cur.lastrowid


async def list_upcoming_nights() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT gn.id, gn.date, gn.location,
                      COUNT(gs.id) AS sessions_count
               FROM game_nights gn
               LEFT JOIN game_sessions gs ON gs.game_night_id = gn.id
               WHERE gn.date >= date('now')
               GROUP BY gn.id
               ORDER BY gn.date"""
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_night_sessions(night_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT gs.id, gs.time_start, gs.time_end, gs.max_slots,
                      gs.slots_taken,
                      (gs.max_slots - gs.slots_taken) AS free_slots,
                      g.title, g.genre, g.min_players, g.max_players,
                      g.duration_min, g.duration_max, g.is_subscriber_only
               FROM game_sessions gs
               JOIN games g ON g.id = gs.game_id
               WHERE gs.game_night_id = ?
               ORDER BY gs.time_start""",
            (night_id,),
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_session(session_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT gs.*, g.title, g.genre, g.owner,
                      g.min_players, g.max_players,
                      g.is_subscriber_only,
                      gn.date, gn.location,
                      (gs.max_slots - gs.slots_taken) AS free_slots
               FROM game_sessions gs
               JOIN games g       ON g.id  = gs.game_id
               JOIN game_nights gn ON gn.id = gs.game_night_id
               WHERE gs.id = ?""",
            (session_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


# ---------- Записи на игры ----------

async def register_for_session(session_id: int, user_id: int) -> tuple[bool, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("BEGIN")

            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """SELECT gs.max_slots, gs.slots_taken,
                          g.is_subscriber_only,
                          u.subscriber_level
                   FROM game_sessions gs
                   JOIN games g ON g.id = gs.game_id
                   JOIN users u ON u.telegram_id = ?
                   WHERE gs.id = ?""",
                (user_id, session_id),
            )
            row = await cur.fetchone()
            if row is None:
                await db.rollback()
                return False, "Сессия не найдена или пользователь не зарегистрирован."

            if row["is_subscriber_only"] and row["subscriber_level"] not in ("provodnik", "host"):
                await db.rollback()
                return False, "Эта игра доступна только подписчикам уровня «Проводник»."

            if row["slots_taken"] >= row["max_slots"]:
                await db.rollback()
                return False, "Свободных мест больше нет."

            cur = await db.execute(
                "SELECT 1 FROM registrations WHERE session_id = ? AND user_telegram_id = ?",
                (session_id, user_id),
            )
            if await cur.fetchone():
                await db.rollback()
                return False, "Вы уже записаны на эту игру."

            await db.execute(
                "INSERT INTO registrations (session_id, user_telegram_id) VALUES (?, ?)",
                (session_id, user_id),
            )
            await db.execute(
                "UPDATE game_sessions SET slots_taken = slots_taken + 1 WHERE id = ?",
                (session_id,),
            )
            await db.commit()
            return True, "Вы успешно записаны!"
        except Exception as e:
            await db.rollback()
            return False, f"Ошибка записи: {e}"


async def list_user_registrations(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT r.id AS reg_id, gs.id AS session_id,
                      gs.time_start, gs.time_end,
                      gn.date, gn.location,
                      g.title, g.genre
               FROM registrations r
               JOIN game_sessions gs ON gs.id = r.session_id
               JOIN game_nights  gn ON gn.id = gs.game_night_id
               JOIN games        g  ON g.id  = gs.game_id
               WHERE r.user_telegram_id = ?
                 AND gn.date >= date('now')
               ORDER BY gn.date, gs.time_start""",
            (user_id,),
        )
        return [dict(r) for r in await cur.fetchall()]


async def cancel_registration(reg_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT session_id FROM registrations WHERE id = ? AND user_telegram_id = ?",
            (reg_id, user_id),
        )
        row = await cur.fetchone()
        if not row:
            return False
        session_id = row["session_id"]
        await db.execute("DELETE FROM registrations WHERE id = ?", (reg_id,))
        await db.execute(
            "UPDATE game_sessions SET slots_taken = slots_taken - 1 WHERE id = ?",
            (session_id,),
        )
        await db.commit()
        return True


# ---------- Управление игротеками (для хостов) ----------

async def list_host_nights(host_telegram_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT gn.id, gn.date, gn.location,
                      COUNT(gs.id) AS sessions_count,
                      COALESCE(SUM(gs.slots_taken), 0) AS total_taken
               FROM game_nights gn
               LEFT JOIN game_sessions gs ON gs.game_night_id = gn.id
               WHERE gn.host_telegram_id = ?
                 AND gn.date >= date('now')
               GROUP BY gn.id
               ORDER BY gn.date""",
            (host_telegram_id,),
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_night(night_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT gn.id, gn.date, gn.location, gn.host_telegram_id,
                      COUNT(gs.id) AS sessions_count,
                      COALESCE(SUM(gs.slots_taken), 0) AS total_taken
               FROM game_nights gn
               LEFT JOIN game_sessions gs ON gs.game_night_id = gn.id
               WHERE gn.id = ?
               GROUP BY gn.id""",
            (night_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_night_sessions_for_edit(night_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT gs.id, gs.time_start, gs.time_end,
                      gs.max_slots, gs.slots_taken,
                      g.title AS game_title
               FROM game_sessions gs
               JOIN games g ON g.id = gs.game_id
               WHERE gs.game_night_id = ?
               ORDER BY gs.time_start""",
            (night_id,),
        )
        return [dict(r) for r in await cur.fetchall()]


async def update_night_date(night_id: int, new_date: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE game_nights SET date = ? WHERE id = ?",
            (new_date, night_id),
        )
        await db.commit()


async def update_night_location(night_id: int, new_location: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE game_nights SET location = ? WHERE id = ?",
            (new_location, night_id),
        )
        await db.commit()


async def delete_night(night_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("DELETE FROM game_nights WHERE id = ?", (night_id,))
        await db.commit()


async def delete_session(session_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("DELETE FROM game_sessions WHERE id = ?", (session_id,))
        await db.commit()


async def count_registrations_for_night(night_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """SELECT COUNT(*) FROM registrations r
               JOIN game_sessions gs ON gs.id = r.session_id
               WHERE gs.game_night_id = ?""",
            (night_id,),
        )
        (count,) = await cur.fetchone()
        return count


async def get_session_with_host(session_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT gs.id, gs.max_slots, gs.slots_taken,
                      gs.time_start, gs.time_end,
                      g.title,
                      gn.id AS night_id, gn.date, gn.location,
                      gn.host_telegram_id
               FROM game_sessions gs
               JOIN games g       ON g.id  = gs.game_id
               JOIN game_nights gn ON gn.id = gs.game_night_id
               WHERE gs.id = ?""",
            (session_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_all_night_registrations(night_id: int) -> list[dict]:
    """Все записи на игротеку — плоский список, отсортированный по времени."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT gs.id AS session_id,
                      gs.time_start, gs.time_end,
                      gs.max_slots, gs.slots_taken,
                      g.title AS game_title, g.genre,
                      u.telegram_id, u.username,
                      u.first_name, u.last_name,
                      r.registered_at
               FROM game_sessions gs
               JOIN games g ON g.id = gs.game_id
               LEFT JOIN registrations r ON r.session_id = gs.id
               LEFT JOIN users u ON u.telegram_id = r.user_telegram_id
               WHERE gs.game_night_id = ?
               ORDER BY gs.time_start, r.registered_at""",
            (night_id,),
        )
        return [dict(r) for r in await cur.fetchall()]