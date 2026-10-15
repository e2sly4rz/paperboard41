from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.queries import (
    list_games,
    get_game,
    get_user,
    create_game_night,
    add_session,
)
from keyboards.menus import games_picker, confirm_session, main_menu
from states.states import CreateNight

router = Router()


async def _is_host(user_id: int) -> bool:
    """Читает уровень пользователя из БД в момент вызова."""
    user = await get_user(user_id)
    return bool(user and user["subscriber_level"] == "host")


# ---------- Создание игротеки ----------

@router.callback_query(F.data == "host_create")
async def start_create(call: CallbackQuery, state: FSMContext) -> None:
    if not await _is_host(call.from_user.id):
        await call.answer(
            "Только хосты могут создавать игротеки",
            show_alert=True,
        )
        return
    await state.clear()
    await state.set_state(CreateNight.date)
    await call.message.edit_text(
        "Создание игротеки.\n\nВведите дату в формате ДД.ММ.ГГГГ:"
    )
    await call.answer()


# ---------- Пошаговый ввод ----------

@router.message(CreateNight.date)
async def enter_date(message: Message, state: FSMContext) -> None:
    # Пользователь вводит ДД.ММ.ГГГГ, в БД храним ГГГГ-ММ-ДД
    try:
        parsed = datetime.strptime(message.text.strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer(
            "Неверный формат. Введите дату как ДД.ММ.ГГГГ:"
        )
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
        await message.answer(
            "Время окончания должно быть позже начала. Повторите:"
        )
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


# ---------- Завершение и отмена ----------

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
