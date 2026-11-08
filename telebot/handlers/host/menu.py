from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.queries import (
    get_night,
    list_all_upcoming_nights,
    get_session,
    get_all_night_registrations,
    get_active_poll_for_night,
)
from keyboards.menus import (
    host_menu_with_nights,
    host_menu_empty,
    host_night_card_with_poll,
)
from utils import is_admin, is_host_or_admin, fmt_date, safe_edit

from ._helpers import can_manage_night

router = Router()


@router.callback_query(F.data == "host_menu")
async def open_host_menu(call: CallbackQuery) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return

    nights = await list_all_upcoming_nights()

    if not nights:
        await safe_edit(
            call.message,
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

    await safe_edit(
        call.message,
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
    active_poll = await get_active_poll_for_night(night_id)

    rows = await get_all_night_registrations(night_id)
    sessions: dict[int, dict] = {}
    for r in rows:
        sid = r["session_id"]
        if sid not in sessions:
            sessions[sid] = {
                "time_start": r["time_start"],
                "time_end": r["time_end"],
                "game_title": r["game_title"],
                "max_slots": r["max_slots"],
                "slots_taken": r["slots_taken"],
                "players": [],
            }
        if r["telegram_id"] is not None:
            sessions[sid]["players"].append({
                "first_name": r["first_name"],
                "last_name": r["last_name"],
                "username": r["username"],
            })

    reg_status = "🔓 открыта" if night["registration_open"] else "🔒 закрыта"

    lines = [
        "🎲 <b>Игротека</b>",
        f"📅 {fmt_date(night['date'])}",
        f"📍 {night['location']}",
        f"Игр: {night['sessions_count']} • Записей: {night['total_taken']}",
        f"Запись: {reg_status}",
    ]
    if is_admin(call.from_user.id) and not is_own:
        lines.append("<i>(админ: игротека другого хоста)</i>")
    elif not can_manage:
        lines.append("<i>(игротека другого хоста)</i>")

    if active_poll:
        lines.append("\n📊 Опрос о времени активен.")

    if not sessions:
        lines.append("\n<i>В этой игротеке пока нет игр.</i>")
    else:
        lines.append("\n👥 <b>Участники:</b>")
        for s in sessions.values():
            time_range = f"{s['time_start']}–{s['time_end'] or '?'}"
            lines.append(
                f"\n🎲 <b>{s['game_title']}</b>\n"
                f"⏰ {time_range} • занято {s['slots_taken']} из {s['max_slots']}"
            )
            if not s["players"]:
                lines.append("— никто не записан")
            else:
                for i, p in enumerate(s["players"], 1):
                    name_parts = [p["first_name"] or "", p["last_name"] or ""]
                    name = " ".join(x for x in name_parts if x).strip() or "Без имени"
                    username = f" (@{p['username']})" if p["username"] else ""
                    lines.append(f"{i}. {name}{username}")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3990] + "\n\n<i>…список обрезан</i>"

    await safe_edit(
        call.message,
        text,
        parse_mode="HTML",
        reply_markup=host_night_card_with_poll(
            night_id,
            is_owner=can_manage,
            has_active_poll=bool(active_poll),
            has_any_poll=bool(active_poll),
            registration_open=bool(night["registration_open"]),
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

    await call.answer("Список участников — в карточке игротеки")