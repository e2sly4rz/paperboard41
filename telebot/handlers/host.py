from datetime import datetime, timedelta

import aiosqlite
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback

from config import DB_PATH
from database.queries import (
    get_game,
    get_user,
    create_game_night,
    add_session,
    list_all_upcoming_nights,
    get_night,
    get_night_sessions_for_edit,
    update_night_date,
    update_night_location,
    delete_night,
    delete_session,
    count_registrations_for_night,
    get_all_night_registrations,
    search_games,
)
from keyboards.menus import (
    main_menu,
    host_menu,
    host_nights_list,
    host_night_card,
    host_sessions_list,
    confirm_delete_night,
    confirm_delete_session,
    cancel_edit,
    games_search_results,
    games_search_create,
    search_prompt_keyboard,
)
from states.states import CreateNight, EditNight, AddSessionToNight
from utils import is_admin

router = Router()


async def _is_host(user_id: int) -> bool:
    user = await get_user(user_id)
    return bool(user and user["subscriber_level"] == "host")


async def _is_host_or_admin(user_id: int) -> bool:
    return is_admin(user_id) or await _is_host(user_id)


async def _can_manage_night(user_id: int, night: dict | None) -> bool:
    """Право управлять игротекой: владелец-хост или админ."""
    if night is None:
        return False
    if is_admin(user_id):
        return True
    return night["host_telegram_id"] == user_id


def _fmt_date(iso_date: str) -> str:
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return iso_date or "—"


# ============ МЕНЮ ОРГАНИЗАТОРА ============

@router.callback_query(F.data == "host_menu")
async def open_host_menu(call: CallbackQuery) -> None:
    if not await _is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return
    await call.message.edit_text("Меню организатора:", reply_markup=host_menu())
    await call.answer()


# ============ СОЗДАНИЕ ИГРОТЕКИ ============

@router.callback_query(F.data == "host_create")
async def start_create(call: CallbackQuery, state: FSMContext) -> None:
    if not await _is_host_or_admin(call.from_user.id):
        await call.answer("Только организаторы могут создавать игротеки", show_alert=True)
        return

    await state.clear()
    await state.set_state(CreateNight.date)

    calendar = SimpleCalendar(locale="ru_RU.UTF-8", show_alerts=True)
    calendar.set_dates_range(
        datetime.now(),
        datetime.now() + timedelta(days=365),
    )
    await call.message.edit_text(
        "Создание игротеки.\n\nВыберите дату:",
        reply_markup=await calendar.start_calendar(),
    )
    await call.answer()


@router.callback_query(SimpleCalendarCallback.filter(), CreateNight.date)
async def enter_date(
    call: CallbackQuery,
    callback_data: SimpleCalendarCallback,
    state: FSMContext,
) -> None:
    calendar = SimpleCalendar(locale="ru_RU.UTF-8", show_alerts=True)
    calendar.set_dates_range(
        datetime.now(),
        datetime.now() + timedelta(days=365),
    )
    selected, date_obj = await calendar.process_selection(call, callback_data)

    if not selected:
        return

    await state.update_data(date=date_obj.strftime("%Y-%m-%d"))
    await state.update_data(date_display=date_obj.strftime("%d.%m.%Y"))
    await state.set_state(CreateNight.location)

    await call.message.edit_text(
        f"📅 Дата: {date_obj.strftime('%d.%m.%Y')}\n\n"
        f"Введите место проведения:"
    )
    await call.answer()


@router.message(CreateNight.location)
async def enter_location(message: Message, state: FSMContext) -> None:
    await state.update_data(location=message.text.strip())
    await state.set_state(CreateNight.searching_game)
    await message.answer(
        "🔍 <b>Поиск игры</b>\n\n"
        "Введите название или его часть (например, <code>catan</code>):",
        parse_mode="HTML",
        reply_markup=search_prompt_keyboard("host_cancel"),
    )


@router.callback_query(F.data == "host_create_search_again")
async def create_search_again(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CreateNight.searching_game)
    await call.message.edit_text(
        "🔍 Введите название или его часть:",
        reply_markup=search_prompt_keyboard("host_cancel"),
    )
    await call.answer()


@router.message(CreateNight.searching_game)
async def create_search(message: Message, state: FSMContext) -> None:
    query = message.text.strip()
    if len(query) < 2:
        await message.answer("Введите хотя бы 2 символа:")
        return

    games = await search_games(query, limit=10)

    if not games:
        await state.set_state(CreateNight.searching_game)
        await message.answer(
            f"🔍 По запросу «{query}» ничего не найдено.\n\n"
            f"Попробуйте другое название:",
            reply_markup=search_prompt_keyboard("host_cancel"),
        )
        return

    await state.set_state(CreateNight.picking_game)
    await message.answer(
        f"🔍 Найдено: {len(games)}\n\nВыберите игру:",
        reply_markup=games_search_create(games),
    )


