from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.queries import (
    list_upcoming_nights,
    get_night,
    get_night_sessions_with_conflicts,
    get_session,
    register_for_session,
    get_user,
    get_active_poll_for_night,
    upsert_availability_response,
    find_session_conflict_for_user,
)
from keyboards.menus import (
    nights_list,
    sessions_list,
    session_card,
    main_menu,
    poll_time_grid,
    poll_time_grid_after,
)
from states.states import PollTime
from utils import is_host_or_admin, fmt_date
from notifications import notify_game_author_registration

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
    sessions = await get_night_sessions_with_conflicts(night_id, call.from_user.id)

    if not sessions:
        await call.message.edit_text(
            "В этой игротеке пока нет игр.",
            reply_markup=nights_list(await list_upcoming_nights()),
        )
        await call.answer()
        return

    night = await get_night(night_id)
    poll = await get_active_poll_for_night(night_id)

    header = (
        f"🎲 <b>Игротека {fmt_date(night['date'])}</b>\n"
        f"📍 {night['location']}\n"
        f"Игр: {night['sessions_count']} • Записей: {night['total_taken']}"
    )
    if poll:
        header += "\n\n📊 Хост собирает удобное время для игр."

    kb = sessions_list(night_id, sessions)
    if poll:
        builder = InlineKeyboardBuilder()
        builder.button(
            text="⏰ Указать удобное время",
            callback_data=f"poll_answer:{night_id}",
        )
        for row in kb.inline_keyboard:
            for btn in row:
                builder.button(text=btn.text, callback_data=btn.callback_data)
        builder.adjust(1)
        kb = builder.as_markup()

    await call.message.edit_text(
        header,
        parse_mode="HTML",
        reply_markup=kb,
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

    conflict = await find_session_conflict_for_user(session_id, call.from_user.id)

    can_register = (
        s["free_slots"] > 0
        and (not s["is_subscriber_only"] or level in ("provodnik", "host"))
        and conflict is None
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

    if conflict:
        c_start = conflict["time_start"]
        c_end = conflict["time_end"] or "?"
        text += (
            f"\n\n⚠️ <b>Пересекается с вашей записью:</b>\n"
            f"🎲 {conflict['game_title']}\n"
            f"⏰ {c_start}–{c_end}\n"
            f"📍 {conflict['location']}\n\n"
            f"Чтобы записаться сюда, сначала отмените ту запись "
            f"в разделе «🎲 Мои записи»."
        )

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
    if not s:
        return

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

    # Уведомление автору игры о новой записи
    user = await get_user(call.from_user.id)
    player_name = "Без имени"
    if user:
        name_parts = [user["first_name"] or "", user["last_name"] or ""]
        player_name = " ".join(p for p in name_parts if p).strip() or "Без имени"
        if user.get("username"):
            player_name += f" (@{user['username']})"

    await notify_game_author_registration(
        call.bot,
        session_id,
        call.from_user.id,
        game_title=s["title"],
        date_str=s["date"],
        location=s["location"],
        time_start=s["time_start"],
        time_end=s["time_end"],
        slots_taken=taken,
        max_slots=s["max_slots"],
        player_name=player_name,
    )


# ---------- Опрос о времени ----------

@router.callback_query(F.data.startswith("poll_answer:"))
async def poll_answer_start(call: CallbackQuery, state: FSMContext) -> None:
    night_id = int(call.data.split(":")[1])
    poll = await get_active_poll_for_night(night_id)
    if not poll:
        await call.answer("Опрос уже закрыт", show_alert=True)
        return

    await state.clear()
    await state.set_state(PollTime.picking_from)
    await state.update_data(poll_id=poll["id"], night_id=night_id)

    await call.message.edit_text(
        "⏰ <b>Когда вам удобно играть?</b>\n\n"
        "Выберите час, с которого вы готовы начать:",
        parse_mode="HTML",
        reply_markup=poll_time_grid("pollfrom"),
    )
    await call.answer()


@router.callback_query(PollTime.picking_from, F.data.startswith("pollfrom:"))
async def poll_pick_from(call: CallbackQuery, state: FSMContext) -> None:
    time_from = call.data.split(":", 1)[1]
    await state.update_data(time_from=time_from)
    await state.set_state(PollTime.picking_to)

    await call.message.edit_text(
        f"⏰ Начало: <b>{time_from}</b>\n\n"
        f"Выберите час, до которого вы готовы играть:",
        parse_mode="HTML",
        reply_markup=poll_time_grid_after("pollto", after=time_from),
    )
    await call.answer()


@router.callback_query(PollTime.picking_to, F.data.startswith("pollto:"))
async def poll_pick_to(call: CallbackQuery, state: FSMContext) -> None:
    time_to = call.data.split(":", 1)[1]
    data = await state.get_data()
    time_from = data["time_from"]

    if time_to <= time_from:
        await call.answer(
            "Время окончания должно быть позже начала. Выберите ещё раз.",
            show_alert=True,
        )
        return

    await upsert_availability_response(
        data["poll_id"],
        call.from_user.id,
        time_from,
        time_to,
    )
    await state.clear()

    await call.message.edit_text(
        f"✅ Ваше время: <b>{time_from}–{time_to}</b>\n\n"
        "Спасибо! Хост увидит ваш ответ.",
        parse_mode="HTML",
        reply_markup=main_menu(False, call.from_user.id),
    )
    await call.answer()