from datetime import datetime

import aiosqlite
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import DB_PATH
from database.queries import (
    get_game,
    get_night,
    get_night_sessions_for_edit,
    add_session,
    delete_session,
    search_games,
)
from keyboards.menus import (
    host_night_card,
    host_sessions_list,
    confirm_delete_session,
    games_search_results,
    search_prompt_keyboard,
    time_start_picker,
    duration_picker,
    slots_picker_autofill,
)
from states.states import AddSessionToNight
from utils import is_admin, is_host_or_admin, fmt_date

from ._helpers import add_minutes, can_manage_night, can_delete_session

router = Router()


@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery) -> None:
    await call.answer(
        "Эту игру добавил другой хост. Удалить её может только он "
        "или владелец игротеки.",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("hn_sessions:"))
async def sessions_manage(call: CallbackQuery) -> None:
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not night:
        await call.answer("Игротека не найдена", show_alert=True)
        return

    can_manage = await can_manage_night(call.from_user.id, night)
    sessions = await get_night_sessions_for_edit(night_id)

    if not can_manage:
        has_authored = any(
            s.get("created_by_user_id") == call.from_user.id
            for s in sessions
        )
        if not has_authored:
            await call.answer("Нет доступа", show_alert=True)
            return

    if not sessions:
        await call.message.edit_text(
            f"🎲 Игротека\n"
            f"Дата: {fmt_date(night['date'])}\n"
            f"Место: {night['location']}\n"
            f"Игр: 0\n"
            f"Записей: 0\n\n"
            f"В игротеке пока нет игр. Добавьте первую.",
            reply_markup=host_night_card(night_id, is_owner=can_manage),
        )
        await call.answer()
        return

    await call.message.edit_text(
        "Нажмите 🗑 на игре, чтобы удалить её из игротеки, "
        "или ➕, чтобы добавить новую:",
        reply_markup=host_sessions_list(
            night_id, sessions,
            can_delete_all=can_manage,
            user_id=call.from_user.id,
        ),
    )
    await call.answer()