@router.callback_query(CreateNight.picking_game, F.data.startswith("pickgame:"))
async def pick_game(call: CallbackQuery, state: FSMContext) -> None:
    game_id = int(call.data.split(":")[1])
    await state.update_data(game_id=game_id)
    await state.set_state(CreateNight.time_start)
    await call.message.edit_text(
        "Введите время начала в формате ЧЧ:ММ (например, 18:30):"
    )
    await call.answer()


@router.message(CreateNight.time_start)
async def enter_time_start(message: Message, state: FSMContext) -> None:
    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Введите время как ЧЧ:ММ:")
        return
    await state.update_data(time_start=message.text.strip())
    await state.set_state(CreateNight.time_end)
    await message.answer("Введите время окончания в формате ЧЧ:ММ:")


@router.message(CreateNight.time_end)
async def enter_time_end(message: Message, state: FSMContext) -> None:
    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Введите время как ЧЧ:ММ:")
        return
    data = await state.get_data()
    if message.text.strip() <= data["time_start"]:
        await message.answer("Время окончания должно быть позже начала. Повторите:")
        return
    await state.update_data(time_end=message.text.strip())
    await state.set_state(CreateNight.slots)
    await message.answer("Сколько свободных мест на эту игру?")


@router.message(CreateNight.slots)
async def enter_slots(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit() or int(message.text.strip()) <= 0:
        await message.answer("Введите положительное число:")
        return
    slots = int(message.text.strip())
    await state.update_data(slots=slots)

    data = await state.get_data()
    game = await get_game(data["game_id"])

    night_id = data.get("night_id")
    if night_id is None:
        night_id = await create_game_night(
            data["date"], data["location"], message.from_user.id
        )
        await state.update_data(night_id=night_id)

    await add_session(
        night_id,
        data["game_id"],
        data["time_start"],
        data["time_end"],
        slots,
    )

    date_display = data.get("date_display", data["date"])
    text = (
        f"✅ Добавлена игра «{game['title']}» "
        f"({data['time_start']}–{data['time_end']}), мест: {slots}.\n\n"
        f"Игротека: {date_display}, {data['location']}.\n\n"
        f"Что дальше?"
    )

    await state.update_data(game_id=None, time_start=None, time_end=None, slots=None)
    await state.set_state(CreateNight.searching_game)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить ещё игру", callback_data="host_add_more")
    kb.button(text="✅ Завершить создание", callback_data="host_finish")
    kb.button(text="❌ Отмена", callback_data="host_cancel")
    kb.adjust(1)

    await message.answer(text, reply_markup=kb.as_markup())


@router.callback_query(F.data == "host_add_more")
async def host_add_more(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CreateNight.searching_game)
    await call.message.edit_text(
        "🔍 Введите название игры или его часть:",
        reply_markup=search_prompt_keyboard("host_finish"),
    )
    await call.answer()


@router.callback_query(F.data == "host_finish")
async def host_finish(call: CallbackQuery, state: FSMContext) -> None:
    is_host = await _is_host_or_admin(call.from_user.id)
    data = await state.get_data()
    await state.clear()

    if not data.get("night_id"):
        await call.message.edit_text(
            "Игротека не создана: не добавлено ни одной игры.",
            reply_markup=main_menu(is_host, call.from_user.id),
        )
        await call.answer()
        return

    date_display = data.get("date_display", data.get("date", "—"))
    location = data.get("location", "—")

    await call.message.edit_text(
        f"✅ Игротека на {date_display} ({location}) создана.\n"
        f"Игроки смогут увидеть её в разделе «Расписание».",
        reply_markup=main_menu(is_host, call.from_user.id),
    )
    await call.answer()


@router.callback_query(F.data == "host_cancel")
async def host_cancel(call: CallbackQuery, state: FSMContext) -> None:
    is_host = await _is_host_or_admin(call.from_user.id)
    await state.clear()
    await call.message.edit_text(
        "Создание игротеки отменено.",
        reply_markup=main_menu(is_host, call.from_user.id),
    )
    await call.answer()


# ============ СПИСОК ИГРОТЕК ============

@router.callback_query(F.data == "host_manage_list")
async def manage_list(call: CallbackQuery) -> None:
    if not await _is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return

    nights = await list_all_upcoming_nights()
    if not nights:
        await call.message.edit_text(
            "Нет предстоящих игротек.",
            reply_markup=host_menu(),
        )
        await call.answer()
        return

    # «Свои» — только те, где host_telegram_id == текущий пользователь.
    # Для админа чужие игротеки остаются с 👀, хотя он может ими управлять.
    own_ids = {
        n["id"] for n in nights
        if n["host_telegram_id"] == call.from_user.id
    }

    await call.message.edit_text(
        "Предстоящие игротеки:",
        reply_markup=host_nights_list(nights, own_ids),
    )
    await call.answer()


# ============ КАРТОЧКА ИГРОТЕКИ ============

@router.callback_query(F.data.startswith("hn:"))
async def night_card(call: CallbackQuery) -> None:
    if not await _is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return

    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not night:
        await call.answer("Игротека не найдена", show_alert=True)
        return

    can_manage = await _can_manage_night(call.from_user.id, night)
    is_own = night["host_telegram_id"] == call.from_user.id

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

    lines = [
        "🎲 <b>Игротека</b>",
        f"📅 {_fmt_date(night['date'])}",
        f"📍 {night['location']}",
        f"Игр: {night['sessions_count']} • Записей: {night['total_taken']}",
    ]
    if is_admin(call.from_user.id) and not is_own:
        lines.append("<i>(админ: игротека другого хоста)</i>")
    elif not can_manage:
        lines.append("<i>(игротека другого хоста)</i>")

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

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=host_night_card(night_id, is_owner=can_manage),
    )
    await call.answer()


