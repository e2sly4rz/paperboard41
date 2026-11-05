from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.queries import (
    list_upcoming_nights,
    get_night,
    get_night_sessions,
    get_session,
    register_for_session,
    get_user,
)
from keyboards.menus import (
    nights_list,
    sessions_list,
    session_card,
    main_menu,
)
from utils import is_host_or_admin, fmt_date

router = Router()


@router.callback_query(F.data == "schedule")
async def show_schedule(call: CallbackQuery) -> None:
    nights = await list_upcoming_nights()
    is_host_user = await is_host_or_admin(call.from_user.id)
    if not nights:
        await call.message.edit_text(
            "Пока нет запланированных игротек.",
            reply_markup=main_menu(is_host_user, call.from_user.id),
        )
        await call.answer()
        return
    await call.message.edit_text(
        "Ближайшие игротеки:",
        reply_markup=nights_list(nights),
    )
    await call.answer()


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

    night = await get_night(night_id)
    header = (
        f"🎲 <b>Игротека {fmt_date(night['date'])}</b>\n"
        f"📍 {night['location']}\n"
        f"Игр: {night['sessions_count']} • Записей: {night['total_taken']}"
    )

    await call.message.edit_text(
        header,
        parse_mode="HTML",
        reply_markup=sessions_list(night_id, sessions),
    )
    await call.answer()


@router.callback_query(F.data.startswith("session:"))
async def show_session(call: CallbackQuery) -> None:
    session_id = int(call.data.split(":")[1])
    s = await get_session(session_id)
    if not s:
        await call.answer("Сессия не найдена", show_alert=True)
        return

    user = await get_user(call.from_user.id)
    level = user["subscriber_level"] if user else "passenger"
    can_register = (
        s["free_slots"] > 0
        and (not s["is_subscriber_only"] or level in ("provodnik", "host"))
    )

    taken = s["max_slots"] - s["free_slots"]
    text = (
        f"🎲 <b>{s['title']}</b>\n"
        f"Дата: {fmt_date(s['date'])}\n"
        f"Время: {s['time_start']}–{s['time_end'] or '?'}\n"
        f"Место: {s['location']}\n"
        f"Занято мест: {taken} из {s['max_slots']}\n"
    )
    if s["is_subscriber_only"]:
        text += "\n🔒 Только для подписчиков «Проводник»."

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=session_card(session_id, s["night_id"], can_register),
    )
    await call.answer()


@router.callback_query(F.data.startswith("reg:"))
async def do_register(call: CallbackQuery) -> None:
    session_id = int(call.data.split(":")[1])
    ok, msg = await register_for_session(session_id, call.from_user.id)
    await call.answer(msg, show_alert=True)

    if not ok:
        return

    s = await get_session(session_id)
    if s:
        taken = s["max_slots"] - s["free_slots"]
        text = (
            f"🎲 <b>{s['title']}</b>\n"
            f"Дата: {fmt_date(s['date'])}\n"
            f"Время: {s['time_start']}–{s['time_end'] or '?'}\n"
            f"Место: {s['location']}\n"
            f"Занято мест: {taken} из {s['max_slots']}\n"
            f"\n✅ Вы записаны!"
        )
        await call.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=session_card(session_id, s["night_id"], False),
        )