@router.callback_query(F.data.startswith("hs_del:"))
async def session_delete_confirm(call: CallbackQuery) -> None:
    session_id = int(call.data.split(":")[1])

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT gs.game_night_id, gs.slots_taken,
                      gs.created_by_user_id, g.title
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
    if not await can_delete_session(call.from_user.id, session_id, night):
        await call.answer("Нет доступа", show_alert=True)
        return

    is_owner = (
        night["host_telegram_id"] == call.from_user.id
        or is_admin(call.from_user.id)
    )
    is_author = row["created_by_user_id"] == call.from_user.id

    warning = ""
    if row["slots_taken"] > 0:
        warning = (
            f"\n\n⚠️ На игру записано {row['slots_taken']} чел. "
            f"Их записи будут удалены без уведомления."
        )
    if is_author and not is_owner:
        warning += (
            "\n\n<i>Вы добавляли эту игру в чужую игротеку. "
            "Владелец игротеки не будет уведомлён об удалении.</i>"
        )

    await call.message.edit_text(
        f"Удалить игру «{row['title']}» из игротеки?{warning}",
        parse_mode="HTML",
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
    if not await can_delete_session(call.from_user.id, session_id, night):
        await call.answer("Нет доступа", show_alert=True)
        return

    await delete_session(session_id)

    can_manage = await can_manage_night(call.from_user.id, night)
    sessions = await get_night_sessions_for_edit(night_id)
    if not sessions:
        await call.message.edit_text(
            "Все игры удалены. В игротеке больше нет сессий.",
            reply_markup=host_night_card(night_id, is_owner=can_manage),
        )
    else:
        await call.message.edit_text(
            "✅ Игра удалена.\n\nНажмите на игру, чтобы удалить её из игротеки:",
            reply_markup=host_sessions_list(
                night_id, sessions,
                can_delete_all=can_manage,
                user_id=call.from_user.id,
            ),
        )
    await call.answer("Игра удалена")


# ---------- Добавление игры ----------

async def _finalize_add_session(message, state: FSMContext,
                                slots: int, user_id: int) -> None:
    data = await state.get_data()
    night_id = data["night_id"]
    game_id = data["game_id"]

    await add_session(
        night_id,
        game_id,
        data["time_start"],
        data["time_end"],
        slots,
        created_by_user_id=user_id,
    )
    await state.clear()

    game = await get_game(game_id)
    night = await get_night(night_id)
    can_manage = await can_manage_night(user_id, night)
    sessions = await get_night_sessions_for_edit(night_id)

    if can_manage:
        text = (
            f"✅ Игра «{game['title']}» добавлена в игротеку.\n"
            f"📅 {fmt_date(night['date'])} • {night['location']}\n\n"
            "Нажмите 🗑 на игре, чтобы удалить её, "
            "или ➕, чтобы добавить ещё:"
        )
        await message.answer(
            text,
            reply_markup=host_sessions_list(
                night_id, sessions,
                can_delete_all=True,
                user_id=user_id,
            ),
        )
    else:
        await message.answer(
            f"✅ Игра «{game['title']}» добавлена в игротеку "
            f"{fmt_date(night['date'])} ({night['location']}).",
            reply_markup=host_night_card(night_id, is_owner=False),
        )


@router.callback_query(F.data.startswith("hn_add:"))
async def add_game_start(call: CallbackQuery, state: FSMContext) -> None:
    if not await is_host_or_admin(call.from_user.id):
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
            "Попробуйте другое название:",
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
        "⏰ <b>Время начала игры</b>\n\nВыберите час:",
        parse_mode="HTML",
        reply_markup=time_start_picker(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("pickstart:"), AddSessionToNight.time_start)
async def add_game_time_start_pick(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 1)[1]

    if value == "manual":
        await call.message.edit_text(
            "Введите время начала в формате ЧЧ:ММ:"
        )
        return

    await state.update_data(time_start=value)

    data = await state.get_data()
    game = await get_game(data["game_id"])

    await state.set_state(AddSessionToNight.time_end)
    await call.message.edit_text(
        f"⏰ Начало: <b>{value}</b>\n\n"
        f"🎲 {game['title']}\n"
        f"Обычная длительность: "
        f"{game.get('duration_min') or '?'}–{game.get('duration_max') or '?'} мин\n\n"
        "Выберите длительность партии:",
        parse_mode="HTML",
        reply_markup=duration_picker(game),
    )
    await call.answer()


@router.callback_query(F.data.startswith("pickdur:"), AddSessionToNight.time_end)
async def add_game_duration_pick(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 1)[1]

    if value == "manual":
        await call.message.edit_text(
            "Введите время окончания в формате ЧЧ:ММ:"
        )
        return

    minutes = int(value)
    data = await state.get_data()
    time_start = data["time_start"]
    time_end = add_minutes(time_start, minutes)

    if time_end <= time_start:
        await call.answer(
            "Игра заканчивается на следующий день. "
            "Выберите меньшую длительность или введите окончание вручную.",
            show_alert=True,
        )
        return

    await state.update_data(time_end=time_end)

    game = await get_game(data["game_id"])
    default_slots = game.get("max_players") or 4

    await state.set_state(AddSessionToNight.slots)
    await call.message.edit_text(
        f"⏰ Время: <b>{time_start}–{time_end}</b>\n\n"
        f"🎲 {game['title']}\n"
        f"Игроков по правилам: "
        f"{game.get('min_players') or '?'}–{game.get('max_players') or '?'}\n\n"
        "Сколько свободных мест?",
        parse_mode="HTML",
        reply_markup=slots_picker_autofill(game, default_slots),
    )
    await call.answer()


@router.callback_query(F.data.startswith("pickslots:"), AddSessionToNight.slots)
async def add_game_slots_pick(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 1)[1]

    if value == "manual":
        await call.message.edit_text(
            "Введите количество свободных мест (положительное число):"
        )
        return

    slots = int(value)
    await _finalize_add_session(call.message, state, slots, call.from_user.id)
    await call.answer()


# --- Ручной ввод как fallback ---

@router.message(AddSessionToNight.time_start)
async def add_game_time_start(message: Message, state: FSMContext) -> None:
    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Введите время как ЧЧ:ММ:")
        return
    await state.update_data(time_start=message.text.strip())
    await state.set_state(AddSessionToNight.time_end)

    data = await state.get_data()
    game = await get_game(data["game_id"])
    await message.answer(
        f"⏰ Начало: <b>{message.text.strip()}</b>\n\n"
        f"🎲 {game['title']}\n\n"
        "Выберите длительность партии:",
        parse_mode="HTML",
        reply_markup=duration_picker(game),
    )


@router.message(AddSessionToNight.time_end)
async def add_game_time_end(message: Message, state: FSMContext) -> None:
    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Введите время как ЧЧ:ММ:")
        return
    data = await state.get_data()
    if message.text.strip() <= data["time_start"]:
        await message.answer(
            "Время окончания должно быть позже начала. Повторите:"
        )
        return
    await state.update_data(time_end=message.text.strip())
    await state.set_state(AddSessionToNight.slots)

    game = await get_game(data["game_id"])
    default_slots = game.get("max_players") or 4
    await message.answer(
        f"⏰ Время: <b>{data['time_start']}–{message.text.strip()}</b>\n\n"
        "Сколько свободных мест?",
        parse_mode="HTML",
        reply_markup=slots_picker_autofill(game, default_slots),
    )


@router.message(AddSessionToNight.slots)
async def add_game_slots(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit() or int(message.text.strip()) <= 0:
        await message.answer("Введите положительное число:")
        return
    slots = int(message.text.strip())
    await _finalize_add_session(message, state, slots, message.from_user.id)