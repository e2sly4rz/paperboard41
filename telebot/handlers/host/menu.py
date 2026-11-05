from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.queries import (
    get_night,
    list_all_upcoming_nights,
    get_night_sessions_for_edit,
    get_session,
    get_session_registrations_full,
    get_active_poll_for_night,
)
from keyboards.menus import (
    host_menu_with_nights,
    host_menu_empty,
    host_night_card_with_poll,
    host_session_participants,
)
from utils import is_admin, is_host_or_admin, fmt_date

from ._helpers import can_manage_night

router = Router()


@router.callback_query(F.data == "host_menu")
async def open_host_menu(call: CallbackQuery) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return

    nights = await list_all_upcoming_nights()

    if not nights:
        await call.message.edit_text(
            "🎩 <b>Меню организатора</b>\n\n"
            "Предстоящих игротек пока нет. Создайте первую!",
            parse_mode="HTML",
            reply_markup=host_menu_empty(),
        )
        await call.answer()
        return

    own_ids = {
        n["id"] for n in nights
        if n["host_telegram_id"] == call.from_user.id
    }

    await call.message.edit_text(
        "🎩 <b>Меню организатора</b>\n\n"
        "Выберите игротеку или создайте новую:",
        parse_mode="HTML",
        reply_markup=host_menu_with_nights(nights, own_ids),
    )
    await call.answer()


@router.callback_query(F.data.startswith("hn:"))
async def night_card(call: CallbackQuery) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return

    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not night:
        await call.answer("Игротека не найдена", show_alert=True)
        return

    can_manage = await can_manage_night(call.from_user.id, night)
    is_own = night["host_telegram_id"] == call.from_user.id
    sessions = await get_night_sessions_for_edit(night_id)
    poll = await get_active_poll_for_night(night_id) if can_manage else None

    lines = [
        f"🎲 <b>Игротека {fmt_date(night['date'])}</b>",
        f"📍 {night['location']}",
        f"Игр: {night['sessions_count']} • Записей: {night['total_taken']}",
    ]
    if is_admin(call.from_user.id) and not is_own:
        lines.append("<i>(админ: игротека другого хоста)</i>")
    elif not can_manage:
        lines.append("<i>(игротека другого хоста)</i>")

    if poll and can_manage:
        lines.append("\n📊 Опрос о времени активен.")

    if not sessions:
        lines.append("\n<i>В этой игротеке пока нет игр.</i>")
    else:
        lines.append("\nНажмите на игру, чтобы увидеть участников:")

    await call.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=host_night_card_with_poll(
            night_id,
            is_owner=can_manage,
            has_poll=bool(poll) if can_manage else False,
        ),
    )
    await call.answer()


@router.callback_query(F.data.startswith("hn_part:"))
async def session_participants(call: CallbackQuery) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return

    parts = call.data.split(":")
    night_id = int(parts[1])
    session_id = int(parts[2])

    night = await get_night(night_id)
    if not night:
        await call.answer("Игротека не найдена", show_alert=True)
        return

    session = await get_session(session_id)
    if not session or session["night_id"] != night_id:
        await call.answer("Игра не найдена", show_alert=True)
        return

    can_manage = await can_manage_night(call.from_user.id, night)
    is_author = session.get("created_by_user_id") == call.from_user.id
    if not (can_manage or is_author):
        await call.answer("Нет доступа", show_alert=True)
        return

    registrants = await get_session_registrations_full(session_id)

    taken = session["slots_taken"]
    total = session["max_slots"]
    time_range = f"{session['time_start']}–{session['time_end'] or '?'}"

    lines = [
        f"🎲 <b>{session['title']}</b>",
        f"⏰ {time_range} • занято {taken} из {total}",
        f"📅 {fmt_date(night['date'])} • {night['location']}",
    ]

    if not registrants:
        lines.append("\n<i>Пока никто не записался.</i>")
    else:
        lines.append("\n<b>Участники:</b>")
        for i, r in enumerate(registrants, 1):
            name_parts = [r["first_name"] or "", r.get("last_name") or ""]
            name = " ".join(x for x in name_parts if x).strip() or "Без имени"
            username = f" (@{r['username']})" if r.get("username") else ""
            lines.append(f"{i}. {name}{username}")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3990] + "\n\n<i>…список обрезан</i>"

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=host_session_participants(night_id, session_id),
    )
    await call.answer()