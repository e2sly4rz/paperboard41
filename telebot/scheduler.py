import logging
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from config import CLUB_TIMEZONE
from database.queries import (
    get_user_day_registrations,
    was_day_notification_sent,
    log_day_notification,
)


_TZ = ZoneInfo(CLUB_TIMEZONE)

scheduler = AsyncIOScheduler()


def _fmt_date(iso_date: str) -> str:
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return iso_date or "—"


def _session_datetime(iso_date: str, time_str: str) -> datetime | None:
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d")
        t = datetime.strptime(time_str, "%H:%M")
        naive = d.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
        return naive.replace(tzinfo=_TZ)
    except (ValueError, TypeError):
        return None


def _build_group_message(kind: str, date: str, location: str,
                         games: list[dict]) -> str:
    """Одно сообщение на день с полным списком игр."""
    when = "завтра" if kind == "day_before" else "через час"
    icon = "📅" if kind == "day_before" else "⏰"

    lines = [
        f"{icon} <b>Напоминание: игра {when}</b>",
        f"📅 {_fmt_date(date)} • {location}",
        "",
        "<b>Вы записаны на:</b>",
    ]
    for g in games:
        time_range = f"{g['time_start']}–{g['time_end'] or '?'}"
        lines.append(f"🎲 {g['game_title']} — {time_range}")

    lines.append("")
    lines.append("Хорошей игры! 🎲")
    return "\n".join(lines)


async def _notify_user(bot: Bot, user_id: int, text: str) -> bool:
    try:
        await bot.send_message(user_id, text)
        return True
    except TelegramForbiddenError:
        logging.warning(
            "Напоминание не доставлено: user=%s заблокировал бота", user_id
        )
        return False
    except TelegramRetryAfter as e:
        logging.warning("Flood control, retry_after=%s", e.retry_after)
        return False
    except Exception as e:
        logging.exception("Ошибка отправки напоминания user=%s: %s", user_id, e)
        return False


async def check_and_send_reminders(bot: Bot) -> None:
    """Группирует записи по (user, date) и отправляет одно напоминание
    на день, беря время самой ранней игры.

    Окна:
      day_before  — 23–25 часов до первой игры дня
      hour_before — 50–70 минут до первой игры дня
    """
    now = datetime.now(_TZ)

    today = now.date().isoformat()
    tomorrow = (now.date() + timedelta(days=1)).isoformat()

    rows = await get_user_day_registrations(today, tomorrow)

    # Группируем: (user_id, date) → список игр
    groups: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["telegram_id"], row["date"])].append(row)

    for (user_id, date), games in groups.items():
        # Сортируем по времени начала — первая запись в списке самая ранняя
        games.sort(key=lambda g: g["time_start"])
        earliest = games[0]

        first_dt = _session_datetime(date, earliest["time_start"])
        if first_dt is None:
            continue

        delta = first_dt - now

        kind = None
        if timedelta(hours=23) <= delta <= timedelta(hours=25):
            kind = "day_before"
        elif timedelta(minutes=50) <= delta <= timedelta(minutes=70):
            kind = "hour_before"

        if kind is None:
            continue

        if await was_day_notification_sent(user_id, date, kind):
            continue

        text = _build_group_message(kind, date, earliest["location"], games)
        ok = await _notify_user(bot, user_id, text)

        if ok:
            await log_day_notification(user_id, date, kind)
            logging.info(
                "Напоминание %s отправлено: user=%s date=%s games=%d",
                kind, user_id, date, len(games),
            )


def start_scheduler(bot: Bot) -> None:
    scheduler.add_job(
        check_and_send_reminders,
        trigger="interval",
        minutes=10,
        args=[bot],
        id="check_reminders",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logging.info(
        "Планировщик напоминаний запущен "
        "(проверка каждые 10 минут, часовой пояс: %s)",
        CLUB_TIMEZONE,
    )


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logging.info("Планировщик напоминаний остановлен")