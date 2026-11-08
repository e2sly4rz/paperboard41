import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from database.db import db
from database.queries import get_night, get_game
from utils import fmt_date


async def _safe_send(bot: Bot, user_id: int, text: str) -> bool:
    try:
        await bot.send_message(user_id, text)
        return True
    except TelegramForbiddenError:
        logging.warning(
            "Уведомление не доставлено: user=%s заблокировал бота", user_id
        )
        return False
    except TelegramRetryAfter as e:
        logging.warning("Flood control, retry_after=%s", e.retry_after)
        return False
    except Exception as e:
        logging.exception("Ошибка отправки уведомления user=%s: %s", user_id, e)
        return False


async def _send_with_delay(
    bot: Bot,
    user_ids: list[int],
    build_text,
    delay_seconds: float = 1.0,
) -> int:
    """Отправляет сообщения по одному с задержкой.

    build_text(user_id) -> str — функция, возвращающая текст для пользователя.
    Возвращает количество успешно отправленных.
    """
    sent = 0
    for user_id in user_ids:
        text = build_text(user_id)
        if text is None:
            continue
        ok = await _safe_send(bot, user_id, text)
        if ok:
            sent += 1
        await asyncio.sleep(delay_seconds)
    return sent


async def notify_session_deleted(
    bot: Bot,
    session_id: int,
    initiator_id: int,
    *,
    night_id: int,
    game_title: str,
    time_start: str,
    time_end: str | None,
) -> None:
    night = await get_night(night_id)
    if not night:
        return

    host_id = night["host_telegram_id"]
    if host_id and host_id != initiator_id:
        text = (
            f"🔔 <b>Из вашей игротеки удалена игра</b>\n\n"
            f"🎲 {game_title}\n"
            f"📅 {fmt_date(night['date'])} • {time_start}–{time_end or '?'}\n"
            f"📍 {night['location']}"
        )
        await _safe_send(bot, host_id, text)


async def notify_registrants_deleted(
    bot: Bot,
    registrants: list[dict],
    initiator_id: int,
    *,
    game_title: str,
    date_str: str,
    location: str,
    time_start: str,
    time_end: str | None,
) -> None:
    for r in registrants:
        user_id = r["telegram_id"]
        if user_id == initiator_id:
            continue
        text = (
            f"❌ <b>Игра отменена</b>\n\n"
            f"🎲 {game_title}\n"
            f"📅 {fmt_date(date_str)} • {time_start}–{time_end or '?'}\n"
            f"📍 {location}\n\n"
            f"Запись удалена. Приносим извинения за неудобства."
        )
        await _safe_send(bot, user_id, text)


async def notify_game_owner_deleted(
    bot: Bot,
    game_id: int,
    initiator_id: int,
    *,
    game_title: str,
    date_str: str,
    location: str,
    time_start: str,
    time_end: str | None,
) -> None:
    game = await get_game(game_id)
    if not game:
        return
    owner_id = game.get("owner_user_id")
    if not owner_id or owner_id == initiator_id:
        return

    text = (
        f"🔔 <b>Ваша игра удалена из игротеки</b>\n\n"
        f"🎲 {game_title}\n"
        f"📅 {fmt_date(date_str)} • {time_start}–{time_end or '?'}\n"
        f"📍 {location}"
    )
    await _safe_send(bot, owner_id, text)


async def notify_poll_created(
    bot: Bot,
    participants: list[dict],
    initiator_id: int,
    *,
    night_date: str,
    night_location: str,
) -> None:
    for p in participants:
        user_id = p["telegram_id"]
        if user_id == initiator_id:
            continue
        text = (
            f"📊 <b>Хост собирает удобное время</b>\n\n"
            f"📅 {fmt_date(night_date)} • {night_location}\n\n"
            f"Откройте «📅 Расписание» → эту игротеку "
            f"и нажмите «⏰ Указать удобное время»."
        )
        await _safe_send(bot, user_id, text)


async def notify_game_author_registration(
    bot: Bot,
    session_id: int,
    initiator_id: int,
    *,
    game_title: str,
    date_str: str,
    location: str,
    time_start: str,
    time_end: str | None,
    slots_taken: int,
    max_slots: int,
    player_name: str,
) -> None:
    async with db.conn.execute(
        "SELECT created_by_user_id FROM game_sessions WHERE id = ?",
        (session_id,),
    ) as cur:
        row = await cur.fetchone()

    if not row:
        return

    author_id = row["created_by_user_id"]
    if not author_id or author_id == initiator_id:
        return

    text = (
        f"<b>Новая запись на вашу игру</b>\n\n"
        f"🎲 {game_title}\n"
        f"📅 {fmt_date(date_str)} • {time_start}–{time_end or '?'}\n"
        f"📍 {location}\n\n"
        f"Записался: {player_name}\n"
        f"Занято: {slots_taken} из {max_slots}"
    )
    await _safe_send(bot, author_id, text)


async def notify_game_author_cancellation(
    bot: Bot,
    session_id: int,
    initiator_id: int,
    *,
    game_title: str,
    date_str: str,
    location: str,
    time_start: str,
    time_end: str | None,
    slots_taken: int,
    max_slots: int,
    player_name: str,
) -> None:
    async with db.conn.execute(
        "SELECT created_by_user_id FROM game_sessions WHERE id = ?",
        (session_id,),
    ) as cur:
        row = await cur.fetchone()

    if not row:
        return

    author_id = row["created_by_user_id"]
    if not author_id or author_id == initiator_id:
        return

    text = (
        f"<b>Игрок отменил запись</b>\n\n"
        f"🎲 {game_title}\n"
        f"📅 {fmt_date(date_str)} • {time_start}–{time_end or '?'}\n"
        f"📍 {location}\n\n"
        f"Отменился: {player_name}\n"
        f"Занято: {slots_taken} из {max_slots}"
    )
    await _safe_send(bot, author_id, text)


async def notify_registration_opened(
    bot: Bot,
    users: list[dict],
    initiator_id: int,
    *,
    night_date: str,
    night_location: str,
    night_id: int,
    target_level: str,
) -> int:
    """Уведомляет игроков указанного уровня об открытии записи.

    Отправка с задержкой 1 секунда между сообщениями.
    """
    if target_level == "provodnik":
        header = "🔓 <b>Запись открыта</b>"
        body = "Откройте «📅 Расписание» → эту игротеку и запишитесь на игры."
    else:
        header = "🔓 <b>Запись открыта для пассажиров</b>"
        body = (
            "До начала игры осталось меньше 8 часов — запись открыта для всех.\n"
            "Откройте «📅 Расписание» → эту игротеку и запишитесь на игры."
        )

    user_ids = [
        u["telegram_id"] for u in users
        if u["telegram_id"] != initiator_id
    ]

    def build_text(uid: int) -> str:
        return (
            f"{header}\n\n"
            f"📅 {fmt_date(night_date)} • {night_location}\n\n"
            f"{body}"
        )

    return await _send_with_delay(bot, user_ids, build_text, delay_seconds=1.0)