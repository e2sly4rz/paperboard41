from datetime import datetime

import aiosqlite
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import DB_PATH
from database.queries import (
    list_games,
    get_game,
    get_user,
    create_game_night,
    add_session,
    list_host_nights,
    get_night,
    get_night_sessions_for_edit,
    update_night_date,
    update_night_location,
    delete_night,
    delete_session,
    count_registrations_for_night,
    get_all_night_registrations,
)
from keyboards.menus import (
    games_picker,
    confirm_session,
    main_menu,
    host_menu,
    host_nights_list,
    host_night_card,
    host_sessions_list,
    confirm_delete_night,
    confirm_delete_session,
    cancel_edit,
    night_participants_back,
)
from states.states import CreateNight, EditNight

router = Router()


async def _is_host(user_id: int) -> bool:
    """Читает уровень пользователя из БД в момент вызова."""
    user = await get_user(user_id)
    return bool(user and user["subscriber_level"] == "host")


def _fmt_date(iso_date: str) -> str:
    """ГГГГ-ММ-ДД → ДД.ММ.ГГГГ."""
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return iso_date or "—"


# ============ МЕНЮ ОРГАНИЗАТОРА ============

@router.callback_query(F.data == "host_menu")
async def open_host_menu(call: CallbackQuery) -> None:
    if not await _is_host(call.from_user.id):
        await call.answer("Только для хостов", show_alert=True)
        return
    await call.message.edit_text(
        "Меню организатора:",
        reply_markup=host_menu(),
    )
    await call.answer()


# ============ СОЗДАНИЕ ИГРОТЕКИ ============

@router.callback_query(F.data == "host_create")
async def start_create(call: CallbackQuery, state: FSMContext) -> None:
    if not await _is_host(call.from_user.id):
        await call.answer("Только хосты могут создавать игротеки", show_alert=True)
        return
    await state.clear()
    await state.set_state(CreateNight.date)
    await call.message.edit_text(
        "Создание игротеки.\n\nВведите дату в формате ДД.ММ.ГГГГ:"
    )
    await call.answer()


