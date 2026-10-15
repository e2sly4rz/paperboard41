import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from config import CLUB_TIMEZONE
from database.queries import (
    list_sessions_with_registrations_for_notify,
    was_notification_sent,
    log_notification,
)


_TZ = ZoneInfo(CLUB_TIMEZONE)

scheduler = AsyncIOScheduler()


def _fmt_date(iso_date: str) -> str:
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return iso_date or "—"


def _session_datetime(iso_date: str, time_str: str) -> datetime | None:
    """Собирает timezone-aware datetime игры в часовом поясе клуба."""
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d")
        t = datetime.strptime(time_str, "%H:%M")
        naive = d.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
        return naive.replace(tzinfo=_TZ)
    except (ValueError, TypeError):
        return None


def _build_message(kind: str, row: dict) -> str:
    when = "завтра" if kind == "day_before" else "через час"
    icon = "📅" if kind == "day_before" else "⏰"
    return (
        f"{icon} <b>Напоминание: игра {when}</b>\n\n"
        f"🎲 {row['game_title']}\n"
        f"📅 {_fmt_date(row['date'])} в {row['time_start']}\n"
        f"📍 {row['location']}"
    )


async def _notify_user(bot: Bot, user_id: int, text: str) -> bool:
    """Отправляет сообщение. Возвращает True при успехе."""
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
    """Проходит по ближайшим сессиям и рассылает напоминания.

    Запускается планировщиком каждые 10 минут.
    Все сравнения времени — в часовом поясе клуба (CLUB_TIMEZONE).
    """
    now = datetime.now(_TZ)
    rows = await list_sessions_with_registrations_for_notify()

    for row in rows:
        session_dt = _session_datetime(row["date"], row["time_start"])
        if session_dt is None:
            continue

        delta = session_dt - now

        # Определяем, какое напоминание сейчас уместно.
        # Окна шире интервала планировщика (10 минут),
        # чтобы не пропустить момент при задержке запуска.
        kind = None
        if timedelta(hours=23) <= delta <= timedelta(hours=25):
            kind = "day_before"
        elif timedelta(minutes=50) <= delta <= timedelta(minutes=70):
            kind = "hour_before"

        if kind is None:
            continue

        user_id = row["telegram_id"]

        if await was_notification_sent(row["session_id"], user_id, kind):
            continue

        text = _build_message(kind, row)
        ok = await _notify_user(bot, user_id, text)

        if ok:
            await log_notification(row["session_id"], user_id, kind)
            logging.info(
                "Напоминание %s отправлено: session=%s user=%s",
                kind, row["session_id"], user_id,
            )


def start_scheduler(bot: Bot) -> None:
    """Регистрирует задачи и запускает планировщик."""
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