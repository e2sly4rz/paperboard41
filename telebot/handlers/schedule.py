from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import db
from database.queries import (
    can_register_for_night,
    find_session_conflict_for_user,
    get_active_poll_for_night,
    get_night,
    get_night_sessions_with_conflicts,
    get_session,
    get_session_with_registrations,
    get_user,
    list_cars,
    list_upcoming_nights,
    mark_availability_unavailable,
    register_for_session,
    upsert_availability_response,
)
from keyboards.menus import (
    main_menu,
    nights_list,
    poll_time_grid,
    poll_time_grid_after,
    session_card,
)
from notifications import notify_game_author_registration
from states.states import PollTime
from utils import fmt_date, is_host_or_admin, safe_edit

router = Router()


def _time_range(s: dict) -> str:
    if s.get("time_end"):
        return f"{s['time_start']}–{s['time_end']}"
    return s["time_start"]


@router.callback_query(F.data == "schedule")
async def show_schedule(call: CallbackQuery) -> None:
    nights = await list_upcoming_nights()
    is_host_user = await is_host_or_admin(call.from_user.id)
    user = await get_user(call.from_user.id)
    is_provodnik = bool(user and user["subscriber_level"] in ("provodnik", "host"))
    if not nights:
        await safe_edit(
            call.message,
            "Пока нет запланированных игротек.",
            reply_markup=main_menu(is_host_user, call.from_user.id,
                                   is_provodnik=is_provodnik),
        )
        await call.answer()
        return
    await safe_edit(
        call.message,
        "Ближайшие игротеки:",
        reply_markup=nights_list(nights),
    )
    await call.answer()


