from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.queries import (
    list_upcoming_nights,
    get_night_sessions,
    get_session,
    register_for_session,
    get_user,
    get_session_with_host,
    get_session_registrations,
)
from keyboards.menus import (
    nights_list,
    sessions_list,
    session_card,
    main_menu,
    participants_back,
)

router = Router()


def _fmt_date(iso_date: str) -> str:
    """ГГГГ-ММ-ДД → ДД.ММ.ГГГГ."""
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return iso_date or "—"


async def _is_host(user_id: int) -> bool:
    """Читает уровень пользователя из БД в момент вызова."""
    user = await get_user(user_id)
    return bool(user and user["subscriber_level"] == "host")


# ---------- Список игротек ----------

@router.callback_query(F.data == "schedule")
async def show_schedule(call: CallbackQuery) -> None:
    nights = await list_upcoming_nights()
    is_host = await _is_host(call.from_user.id)
    if not nights:
        await call.message.edit_text(
            "Пока нет запланированных игротек.",
            reply_markup=main_menu(is_host),
        )
        await call.answer()
        return
    await call.message.edit_text(
        "Ближайшие игротеки:",
        reply_markup=nights_list(nights),
    )
    await call.answer()


# ---------- Список игр в игротеке ----------

@router.callback_query(F.data.startswith("night:"))
async def show_night(call: CallbackQuery) -> None:
    night_id = int(call.data.split(":")[1])
    sessions = await get_night_sessions(night_id)
    if not sessions:
        await call.message.edit_text(
            "В этой игротеке пока нет игр.",
            reply_markup=nights_list(await list_upcoming_nights()),
        )
        await call.answer()
        return
    text_lines = ["Игры игротеки:\n"]
    for s in sessions:
        taken = s["max_slots"] - s["free_slots"]
        text_lines.append(
            f"• {s['time_start']}–{s['time_end'] or '?'} "
            f"{s['title']} ({taken}/{s['max_slots']} занято)"
        )
    await call.message.edit_text(
        "\n".join(text_lines),
        reply_markup=sessions_list(night_id, sessions),
    )
    await call.answer()


# ---------- Карточка сессии ----------

@router.callback_query(F.data.startswith("session:"))
async def show_session(call: CallbackQuery) -> None:
    session_id = int(call.data.split(":")[1])
    s = await get_session(session_id)
    if not s:
        await call.answer("Сессия не найдена", show_alert=True)
        return

    # Узнаём, хост ли текущий пользователь для этой игротеки
    meta = await get_session_with_host(session_id)
    is_own_host = bool(
        meta and meta["host_telegram_id"] == call.from_user.id
    )

    user = await get_user(call.from_user.id)
    level = user["subscriber_level"] if user else "guest"
    can_register = (
        s["free_slots"] > 0
        and (not s["is_subscriber_only"] or level in ("provodnik", "host"))
    )

    taken = s["max_slots"] - s["free_slots"]
    text = (
        f"🎲 <b>{s['title']}</b>\n"
        f"Дата: {_fmt_date(s['date'])}\n"
        f"Время: {s['time_start']}–{s['time_end'] or '?'}\n"
        f"Место: {s['location']}\n"
        f"Занято мест: {taken} из {s['max_slots']}\n"
    )
    if s["is_subscriber_only"]:
        text += "\n🔒 Только для подписчиков «Проводник»."

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=session_card(session_id, can_register, is_own_host),
    )
    await call.answer()


# ---------- Список участников (только для хоста) ----------

@router.callback_query(F.data.startswith("participants:"))
async def show_participants(call: CallbackQuery) -> None:
    session_id = int(call.data.split(":")[1])
    meta = await get_session_with_host(session_id)
    if not meta:
        await call.answer("Сессия не найдена", show_alert=True)
        return

    # Смотреть участников может только хост этой игротеки
    if meta["host_telegram_id"] != call.from_user.id:
        await call.answer("Только хост видит участников", show_alert=True)
        return

    regs = await get_session_registrations(session_id)

    header = (
        f"👥 <b>Участники</b>\n"
        f"🎲 {meta['title']}\n"
        f"📅 {_fmt_date(meta['date'])} • {meta['time_start']}–"
        f"{meta['time_end'] or '?'}\n"
        f"📍 {meta['location']}\n"
        f"Занято мест: {meta['slots_taken']} из {meta['max_slots']}\n"
    )

    if not regs:
        body = "\nПока никто не записался."
    else:
        lines = []
        for i, r in enumerate(regs, 1):
            name_parts = [r["first_name"] or "", r["last_name"] or ""]
            name = " ".join(p for p in name_parts if p).strip() or "Без имени"
            username = f" (@{r['username']})" if r["username"] else ""
            lines.append(f"{i}. {name}{username}")
        body = "\n\n" + "\n".join(lines)

    await call.message.edit_text(
        header + body,
        parse_mode="HTML",
        reply_markup=participants_back(session_id),
    )
    await call.answer()


# ---------- Запись на игру ----------

@router.callback_query(F.data.startswith("reg:"))
async def do_register(call: CallbackQuery) -> None:
    session_id = int(call.data.split(":")[1])
    ok, msg = await register_for_session(session_id, call.from_user.id)
    await call.answer(msg, show_alert=True)

    if not ok:
        return

    s = await get_session(session_id)
    meta = await get_session_with_host(session_id)
    is_own_host = bool(meta and meta["host_telegram_id"] == call.from_user.id)

    if s:
        taken = s["max_slots"] - s["free_slots"]
        text = (
            f"🎲 <b>{s['title']}</b>\n"
            f"Дата: {_fmt_date(s['date'])}\n"
            f"Время: {s['time_start']}–{s['time_end'] or '?'}\n"
            f"Место: {s['location']}\n"
            f"Занято мест: {taken} из {s['max_slots']}\n"
            f"\n✅ Вы записаны!"
        )
        await call.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=session_card(session_id, False, is_own_host),
        )