# ============ РЕДАКТИРОВАНИЕ ============

@router.callback_query(F.data.startswith("hn_date:"))
async def edit_date(call: CallbackQuery, state: FSMContext) -> None:
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not await _can_manage_night(call.from_user.id, night):
        await call.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(EditNight.new_date)
    await state.update_data(night_id=night_id)
    await call.message.edit_text(
        f"Текущая дата: {_fmt_date(night['date'])}\n\n"
        f"Введите новую дату в формате ДД.ММ.ГГГГ:",
        reply_markup=cancel_edit(night_id),
    )
    await call.answer()


@router.message(EditNight.new_date)
async def save_date(message: Message, state: FSMContext) -> None:
    try:
        parsed = datetime.strptime(message.text.strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer("Неверный формат. Введите дату как ДД.ММ.ГГГГ:")
        return
    data = await state.get_data()
    night_id = data["night_id"]

    night = await get_night(night_id)
    if not await _can_manage_night(message.from_user.id, night):
        await state.clear()
        await message.answer("Нет доступа к этой игротеке.")
        return

    await update_night_date(night_id, parsed.strftime("%Y-%m-%d"))
    await state.clear()

    night = await get_night(night_id)
    text = (
        f"✅ Дата обновлена: {_fmt_date(night['date'])}\n\n"
        f"🎲 Игротека\n"
        f"Дата: {_fmt_date(night['date'])}\n"
        f"Место: {night['location']}\n"
        f"Игр: {night['sessions_count']}\n"
        f"Записей: {night['total_taken']}"
    )
    can_manage = await _can_manage_night(message.from_user.id, night)
    await message.answer(text, reply_markup=host_night_card(night_id, is_owner=can_manage))


@router.callback_query(F.data.startswith("hn_loc:"))
async def edit_location(call: CallbackQuery, state: FSMContext) -> None:
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not await _can_manage_night(call.from_user.id, night):
        await call.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(EditNight.new_location)
    await state.update_data(night_id=night_id)
    await call.message.edit_text(
        f"Текущее место: {night['location']}\n\n"
        f"Введите новое место проведения:",
        reply_markup=cancel_edit(night_id),
    )
    await call.answer()


@router.message(EditNight.new_location)
async def save_location(message: Message, state: FSMContext) -> None:
    new_location = message.text.strip()
    if len(new_location) < 3:
        await message.answer("Слишком короткое название. Попробуйте ещё раз:")
        return
    data = await state.get_data()
    night_id = data["night_id"]

    night = await get_night(night_id)
    if not await _can_manage_night(message.from_user.id, night):
        await state.clear()
        await message.answer("Нет доступа к этой игротеке.")
        return

    await update_night_location(night_id, new_location)
    await state.clear()

    night = await get_night(night_id)
    text = (
        f"✅ Место обновлено.\n\n"
        f"🎲 Игротека\n"
        f"Дата: {_fmt_date(night['date'])}\n"
        f"Место: {night['location']}\n"
        f"Игр: {night['sessions_count']}\n"
        f"Записей: {night['total_taken']}"
    )
    can_manage = await _can_manage_night(message.from_user.id, night)
    await message.answer(text, reply_markup=host_night_card(night_id, is_owner=can_manage))


# ============ УПРАВЛЕНИЕ ИГРАМИ ============

@router.callback_query(F.data.startswith("hn_sessions:"))
async def sessions_manage(call: CallbackQuery) -> None:
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not await _can_manage_night(call.from_user.id, night):
        await call.answer("Нет доступа", show_alert=True)
        return

    sessions = await get_night_sessions_for_edit(night_id)
    if not sessions:
        await call.message.edit_text(
            f"🎲 Игротека\n"
            f"Дата: {_fmt_date(night['date'])}\n"
            f"Место: {night['location']}\n"
            f"Игр: 0\n"
            f"Записей: 0\n\n"
            f"В игротеке пока нет игр. Добавьте первую.",
            reply_markup=host_night_card(night_id, is_owner=True),
        )
        await call.answer()
        return

    await call.message.edit_text(
        "Нажмите 🗑 на игре, чтобы удалить её из игротеки, "
        "или ➕, чтобы добавить новую:",
        reply_markup=host_sessions_list(night_id, sessions),
    )
    await call.answer()


@router.callback_query(F.data.startswith("hs_del:"))
async def session_delete_confirm(call: CallbackQuery) -> None:
    session_id = int(call.data.split(":")[1])

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT gs.game_night_id, gs.slots_taken, g.title
               FROM game_sessions gs
               JOIN games g ON g.id = gs.game_id
               WHERE gs.id = ?""",
            (session_id,),
        )
        row = await cur.fetchone()

    if not row:
        await call.answer("Сессия не найдена", show_alert=True)
        return

    night_id = row["game_night_id"]
    night = await get_night(night_id)
    if not await _can_manage_night(call.from_user.id, night):
        await call.answer("Нет доступа", show_alert=True)
        return

    warning = ""
    if row["slots_taken"] > 0:
        warning = (
            f"\n\n⚠️ На игру записано {row['slots_taken']} чел. "
            f"Их записи будут удалены без уведомления."
        )

    await call.message.edit_text(
        f"Удалить игру «{row['title']}» из игротеки?{warning}",
        reply_markup=confirm_delete_session(session_id, night_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("hs_del_yes:"))
async def session_delete_confirm_yes(call: CallbackQuery) -> None:
    session_id = int(call.data.split(":")[1])

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT game_night_id FROM game_sessions WHERE id = ?",
            (session_id,),
        )
        row = await cur.fetchone()

    if not row:
        await call.answer("Сессия уже удалена", show_alert=True)
        return

    night_id = row["game_night_id"]
    night = await get_night(night_id)
    if not await _can_manage_night(call.from_user.id, night):
        await call.answer("Нет доступа", show_alert=True)
        return

    await delete_session(session_id)

    sessions = await get_night_sessions_for_edit(night_id)
    if not sessions:
        await call.message.edit_text(
            "Все игры удалены. В игротеке больше нет сессий.",
            reply_markup=host_night_card(night_id, is_owner=True),
        )
    else:
        await call.message.edit_text(
            "✅ Игра удалена.\n\nНажмите на игру, чтобы удалить её из игротеки:",
            reply_markup=host_sessions_list(night_id, sessions),
        )
    await call.answer("Игра удалена")


# ============ УДАЛЕНИЕ ИГРОТЕКИ ============

@router.callback_query(F.data.startswith("hn_del:"))
async def night_delete_confirm(call: CallbackQuery) -> None:
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not await _can_manage_night(call.from_user.id, night):
        await call.answer("Нет доступа", show_alert=True)
        return

    reg_count = await count_registrations_for_night(night_id)
    warning = ""
    if reg_count > 0:
        warning = (
            f"\n\n⚠️ На игры этой игротеки записано {reg_count} чел. "
            f"Все записи будут удалены без уведомления."
        )

    await call.message.edit_text(
        f"Удалить игротеку?\n\n"
        f"Дата: {_fmt_date(night['date'])}\n"
        f"Место: {night['location']}\n"
        f"Игр: {night['sessions_count']}"
        f"{warning}",
        reply_markup=confirm_delete_night(night_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("hn_del_yes:"))
async def night_delete_confirm_yes(call: CallbackQuery) -> None:
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not await _can_manage_night(call.from_user.id, night):
        await call.answer("Нет доступа", show_alert=True)
        return

    await delete_night(night_id)

    nights = await list_all_upcoming_nights()
    own_ids = {
        n["id"] for n in nights
        if n["host_telegram_id"] == call.from_user.id
    }

    if not nights:
        await call.message.edit_text(
            "✅ Игротека удалена.\n\nПредстоящих игротек больше нет.",
            reply_markup=host_menu(),
        )
    else:
        await call.message.edit_text(
            "✅ Игротека удалена.\n\nПредстоящие игротеки:",
            reply_markup=host_nights_list(nights, own_ids),
        )
    await call.answer("Игротека удалена")


# ============ ДОБАВЛЕНИЕ ИГРЫ В ИГРОТЕКУ ============

@router.callback_query(F.data.startswith("hn_add:"))
async def add_game_start(call: CallbackQuery, state: FSMContext) -> None:
    if not await _is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return

    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not night:
        await call.answer("Игротека не найдена", show_alert=True)
        return

    await state.clear()
    await state.set_state(AddSessionToNight.searching_game)
    await state.update_data(night_id=night_id)

    await call.message.edit_text(
        "🔍 <b>Поиск игры</b>\n\n"
        "Введите название или его часть (например, <code>catan</code>):",
        parse_mode="HTML",
        reply_markup=search_prompt_keyboard(f"hn_sessions:{night_id}"),
    )
    await call.answer()


@router.message(AddSessionToNight.searching_game)
async def add_game_search(message: Message, state: FSMContext) -> None:
    query = message.text.strip()
    if len(query) < 2:
        await message.answer("Введите хотя бы 2 символа:")
        return

    data = await state.get_data()
    night_id = data["night_id"]

    games = await search_games(query, limit=10)

    if not games:
        await state.set_state(AddSessionToNight.searching_game)
        await message.answer(
            f"🔍 По запросу «{query}» ничего не найдено.\n\n"
            f"Попробуйте другое название:",
            reply_markup=search_prompt_keyboard(f"hn_sessions:{night_id}"),
        )
        return

    await state.set_state(AddSessionToNight.picking_game)
    await message.answer(
        f"🔍 Найдено: {len(games)}\n\nВыберите игру:",
        reply_markup=games_search_results(night_id, games),
    )


@router.callback_query(AddSessionToNight.picking_game, F.data.startswith("addgame:"))
async def add_game_pick(call: CallbackQuery, state: FSMContext) -> None:
    game_id = int(call.data.split(":")[1])
    await state.update_data(game_id=game_id)
    await state.set_state(AddSessionToNight.time_start)
    await call.message.edit_text(
        "Введите время начала в формате ЧЧ:ММ (например, 18:30):"
    )
    await call.answer()


@router.message(AddSessionToNight.time_start)
async def add_game_time_start(message: Message, state: FSMContext) -> None:
    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Введите время как ЧЧ:ММ:")
        return
    await state.update_data(time_start=message.text.strip())
    await state.set_state(AddSessionToNight.time_end)
    await message.answer("Введите время окончания в формате ЧЧ:ММ:")


@router.message(AddSessionToNight.time_end)
async def add_game_time_end(message: Message, state: FSMContext) -> None:
    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Введите время как ЧЧ:ММ:")
        return
    data = await state.get_data()
    if message.text.strip() <= data["time_start"]:
        await message.answer("Время окончания должно быть позже начала. Повторите:")
        return
    await state.update_data(time_end=message.text.strip())
    await state.set_state(AddSessionToNight.slots)
    await message.answer("Сколько свободных мест на эту игру?")


@router.message(AddSessionToNight.slots)
async def add_game_slots(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit() or int(message.text.strip()) <= 0:
        await message.answer("Введите положительное число:")
        return
    slots = int(message.text.strip())

    data = await state.get_data()
    night_id = data["night_id"]
    game_id = data["game_id"]
    time_start = data["time_start"]
    time_end = data["time_end"]

    await add_session(night_id, game_id, time_start, time_end, slots)
    await state.clear()

    game = await get_game(game_id)
    night = await get_night(night_id)
    can_manage = await _can_manage_night(message.from_user.id, night)
    sessions = await get_night_sessions_for_edit(night_id)

    if can_manage:
        text = (
            f"✅ Игра «{game['title']}» добавлена в игротеку.\n"
            f"📅 {_fmt_date(night['date'])} • {night['location']}\n\n"
            f"Нажмите 🗑 на игре, чтобы удалить её, "
            f"или ➕, чтобы добавить ещё:"
        )
        await message.answer(text, reply_markup=host_sessions_list(night_id, sessions))
    else:
        await message.answer(
            f"✅ Игра «{game['title']}» добавлена в игротеку "
            f"{_fmt_date(night['date'])} ({night['location']}).",
            reply_markup=host_night_card(night_id, is_owner=False),
        )