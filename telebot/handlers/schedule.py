from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.queries import (
    list_upcoming_nights,
    get_night_sessions,
    get_session,
    register_for_session,
)
from keyboards.menus import (
    nights_list,
    sessions_list,
    session_card,
    main_menu,
)

router = Router()


@router.callback_query(F.data == "schedule")
async def show_schedule(call: CallbackQuery, user: dict | None = None) -> None:
    nights = await list_upcoming_nights()
    if not nights:
        await call.message.edit_text(
            "Пока нет запланированных игротек.",
            reply_markup=main_menu(bool(user and user["subscriber_level"] == "host")),
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
    text_lines = ["Игры игротеки:\n"]
    for s in sessions:
        text_lines.append(
            f"• {s['time_start']}–{s['time_end'] or '?'} "
            f"{s['title']} ({s['free_slots']}/{s['max_slots']} мест)"
        )
    await call.message.edit_text(
        "\n".join(text_lines),
        reply_markup=sessions_list(night_id, sessions),
    )
    await call.answer()


@router.callback_query(F.data.startswith("session:"))
async def show_session(call: CallbackQuery, user: dict | None = None) -> None:
    session_id = int(call.data.split(":")[1])
    s = await get_session(session_id)
    if not s:
        await call.answer("Сессия не найдена", show_alert=True)
        return

    level = user["subscriber_level"] if user else "guest"
    can_register = (
        s["free_slots"] > 0
        and (not s["is_subscriber_only"] or level in ("provodnik", "host"))
    )

    text = (
        f"🎲 <b>{s['title']}</b>\n"
        f"Дата: {s['date']}\n"
        f"Время: {s['time_start']}–{s['time_end'] or '?'}\n"
        f"Место: {s['location']}\n"
        f"Свободных мест: {s['free_slots']} из {s['max_slots']}\n"
    )
    if s["is_subscriber_only"]:
        text += "\n🔒 Только для подписчиков «Проводник». "

    await call.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=session_card(session_id, can_register),
    )
    await call.answer()


@router.callback_query(F.data.startswith("reg:"))
async def do_register(call: CallbackQuery) -> None:
    session_id = int(call.data.split(":")[1])
    ok, msg = await register_for_session(session_id, call.from_user.id)
    await call.answer(msg, show_alert=True)
    if ok:
        # Обновляем карточку с новыми данными
        s = await get_session(session_id)
        if s:
            text = (
                f"🎲 <b>{s['title']}</b>\n"
                f"Дата: {s['date']}\n"
                f"Время: {s['time_start']}–{s['time_end'] or '?'}\n"
                f"Место: {s['location']}\n"
                f"Свободных мест: {s['free_slots']} из {s['max_slots']}\n"
                f"\n✅ Вы записаны!"
            )
            await call.message.edit_text(
                text, parse_mode="HTML",
                reply_markup=session_card(session_id, False),
            )