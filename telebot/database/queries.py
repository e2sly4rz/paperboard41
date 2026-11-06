from database.db import db


# ---------- Пользователи ----------

async def ensure_user(telegram_id: int, username: str | None,
                      first_name: str | None, last_name: str | None) -> None:
    await db.conn.execute(
        """INSERT INTO users (telegram_id, username, first_name, last_name, is_approved)
           VALUES (?, ?, ?, ?, 0)
           ON CONFLICT(telegram_id) DO UPDATE SET
               username   = excluded.username,
               first_name = excluded.first_name,
               last_name  = excluded.last_name""",
        (telegram_id, username, first_name, last_name),
    )
    await db.conn.commit()


async def get_user(telegram_id: int) -> dict | None:
    async with db.conn.execute(
        "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def set_user_level(telegram_id: int, level: str) -> None:
    if level not in ("host", "provodnik", "passenger"):
        raise ValueError(f"Недопустимый уровень: {level}")
    await db.conn.execute(
        "UPDATE users SET subscriber_level = ? WHERE telegram_id = ?",
        (level, telegram_id),
    )
    await db.conn.commit()


async def approve_user(telegram_id: int) -> bool:
    cur = await db.conn.execute(
        "UPDATE users SET is_approved = 1 WHERE telegram_id = ?",
        (telegram_id,),
    )
    await db.conn.commit()
    return cur.rowcount > 0


async def revoke_user(telegram_id: int) -> bool:
    cur = await db.conn.execute(
        "UPDATE users SET is_approved = 0 WHERE telegram_id = ?",
        (telegram_id,),
    )
    await db.conn.commit()
    return cur.rowcount > 0


async def list_pending_users() -> list[dict]:
    async with db.conn.execute(
        """SELECT telegram_id, username, first_name, last_name, created_at
           FROM users
           WHERE is_approved = 0
           ORDER BY created_at"""
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


# ---------- Каталог игр ----------

async def list_games() -> list[dict]:
    async with db.conn.execute(
        """SELECT g.*,
                  u.username    AS owner_username,
                  u.first_name  AS owner_first_name,
                  u.last_name   AS owner_last_name
           FROM games g
           LEFT JOIN users u ON u.telegram_id = g.owner_user_id
           ORDER BY g.title"""
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def get_game(game_id: int) -> dict | None:
    async with db.conn.execute(
        """SELECT g.*,
                  u.username    AS owner_username,
                  u.first_name  AS owner_first_name,
                  u.last_name   AS owner_last_name
           FROM games g
           LEFT JOIN users u ON u.telegram_id = g.owner_user_id
           WHERE g.id = ?""",
        (game_id,),
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def search_games(query: str, limit: int = 10) -> list[dict]:
    q = query.strip().lower()
    if not q:
        return []

    async with db.conn.execute(
        """SELECT g.*,
                  u.username    AS owner_username,
                  u.first_name  AS owner_first_name,
                  u.last_name   AS owner_last_name
           FROM games g
           LEFT JOIN users u ON u.telegram_id = g.owner_user_id
           ORDER BY g.title"""
    ) as cur:
        games = [dict(r) for r in await cur.fetchall()]

    words = [w for w in q.split() if w]
    scored: list[tuple[int, int, dict]] = []
    for g in games:
        title = (g["title"] or "").lower()
        if not all(w in title for w in words):
            continue
        if title == q:
            rank = 0
        elif title.startswith(q):
            rank = 1
        elif any(w in title.split() for w in words):
            rank = 2
        else:
            rank = 3
        scored.append((rank, len(title), g))

    scored.sort(key=lambda x: (x[0], x[1], x[2]["title"]))
    return [g for _, _, g in scored[:limit]]


# ---------- Игротеки и сессии ----------

async def create_game_night(date: str, location: str,
                            host_telegram_id: int) -> int:
    cur = await db.conn.execute(
        """INSERT INTO game_nights (date, location, host_telegram_id)
           VALUES (?, ?, ?)""",
        (date, location, host_telegram_id),
    )
    await db.conn.commit()
    return cur.lastrowid


async def add_session(
    game_night_id: int,
    game_id: int,
    time_start: str,
    time_end: str | None,
    max_slots: int,
    created_by_user_id: int | None = None,
    registration_opens_at: str | None = None,
    registration_min_level: str = "passenger",
    registration_approved: int = 1,
) -> int:
    cur = await db.conn.execute(
        """INSERT INTO game_sessions
           (game_night_id, game_id, time_start, time_end, max_slots,
            created_by_user_id, registration_opens_at,
            registration_min_level, registration_approved)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (game_night_id, game_id, time_start, time_end, max_slots,
         created_by_user_id, registration_opens_at,
         registration_min_level, registration_approved),
    )
    await db.conn.commit()
    return cur.lastrowid


async def set_session_registration_approved(session_id: int,
                                            approved: int) -> None:
    await db.conn.execute(
        "UPDATE game_sessions SET registration_approved = ? WHERE id = ?",
        (approved, session_id),
    )
    await db.conn.commit()


async def list_upcoming_nights() -> list[dict]:
    async with db.conn.execute(
        """SELECT gn.id, gn.date, gn.location,
                  COUNT(gs.id) AS sessions_count
           FROM game_nights gn
           LEFT JOIN game_sessions gs ON gs.game_night_id = gn.id
           WHERE gn.date >= date('now')
           GROUP BY gn.id
           ORDER BY gn.date"""
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def list_all_upcoming_nights() -> list[dict]:
    async with db.conn.execute(
        """SELECT gn.id, gn.date, gn.location,
                  gn.host_telegram_id,
                  COUNT(gs.id) AS sessions_count,
                  COALESCE(SUM(gs.slots_taken), 0) AS total_taken
           FROM game_nights gn
           LEFT JOIN game_sessions gs ON gs.game_night_id = gn.id
           WHERE gn.date >= date('now')
           GROUP BY gn.id
           ORDER BY gn.date"""
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def get_night_sessions(night_id: int) -> list[dict]:
    async with db.conn.execute(
        """SELECT gs.id, gs.time_start, gs.time_end, gs.max_slots,
                  gs.slots_taken,
                  (gs.max_slots - gs.slots_taken) AS free_slots,
                  gs.registration_opens_at,
                  gs.registration_min_level,
                  gs.registration_approved,
                  g.title, g.genre, g.min_players, g.max_players,
                  g.duration_min, g.duration_max, g.is_subscriber_only
           FROM game_sessions gs
           JOIN games g ON g.id = gs.game_id
           WHERE gs.game_night_id = ?
           ORDER BY gs.time_start""",
        (night_id,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def get_night_sessions_with_conflicts(
    night_id: int, user_id: int
) -> list[dict]:
    """Сессии игротеки + флаг conflict (пересекается с записью пользователя)."""
    async with db.conn.execute(
        """SELECT gs.id, gs.time_start, gs.time_end,
                  gs.max_slots, gs.slots_taken,
                  (gs.max_slots - gs.slots_taken) AS free_slots,
                  gs.registration_opens_at,
                  gs.registration_min_level,
                  gs.registration_approved,
                  g.title, g.genre, g.min_players, g.max_players,
                  g.duration_min, g.duration_max, g.is_subscriber_only,
                  gn.date,
                  CASE WHEN EXISTS (
                      SELECT 1
                      FROM registrations r2
                      JOIN game_sessions gs2 ON gs2.id = r2.session_id
                      JOIN game_nights  gn2  ON gn2.id = gs2.game_night_id
                      WHERE r2.user_telegram_id = ?
                        AND gn2.date = gn.date
                        AND gs2.id != gs.id
                        AND gs2.time_start < COALESCE(gs.time_end, gs.time_start)
                        AND gs.time_start < COALESCE(gs2.time_end, gs2.time_start)
                  ) THEN 1 ELSE 0 END AS conflict
           FROM game_sessions gs
           JOIN games g       ON g.id  = gs.game_id
           JOIN game_nights gn ON gn.id = gs.game_night_id
           WHERE gs.game_night_id = ?
           ORDER BY gs.time_start""",
        (user_id, night_id),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def get_session(session_id: int) -> dict | None:
    async with db.conn.execute(
        """SELECT gs.*, g.title, g.genre, g.owner,
                  g.min_players, g.max_players,
                  g.is_subscriber_only,
                  gn.id AS night_id,
                  gn.date, gn.location,
                  (gs.max_slots - gs.slots_taken) AS free_slots
           FROM game_sessions gs
           JOIN games g       ON g.id  = gs.game_id
           JOIN game_nights gn ON gn.id = gs.game_night_id
           WHERE gs.id = ?""",
        (session_id,),
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_session_author(session_id: int) -> int | None:
    async with db.conn.execute(
        "SELECT created_by_user_id FROM game_sessions WHERE id = ?",
        (session_id,),
    ) as cur:
        row = await cur.fetchone()
        return row[0] if row else None


async def get_session_registrations_full(session_id: int) -> list[dict]:
    """Список записавшихся на сессию с telegram_id — для уведомлений."""
    async with db.conn.execute(
        """SELECT u.telegram_id, u.first_name, u.last_name, u.username
           FROM registrations r
           JOIN users u ON u.telegram_id = r.user_telegram_id
           WHERE r.session_id = ?""",
        (session_id,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def find_host_conflict(
    host_id: int,
    date: str,
    time_start: str,
    time_end: str | None,
    exclude_session_id: int | None = None,
) -> dict | None:
    """Ищет игру, которую ведёт этот хост в тот же день и пересекается по времени."""
    end = time_end or time_start

    query = """
        SELECT gs.id, gs.time_start, gs.time_end,
               g.title AS game_title,
               gn.date, gn.location
        FROM game_sessions gs
        JOIN games g       ON g.id  = gs.game_id
        JOIN game_nights gn ON gn.id = gs.game_night_id
        WHERE gs.created_by_user_id = ?
          AND gn.date = ?
          AND gs.time_start < ?
          AND ? < COALESCE(gs.time_end, gs.time_start)
    """
    params: list = [host_id, date, end, time_start]

    if exclude_session_id is not None:
        query += " AND gs.id != ?"
        params.append(exclude_session_id)

    query += " LIMIT 1"

    async with db.conn.execute(query, params) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def find_session_conflict_for_user(
    session_id: int, user_id: int
) -> dict | None:
    """Ищет запись пользователя, которая пересекается с указанной сессией."""
    async with db.conn.execute(
        """SELECT gs2.time_start, gs2.time_end,
                  g2.title AS game_title,
                  gn2.location
           FROM game_sessions gs1
           JOIN game_sessions gs2 ON gs2.game_night_id = gs1.game_night_id
           JOIN games g2        ON g2.id = gs2.game_id
           JOIN game_nights gn2 ON gn2.id = gs2.game_night_id
           JOIN registrations r ON r.session_id = gs2.id
           WHERE gs1.id = ?
             AND r.user_telegram_id = ?
             AND gs2.id != gs1.id
             AND gs2.time_start < COALESCE(gs1.time_end, gs1.time_start)
             AND gs1.time_start < COALESCE(gs2.time_end, gs2.time_start)
           LIMIT 1""",
        (session_id, user_id),
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


# ---------- Записи на игры ----------

async def register_for_session(session_id: int, user_id: int) -> tuple[bool, str]:
    try:
        await db.conn.execute("BEGIN")

        async with db.conn.execute(
            """SELECT gs.max_slots, gs.slots_taken,
                      gs.time_start, gs.time_end,
                      gs.registration_opens_at,
                      gs.registration_min_level,
                      gs.registration_approved,
                      gn.date,
                      g.is_subscriber_only,
                      u.subscriber_level
               FROM game_sessions gs
               JOIN games g       ON g.id  = gs.game_id
               JOIN game_nights gn ON gn.id = gs.game_night_id
               JOIN users u       ON u.telegram_id = ?
               WHERE gs.id = ?""",
            (user_id, session_id),
        ) as cur:
            row = await cur.fetchone()

        if row is None:
            await db.conn.rollback()
            return False, "Сессия не найдена или пользователь не зарегистрирован."

        if row["is_subscriber_only"] and row["subscriber_level"] not in ("provodnik", "host"):
            await db.conn.rollback()
            return False, "Эта игра доступна только подписчикам уровня «Проводник»."

        if row["registration_min_level"] == "provodnik" and row["subscriber_level"] == "passenger":
            await db.conn.rollback()
            return False, "Запись на эту игру доступна только с уровня «Проводник»."

        if row["slots_taken"] >= row["max_slots"]:
            await db.conn.rollback()
            return False, "Свободных мест больше нет."

        async with db.conn.execute(
            "SELECT 1 FROM registrations WHERE session_id = ? AND user_telegram_id = ?",
            (session_id, user_id),
        ) as cur:
            exists = await cur.fetchone()

        if exists:
            await db.conn.rollback()
            return False, "Вы уже записаны на эту игру."

        # Проверка пересечения с другими записями
        async with db.conn.execute(
            """SELECT gs.time_start, gs.time_end,
                      g.title AS game_title,
                      gn.location
               FROM registrations r
               JOIN game_sessions gs ON gs.id = r.session_id
               JOIN games g       ON g.id  = gs.game_id
               JOIN game_nights gn ON gn.id = gs.game_night_id
               WHERE r.user_telegram_id = ?
                 AND gn.date = ?
                 AND gs.id != ?
                 AND gs.time_start < ?
                 AND ? < COALESCE(gs.time_end, gs.time_start)
               LIMIT 1""",
            (user_id, row["date"], session_id,
             row["time_end"] or row["time_start"], row["time_start"]),
        ) as cur:
            conflict = await cur.fetchone()

        if conflict:
            await db.conn.rollback()
            c_start = conflict["time_start"]
            c_end = conflict["time_end"] or "?"
            return (
                False,
                f"⏰ Конфликт по времени: вы уже записаны на "
                f"«{conflict['game_title']}» "
                f"({c_start}–{c_end}, {conflict['location']}). "
                f"Сначала отмените ту запись."
            )

        await db.conn.execute(
            "INSERT INTO registrations (session_id, user_telegram_id) VALUES (?, ?)",
            (session_id, user_id),
        )
        await db.conn.execute(
            "UPDATE game_sessions SET slots_taken = slots_taken + 1 WHERE id = ?",
            (session_id,),
        )
        await db.conn.commit()
        return True, "Вы успешно записаны!"
    except Exception as e:
        await db.conn.rollback()
        return False, f"Ошибка записи: {e}"


async def list_user_registrations(user_id: int) -> list[dict]:
    async with db.conn.execute(
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
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def cancel_registration(reg_id: int, user_id: int) -> dict | None:
    """Отменяет запись.

    Возвращает данные отменённой сессии (для уведомлений) или None.
    """
    async with db.conn.execute(
        """SELECT r.session_id,
                  gs.time_start, gs.time_end,
                  gs.max_slots,
                  g.title AS game_title,
                  gn.date, gn.location
           FROM registrations r
           JOIN game_sessions gs ON gs.id = r.session_id
           JOIN games g        ON g.id  = gs.game_id
           JOIN game_nights gn ON gn.id = gs.game_night_id
           WHERE r.id = ? AND r.user_telegram_id = ?""",
        (reg_id, user_id),
    ) as cur:
        row = await cur.fetchone()

    if not row:
        return None

    session_id = row["session_id"]

    await db.conn.execute("DELETE FROM registrations WHERE id = ?", (reg_id,))
    await db.conn.execute(
        "UPDATE game_sessions SET slots_taken = slots_taken - 1 WHERE id = ?",
        (session_id,),
    )
    await db.conn.commit()

    async with db.conn.execute(
        "SELECT slots_taken FROM game_sessions WHERE id = ?",
        (session_id,),
    ) as cur:
        row2 = await cur.fetchone()

    return {
        "session_id": session_id,
        "game_title": row["game_title"],
        "date": row["date"],
        "location": row["location"],
        "time_start": row["time_start"],
        "time_end": row["time_end"],
        "slots_taken": row2["slots_taken"] if row2 else 0,
        "max_slots": row["max_slots"],
    }


# ---------- Управление игротеками ----------

async def get_night(night_id: int) -> dict | None:
    async with db.conn.execute(
        """SELECT gn.id, gn.date, gn.location, gn.host_telegram_id,
                  COUNT(gs.id) AS sessions_count,
                  COALESCE(SUM(gs.slots_taken), 0) AS total_taken
           FROM game_nights gn
           LEFT JOIN game_sessions gs ON gs.game_night_id = gn.id
           WHERE gn.id = ?
           GROUP BY gn.id""",
        (night_id,),
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_night_sessions_for_edit(night_id: int) -> list[dict]:
    async with db.conn.execute(
        """SELECT gs.id, gs.time_start, gs.time_end,
                  gs.max_slots, gs.slots_taken,
                  gs.created_by_user_id,
                  g.title AS game_title
           FROM game_sessions gs
           JOIN games g ON g.id = gs.game_id
           WHERE gs.game_night_id = ?
           ORDER BY gs.time_start""",
        (night_id,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def update_night_date(night_id: int, new_date: str) -> None:
    await db.conn.execute(
        "UPDATE game_nights SET date = ? WHERE id = ?",
        (new_date, night_id),
    )
    await db.conn.commit()


async def update_night_location(night_id: int, new_location: str) -> None:
    await db.conn.execute(
        "UPDATE game_nights SET location = ? WHERE id = ?",
        (new_location, night_id),
    )
    await db.conn.commit()


async def delete_night(night_id: int) -> None:
    await db.conn.execute("DELETE FROM game_nights WHERE id = ?", (night_id,))
    await db.conn.commit()


async def delete_session(session_id: int) -> None:
    await db.conn.execute("DELETE FROM game_sessions WHERE id = ?", (session_id,))
    await db.conn.commit()


async def count_registrations_for_night(night_id: int) -> int:
    async with db.conn.execute(
        """SELECT COUNT(*) FROM registrations r
           JOIN game_sessions gs ON gs.id = r.session_id
           WHERE gs.game_night_id = ?""",
        (night_id,),
    ) as cur:
        row = await cur.fetchone()
        return row[0] if row else 0


async def get_all_night_registrations(night_id: int) -> list[dict]:
    async with db.conn.execute(
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
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


# ---------- Напоминания ----------

async def get_user_day_registrations(
    date_from: str, date_to: str
) -> list[dict]:
    async with db.conn.execute(
        """SELECT u.telegram_id,
                  u.first_name,
                  u.username,
                  gn.date,
                  gn.location,
                  gs.id           AS session_id,
                  gs.time_start,
                  gs.time_end,
                  g.title          AS game_title
           FROM registrations r
           JOIN game_sessions gs ON gs.id = r.session_id
           JOIN game_nights  gn ON gn.id = gs.game_night_id
           JOIN games        g  ON g.id  = gs.game_id
           JOIN users        u  ON u.telegram_id = r.user_telegram_id
           WHERE gn.date >= ?
             AND gn.date <= ?
           ORDER BY u.telegram_id, gn.date, gs.time_start""",
        (date_from, date_to),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def was_day_notification_sent(user_id: int, date: str,
                                    kind: str) -> bool:
    async with db.conn.execute(
        """SELECT 1 FROM notifications_log
           WHERE user_id = ? AND date = ? AND kind = ?""",
        (user_id, date, kind),
    ) as cur:
        return await cur.fetchone() is not None


async def log_day_notification(user_id: int, date: str, kind: str) -> None:
    try:
        await db.conn.execute(
            """INSERT INTO notifications_log (user_id, date, kind)
               VALUES (?, ?, ?)""",
            (user_id, date, kind),
        )
        await db.conn.commit()
    except Exception:
        pass


# ---------- Опросы доступности ----------

async def create_availability_poll(game_night_id: int,
                                   created_by_user_id: int,
                                   closes_at: str | None = None) -> int:
    cur = await db.conn.execute(
        """INSERT INTO availability_polls
           (game_night_id, created_by_user_id, closes_at)
           VALUES (?, ?, ?)""",
        (game_night_id, created_by_user_id, closes_at),
    )
    await db.conn.commit()
    return cur.lastrowid


async def get_active_poll_for_night(night_id: int) -> dict | None:
    async with db.conn.execute(
        """SELECT * FROM availability_polls
           WHERE game_night_id = ? AND status = 'open'
           ORDER BY id DESC LIMIT 1""",
        (night_id,),
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def upsert_availability_response(poll_id: int, user_id: int,
                                       time_from: str, time_to: str) -> None:
    await db.conn.execute(
        """INSERT INTO availability_responses
           (poll_id, user_id, time_from, time_to)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(poll_id, user_id) DO UPDATE SET
               time_from = excluded.time_from,
               time_to   = excluded.time_to,
               created_at = CURRENT_TIMESTAMP""",
        (poll_id, user_id, time_from, time_to),
    )
    await db.conn.commit()


async def list_availability_responses(poll_id: int) -> list[dict]:
    async with db.conn.execute(
        """SELECT r.user_id, r.time_from, r.time_to, r.created_at,
                  u.username, u.first_name, u.last_name
           FROM availability_responses r
           JOIN users u ON u.telegram_id = r.user_id
           WHERE r.poll_id = ?
           ORDER BY r.time_from""",
        (poll_id,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def close_availability_poll(poll_id: int) -> None:
    await db.conn.execute(
        "UPDATE availability_polls SET status = 'closed' WHERE id = ?",
        (poll_id,),
    )
    await db.conn.commit()


async def get_night_participants(night_id: int) -> list[dict]:
    """Уникальные пользователи, записанные хотя бы на одну игру игротеки."""
    async with db.conn.execute(
        """SELECT DISTINCT u.telegram_id, u.first_name, u.username
           FROM registrations r
           JOIN game_sessions gs ON gs.id = r.session_id
           JOIN users u ON u.telegram_id = r.user_telegram_id
           WHERE gs.game_night_id = ?""",
        (night_id,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def list_all_users_grouped() -> dict:
    """Список пользователей, сгруппированный по уровню."""
    async with db.conn.execute(
        """SELECT telegram_id, username, first_name, last_name,
                  subscriber_level, is_approved
           FROM users
           ORDER BY subscriber_level, first_name, username"""
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    groups = {
        "host": [],
        "provodnik": [],
        "passenger": [],
        "pending": [],
    }
    for r in rows:
        if not r["is_approved"]:
            groups["pending"].append(r)
        else:
            level = r["subscriber_level"]
            if level in groups:
                groups[level].append(r)
    return groups