@router.callback_query(F.data.startswith("night:"))
async def show_night(call: CallbackQuery) -> None:
    night_id = int(call.data.split(":")[1])
    sessions = await get_night_sessions_with_conflicts(night_id, call.from_user.id)

    night = await get_night(night_id)
    if not night:
        await call.answer("Игротека не найдена", show_alert=True)
        return

    poll = await get_active_poll_for_night(night_id)
    can, reason = await can_register_for_night(night_id, call.from_user.id)

    free_label = "🆓 Бесплатная игротека" if night["is_free"] else "💰 Платная игротека"

    lines = [
        f"🎲 <b>Игротека {fmt_date(night['date'])}</b>",
        free_label,
        f"📍 {night['location']}",
        f"Игр: {night['sessions_count']} • Записей: {night['total_taken']}",
    ]
    if not can:
        lines.append(f"\nℹ️ {reason}")
    if poll:
        lines.append("\n📊 Хост собирает удобное время для игр.")

    cars = await list_cars(night_id)
    car_titles = {c["id"]: c["title"] for c in cars}

    if not sessions:
        lines.append("\n<i>В этой игротеке пока нет игр.</i>")
    else:
        lines.append("")
        current_car = "___init___"
        for i, s in enumerate(sessions, 1):
            car_id = s.get("car_id")
            if car_id != current_car:
                if current_car != "___init___" and car_id is not None:
                    lines.append("")
                if car_id is not None:
                    lines.append(f"🚃 <b>{car_titles.get(car_id, 'Вагон')}</b>")
                current_car = car_id

            time_range = _time_range(s)
            title = s["title"]
            taken = s["max_slots"] - s["free_slots"]

            markers = ""
            if s.get("is_subscriber_only"):
                markers += " ⭐"
            if s["free_slots"] <= 0:
                markers += " ⛔"

            # хост игры: автор сессии, иначе — хост ночи
            author_id = s.get("created_by_user_id")
            author_name = s.get("author_first_name")
            author_username = s.get("author_username")

            if author_id == call.from_user.id:
                host_label = "Вы"
            elif author_name:
                host_label = author_name
                if author_username:
                    host_label += f" (@{author_username})"
            else:
                # fallback — хост ночи (если автор не указан)
                if s.get("host_telegram_id") == call.from_user.id:
                    host_label = "Вы"
                else:
                    host_label = ""  # нет данных — не показываем

            host_part = f" · 🎩 {host_label}" if host_label else ""

            padding = " " if i < 10 else ""
            lines.append(f"{padding}{i}. <b>{time_range}</b>{host_part}")
            lines.append(f" {title} · {taken}/{s['max_slots']}{markers}")

    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3890] + "\n\n<i>…список обрезан</i>"

    builder = InlineKeyboardBuilder()
    if sessions:
        for i, s in enumerate(sessions, 1):
            builder.button(text=str(i), callback_data=f"session:{s['id']}")
        builder.adjust(5)

    if poll:
        builder.row(InlineKeyboardButton(
            text="⏰ Указать удобное время",
            callback_data=f"poll_answer:{night_id}",
        ))
        builder.row(InlineKeyboardButton(
            text="❌ Не смогу прийти",
            callback_data=f"poll_unavailable_notify:{night_id}",
        ))

    builder.row(InlineKeyboardButton(
        text="⬅️ К расписанию",
        callback_data="schedule",
    ))

    await safe_edit(
        call.message,
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("session:"))
async def show_session(call: CallbackQuery) -> None:
    session_id = int(call.data.split(":")[1])
    s = await get_session_with_registrations(session_id)
    if not s:
        await call.answer("Сессия не найдена", show_alert=True)
        return

    user = await get_user(call.from_user.id)
    level = user["subscriber_level"] if user else "passenger"

    async with db.conn.execute(
        "SELECT 1 FROM registrations WHERE session_id = ? AND user_telegram_id = ?",
        (session_id, call.from_user.id),
    ) as cur:
        already_registered = await cur.fetchone() is not None

    if already_registered:
        await call.answer(
            "✅ Вы уже записаны на эту игру.\n"
            "Отменить запись можно в разделе «🎲 Мои записи».",
            show_alert=True,
        )
        return

    conflict = await find_session_conflict_for_user(session_id, call.from_user.id)
    if conflict:
        c_start = conflict["time_start"]
        c_end = conflict["time_end"] or "?"
        await call.answer(
            f"⚠️ Пересекается с вашей записью:\n"
            f"{conflict['game_title']} ({c_start}–{c_end}).\n"
            f"Сначала отмените ту запись в «🎲 Мои записи».",
            show_alert=True,
        )
        return

    can, reason = await can_register_for_night(s["night_id"], call.from_user.id)
    if not can:
        await call.answer(reason, show_alert=True)
        return

    can_register = (
        s["free_slots"] > 0
        and (not s["is_subscriber_only"] or level in ("provodnik", "host"))
    )

    taken = s["max_slots"] - s["free_slots"]
    free_label = "🆓 Бесплатная игротека" if s.get("is_free") else "💰 Платная игротека"

    # хост
    author_id = s.get("created_by_user_id")
    author_name = s.get("author_first_name")
    author_username = s.get("author_username")
    if author_id == call.from_user.id:
        host_label = "Вы"
    elif author_name:
        host_label = author_name
        if author_username:
            host_label += f" (@{author_username})"
    elif s.get("host_telegram_id") == call.from_user.id:
        host_label = "Вы"
    else:
        host_label = None

    # записанные
    regs = s.get("registrations", [])
    if not regs:
        players_label = "Пока никто не записан"
    else:
        names = []
        for r in regs:
            name = r.get("first_name") or "Без имени"
            username = f" (@{r['username']})" if r.get("username") else ""
            names.append(f"{name}{username}")
        players_label = ", ".join(names)

    text = (
        f"🎲 <b>{s['title']}</b>\n"
        f"Дата: {fmt_date(s['date'])}\n"
        f"Время: {s['time_start']}–{s['time_end'] or '?'}\n"
        f"Место: {s['location']}\n"
        f"{free_label}\n"
    )
    if host_label:
        text += f"🎩 Хост: {host_label}\n"
    text += (
        f"👥 Записаны ({taken}/{s['max_slots']}): {players_label}\n"
    )
    if s["is_subscriber_only"]:
        text += "\n⭐ Только для подписчиков «Проводник»."

    await safe_edit(
        call.message,
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
    await safe_edit(
        call.message,
        text,
        parse_mode="HTML",
        reply_markup=session_card(session_id, s["night_id"], False),
    )

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

    await safe_edit(
        call.message,
        "⏰ <b>Когда вам удобно играть?</b>\n\n"
        "Выберите час, с которого вы готовы начать:",
        parse_mode="HTML",
        reply_markup=poll_time_grid("pollfrom"),
    )
    await call.answer()


@router.callback_query(PollTime.picking_from, F.data == "poll_unavailable")
async def poll_unavailable(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    poll_id = data.get("poll_id")
    if not poll_id:
        await call.answer("Сессия устарела. Начните заново.", show_alert=True)
        await state.clear()
        return

    await mark_availability_unavailable(poll_id, call.from_user.id)
    await state.clear()

    is_host_user = await is_host_or_admin(call.from_user.id)
    user = await get_user(call.from_user.id)
    is_provodnik = bool(user and user["subscriber_level"] in ("provodnik", "host"))

    await safe_edit(
        call.message,
        "✅ <b>Отмечено: вы не сможете прийти.</b>\n\n"
        "Если передумаете — откройте опрос в карточке игротеки "
        "и укажите удобное время.",
        parse_mode="HTML",
        reply_markup=main_menu(is_host_user, call.from_user.id,
                               is_provodnik=is_provodnik),
    )
    await call.answer()


@router.callback_query(F.data.startswith("poll_unavailable_notify:"))
async def poll_unavailable_from_notify(call: CallbackQuery) -> None:
    night_id = int(call.data.split(":")[1])
    poll = await get_active_poll_for_night(night_id)
    if not poll:
        await call.answer("Опрос уже закрыт", show_alert=True)
        return

    await mark_availability_unavailable(poll["id"], call.from_user.id)

    is_host_user = await is_host_or_admin(call.from_user.id)
    user = await get_user(call.from_user.id)
    is_provodnik = bool(user and user["subscriber_level"] in ("provodnik", "host"))

    await safe_edit(
        call.message,
        "✅ <b>Отмечено: вы не сможете прийти.</b>\n\n"
        "Если передумаете — откройте опрос в карточке игротеки "
        "и укажите удобное время.",
        parse_mode="HTML",
        reply_markup=main_menu(is_host_user, call.from_user.id,
                               is_provodnik=is_provodnik),
    )
    await call.answer()


@router.callback_query(PollTime.picking_from, F.data.startswith("pollfrom:"))
async def poll_pick_from(call: CallbackQuery, state: FSMContext) -> None:
    time_from = call.data.split(":", 1)[1]
    await state.update_data(time_from=time_from)
    await state.set_state(PollTime.picking_to)

    await safe_edit(
        call.message,
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

    is_host_user = await is_host_or_admin(call.from_user.id)
    user = await get_user(call.from_user.id)
    is_provodnik = bool(user and user["subscriber_level"] in ("provodnik", "host"))

    await safe_edit(
        call.message,
        f"✅ Ваше время: <b>{time_from}–{time_to}</b>\n\n"
        "Спасибо! Хост увидит ваш ответ.",
        parse_mode="HTML",
        reply_markup=main_menu(is_host_user, call.from_user.id,
                               is_provodnik=is_provodnik),
    )
    await call.answer()