@router.message(CreateNight.date)
async def enter_date(message: Message, state: FSMContext) -> None:
    # Пользователь вводит ДД.ММ.ГГГГ, в БД храним ГГГГ-ММ-ДД
    try:
        parsed = datetime.strptime(message.text.strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer("Неверный формат. Введите дату как ДД.ММ.ГГГГ:")
        return
    await state.update_data(date=parsed.strftime("%Y-%m-%d"))
    await state.update_data(date_display=parsed.strftime("%d.%m.%Y"))
    await state.set_state(CreateNight.location)
    await message.answer("Введите место проведения:")


@router.message(CreateNight.location)
async def enter_location(message: Message, state: FSMContext) -> None:
    await state.update_data(location=message.text.strip())
    games = await list_games()
    await state.set_state(CreateNight.picking_game)
    await message.answer(
        "Выберите игру из каталога:",
        reply_markup=games_picker(games),
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

    # Игротека создаётся один раз, при первой игре.
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
        f"Добавлена игра «{game['title']}» "
        f"({data['time_start']}–{data['time_end']}), мест: {slots}.\n\n"
        f"Игротека: {date_display}, {data['location']}."
    )

    await state.set_state(CreateNight.picking_game)
    games = await list_games()
    await message.answer(text, reply_markup=games_picker(games))


@router.callback_query(F.data == "host_add_more")
async def host_add_more(call: CallbackQuery, state: FSMContext) -> None:
    games = await list_games()
    await state.set_state(CreateNight.picking_game)
    await call.message.edit_text(
        "Выберите следующую игру:",
        reply_markup=games_picker(games),
    )
    await call.answer()


@router.callback_query(F.data == "host_finish")
async def host_finish(call: CallbackQuery, state: FSMContext) -> None:
    is_host = await _is_host(call.from_user.id)
    data = await state.get_data()
    await state.clear()

    date_display = data.get("date_display", data.get("date", "—"))
    location = data.get("location", "—")

    await call.message.edit_text(
        f"✅ Игротека на {date_display} ({location}) создана.\n"
        f"Игроки смогут увидеть её в разделе «Расписание».",
        reply_markup=main_menu(is_host),
    )
    await call.answer()


@router.callback_query(F.data == "host_cancel")
async def host_cancel(call: CallbackQuery, state: FSMContext) -> None:
    is_host = await _is_host(call.from_user.id)
    await state.clear()
    await call.message.edit_text(
        "Создание игротеки отменено.",
        reply_markup=main_menu(is_host),
    )
    await call.answer()


# ============ СПИСОК ИГРОТЕК ХОСТА ============

@router.callback_query(F.data == "host_manage_list")
async def manage_list(call: CallbackQuery) -> None:
    if not await _is_host(call.from_user.id):
        await call.answer("Только для хостов", show_alert=True)
        return
    nights = await list_host_nights(call.from_user.id)
    if not nights:
        await call.message.edit_text(
            "У вас нет предстоящих игротек.",
            reply_markup=host_menu(),
        )
        await call.answer()
        return
    await call.message.edit_text(
        "Ваши предстоящие игротеки:",
        reply_markup=host_nights_list(nights),
    )
    await call.answer()


# ============ КАРТОЧКА ИГРОТЕКИ ============

@router.callback_query(F.data.startswith("hn:"))
async def night_card(call: CallbackQuery) -> None:
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not night:
        await call.answer("Игротека не найдена", show_alert=True)
        return
    if night["host_telegram_id"] != call.from_user.id:
        await call.answer("Это не ваша игротека", show_alert=True)
        return

    text = (
        f"🎲 Игротека\n"
        f"Дата: {_fmt_date(night['date'])}\n"
        f"Место: {night['location']}\n"
        f"Игр: {night['sessions_count']}\n"
        f"Записей: {night['total_taken']}"
    )
    await call.message.edit_text(text, reply_markup=host_night_card(night_id))
    await call.answer()


# ============ СВОДНЫЙ СПИСОК УЧАСТНИКОВ ============

@router.callback_query(F.data.startswith("hn_part:"))
async def night_participants(call: CallbackQuery) -> None:
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not night or night["host_telegram_id"] != call.from_user.id:
        await call.answer("Нет доступа", show_alert=True)
        return

    rows = await get_all_night_registrations(night_id)

    # Группируем по session_id, сохраняя порядок (уже отсортирован по времени)
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

    header = (
        f"👥 <b>Участники игротеки</b>\n"
        f"📅 {_fmt_date(night['date'])}\n"
        f"📍 {night['location']}\n"
        f"Всего записей: {night['total_taken']}\n"
    )

    if not sessions:
        body = "\n\nВ этой игротеке пока нет игр."
    else:
        blocks = []
        for s in sessions.values():
            time_range = f"{s['time_start']}–{s['time_end'] or '?'}"
            block_header = (
                f"\n🎲 <b>{s['game_title']}</b>\n"
                f"⏰ {time_range} • "
                f"занято {s['slots_taken']} из {s['max_slots']}"
            )
            if not s["players"]:
                blocks.append(block_header + "\n— никто не записан")
            else:
                lines = []
                for i, p in enumerate(s["players"], 1):
                    name_parts = [p["first_name"] or "", p["last_name"] or ""]
                    name = " ".join(x for x in name_parts if x).strip() or "Без имени"
                    username = f" (@{p['username']})" if p["username"] else ""
                    lines.append(f"{i}. {name}{username}")
                blocks.append(block_header + "\n" + "\n".join(lines))
        body = "\n".join(blocks)

    await call.message.edit_text(
        header + body,
        parse_mode="HTML",
        reply_markup=night_participants_back(night_id),
    )
    await call.answer()


# ============ РЕДАКТИРОВАНИЕ ДАТЫ ============

@router.callback_query(F.data.startswith("hn_date:"))
async def edit_date(call: CallbackQuery, state: FSMContext) -> None:
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not night or night["host_telegram_id"] != call.from_user.id:
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
    await message.answer(text, reply_markup=host_night_card(night_id))


# ============ РЕДАКТИРОВАНИЕ МЕСТА ============

@router.callback_query(F.data.startswith("hn_loc:"))
async def edit_location(call: CallbackQuery, state: FSMContext) -> None:
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not night or night["host_telegram_id"] != call.from_user.id:
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
    await message.answer(text, reply_markup=host_night_card(night_id))


# ============ УПРАВЛЕНИЕ ИГРАМИ ============

@router.callback_query(F.data.startswith("hn_sessions:"))
async def sessions_manage(call: CallbackQuery) -> None:
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not night or night["host_telegram_id"] != call.from_user.id:
        await call.answer("Нет доступа", show_alert=True)
        return
    sessions = await get_night_sessions_for_edit(night_id)
    if not sessions:
        await call.message.edit_text(
            "В этой игротеке нет игр.",
            reply_markup=host_night_card(night_id),
        )
        await call.answer()
        return
    await call.message.edit_text(
        "Нажмите на игру, чтобы удалить её из игротеки:",
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
    if not night or night["host_telegram_id"] != call.from_user.id:
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
    await delete_session(session_id)

    sessions = await get_night_sessions_for_edit(night_id)
    if not sessions:
        await call.message.edit_text(
            "Все игры удалены. В игротеке больше нет сессий.",
            reply_markup=host_night_card(night_id),
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
    if not night or night["host_telegram_id"] != call.from_user.id:
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
    if not night or night["host_telegram_id"] != call.from_user.id:
        await call.answer("Нет доступа", show_alert=True)
        return

    await delete_night(night_id)

    nights = await list_host_nights(call.from_user.id)
    if not nights:
        await call.message.edit_text(
            "✅ Игротека удалена.\n\nУ вас больше нет предстоящих игротек.",
            reply_markup=host_menu(),
        )
    else:
        await call.message.edit_text(
            "✅ Игротека удалена.\n\nВаши оставшиеся игротеки:",
            reply_markup=host_nights_list(nights),
        )
    await call.answer("Игротека удалена")