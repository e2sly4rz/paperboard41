import locale
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback

from database.queries import (
    get_game,
    get_night,
    create_game_night,
    add_session,
    search_games,
    get_active_poll_for_night,
    find_host_conflict,
)
from keyboards.menus import (
    main_menu,
    games_search_create,
    search_prompt_keyboard,
    time_start_picker,
    duration_picker,
    slots_picker_autofill,
    host_night_card_with_poll,
)
from states.states import CreateNight
from utils import is_host_or_admin, fmt_date, safe_edit

from ._helpers import add_minutes

router = Router()


def _make_calendar() -> SimpleCalendar:
    try:
        return SimpleCalendar(locale="ru_RU.UTF-8", show_alerts=True)
    except locale.Error:
        return SimpleCalendar(show_alerts=True)


async def _finalize_session(message, state: FSMContext,
                            slots: int, user_id: int) -> None:
    data = await state.get_data()
    game = await get_game(data["game_id"])

    conflict = await find_host_conflict(
        user_id,
        data["date"],
        data["time_start"],
        data["time_end"],
    )
    if conflict:
        c_start = conflict["time_start"]
        c_end = conflict["time_end"] or "?"
        await state.set_state(CreateNight.searching_game)
        await message.answer(
            f"⚠️ <b>У вас уже есть игра в это время</b>\n\n"
            f"🎲 {conflict['game_title']}\n"
            f"⏰ {c_start}–{c_end}\n\n"
            f"Нельзя добавить ещё одну игру на это же время. "
            f"Выберите другое время или другую дату.\n\n"
            f"Введите название игры для поиска:",
            parse_mode="HTML",
            reply_markup=search_prompt_keyboard("host_cancel"),
        )
        return

    night_id = data.get("night_id")
    if night_id is None:
        night_id = await create_game_night(
            data["date"], data["location"], user_id
        )
        await state.update_data(night_id=night_id)

    await add_session(
        night_id,
        data["game_id"],
        data["time_start"],
        data["time_end"],
        slots,
        created_by_user_id=user_id,
    )

    date_display = data.get("date_display", data["date"])
    text = (
        f"✅ Добавлена игра «{game['title']}» "
        f"({data['time_start']}–{data['time_end']}), мест: {slots}.\n\n"
        f"Игротека: {date_display}, {data['location']}.\n\n"
        f"Что дальше?"
    )

    await state.update_data(
        game_id=None, time_start=None, time_end=None, slots=None
    )
    await state.set_state(CreateNight.searching_game)

    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить ещё игру", callback_data="host_add_more")
    kb.button(text="✅ Завершить создание", callback_data="host_finish")
    kb.button(text="❌ Отмена", callback_data="host_cancel")
    kb.adjust(1)

    await message.answer(text, reply_markup=kb.as_markup())


@router.callback_query(F.data == "host_create")
async def start_create(call: CallbackQuery, state: FSMContext) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer(
            "Только организаторы могут создавать игротеки",
            show_alert=True,
        )
        return

    await state.clear()
    await state.set_state(CreateNight.date)

    calendar = _make_calendar()
    calendar.set_dates_range(
        datetime.now(),
        datetime.now() + timedelta(days=365),
    )

    await safe_edit(
        call.message,
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
    calendar = _make_calendar()
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

    await safe_edit(
        call.message,
        f"📅 Дата: {date_obj.strftime('%d.%m.%Y')}\n\n"
        f"Введите место проведения:"
    )
    await call.answer()


@router.message(CreateNight.location)
async def enter_location(message: Message, state: FSMContext) -> None:
    await state.update_data(location=message.text.strip())
    await state.set_state(CreateNight.searching_game)

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Создать без игр", callback_data="host_finish")
    kb.button(text="❌ Отмена", callback_data="host_cancel")
    kb.adjust(1)

    await message.answer(
        "🔍 <b>Поиск игры</b>\n\n"
        "Введите название или его часть (например, <code>catan</code>):\n\n"
        "<i>Или создайте игротеку без игр — добавите их позже.</i>",
        parse_mode="HTML",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data == "host_create_search_again")
async def create_search_again(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CreateNight.searching_game)

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Создать без игр", callback_data="host_finish")
    kb.button(text="❌ Отмена", callback_data="host_cancel")
    kb.adjust(1)

    await safe_edit(
        call.message,
        "🔍 Введите название или его часть:",
        reply_markup=kb.as_markup(),
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
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Создать без игр", callback_data="host_finish")
        kb.button(text="❌ Отмена", callback_data="host_cancel")
        kb.adjust(1)
        await message.answer(
            f"🔍 По запросу «{query}» ничего не найдено.\n\n"
            f"Попробуйте другое название:",
            reply_markup=kb.as_markup(),
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
    await safe_edit(
        call.message,
        "⏰ <b>Время начала игры</b>\n\nВыберите час:",
        parse_mode="HTML",
        reply_markup=time_start_picker(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("pickstart:"), CreateNight.time_start)
async def pick_time_start(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 1)[1]

    if value == "manual":
        await safe_edit(
            call.message,
            "Введите время начала в формате ЧЧ:ММ:"
        )
        return

    await state.update_data(time_start=value)

    data = await state.get_data()
    game = await get_game(data["game_id"])

    await state.set_state(CreateNight.time_end)
    await safe_edit(
        call.message,
        f"⏰ Начало: <b>{value}</b>\n\n"
        f"🎲 {game['title']}\n"
        f"Обычная длительность: "
        f"{game.get('duration_min') or '?'}–{game.get('duration_max') or '?'} мин\n\n"
        f"Выберите длительность партии:",
        parse_mode="HTML",
        reply_markup=duration_picker(game),
    )
    await call.answer()


@router.callback_query(F.data.startswith("pickdur:"), CreateNight.time_end)
async def pick_duration(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 1)[1]

    if value == "manual":
        await safe_edit(
            call.message,
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

    await state.set_state(CreateNight.slots)
    await safe_edit(
        call.message,
        f"⏰ Время: <b>{time_start}–{time_end}</b>\n\n"
        f"🎲 {game['title']}\n"
        f"Игроков по правилам: "
        f"{game.get('min_players') or '?'}–{game.get('max_players') or '?'}\n\n"
        f"Сколько свободных мест?",
        parse_mode="HTML",
        reply_markup=slots_picker_autofill(game, default_slots),
    )
    await call.answer()


@router.callback_query(F.data.startswith("pickslots:"), CreateNight.slots)
async def pick_slots(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 1)[1]

    if value == "manual":
        await safe_edit(
            call.message,
            "Введите количество свободных мест (положительное число):"
        )
        return

    slots = int(value)
    await _finalize_session(call.message, state, slots, call.from_user.id)
    await call.answer()


# --- Ручной ввод как fallback ---

@router.message(CreateNight.time_start)
async def enter_time_start(message: Message, state: FSMContext) -> None:
    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Введите время как ЧЧ:ММ:")
        return
    await state.update_data(time_start=message.text.strip())
    await state.set_state(CreateNight.time_end)

    data = await state.get_data()
    game = await get_game(data["game_id"])
    await message.answer(
        f"⏰ Начало: <b>{message.text.strip()}</b>\n\n"
        f"🎲 {game['title']}\n\n"
        f"Выберите длительность партии:",
        parse_mode="HTML",
        reply_markup=duration_picker(game),
    )


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

    game = await get_game(data["game_id"])
    default_slots = game.get("max_players") or 4
    await message.answer(
        f"⏰ Время: <b>{data['time_start']}–{message.text.strip()}</b>\n\n"
        f"Сколько свободных мест?",
        parse_mode="HTML",
        reply_markup=slots_picker_autofill(game, default_slots),
    )


@router.message(CreateNight.slots)
async def enter_slots(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit() or int(message.text.strip()) <= 0:
        await message.answer("Введите положительное число:")
        return
    slots = int(message.text.strip())
    await _finalize_session(message, state, slots, message.from_user.id)


@router.callback_query(F.data == "host_add_more")
async def host_add_more(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CreateNight.searching_game)

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Завершить создание", callback_data="host_finish")
    kb.button(text="❌ Отмена", callback_data="host_cancel")
    kb.adjust(1)

    await safe_edit(
        call.message,
        "🔍 Введите название игры или его часть:",
        reply_markup=kb.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data == "host_finish")
async def host_finish(call: CallbackQuery, state: FSMContext) -> None:
    is_host_user = await is_host_or_admin(call.from_user.id)
    data = await state.get_data()
    night_id = data.get("night_id")
    date = data.get("date")
    location = data.get("location")

    await state.clear()

    # Случай 1: игры уже добавлялись — night_id есть
    if night_id:
        night = await get_night(night_id)
        poll = await get_active_poll_for_night(night_id)

        text = (
            f"✅ <b>Игротека создана</b>\n\n"
            f"📅 {fmt_date(night['date'])}\n"
            f"📍 {night['location']}\n"
            f"Игр: {night['sessions_count']} • Записей: {night['total_taken']}\n\n"
            f"Добавьте игры и откройте запись, когда будете готовы."
        )
        await safe_edit(
            call.message,
            text,
            parse_mode="HTML",
            reply_markup=host_night_card_with_poll(
                night_id,
                is_owner=True,
                has_active_poll=bool(poll),
                has_any_poll=bool(poll),
                registration_open=bool(night["registration_open"]),
            ),
        )
        await call.answer()
        return

    # Случай 2: игры не добавлялись, но дата и место введены — создаём пустую игротеку
    if date and location:
        night_id = await create_game_night(
            date, location, call.from_user.id
        )
        night = await get_night(night_id)

        text = (
            f"✅ <b>Игротека создана</b>\n\n"
            f"📅 {fmt_date(night['date'])}\n"
            f"📍 {night['location']}\n"
            f"Игр: 0 • Записей: 0\n\n"
            f"<i>Пока в игротеке нет игр. Добавьте их через «➕ Добавить игру», "
            f"когда будете готовы.</i>\n\n"
            f"<i>Можно сначала создать опрос о времени, чтобы игроки "
            f"указали удобные часы, и подобрать игры по результатам.</i>"
        )
        await safe_edit(
            call.message,
            text,
            parse_mode="HTML",
            reply_markup=host_night_card_with_poll(
                night_id,
                is_owner=True,
                has_active_poll=False,
                has_any_poll=False,
                registration_open=False,
            ),
        )
        await call.answer()
        return

    # Случай 3: ничего не введено — ошибка
    await safe_edit(
        call.message,
        "Игротека не создана: не указаны дата и место.",
        reply_markup=main_menu(is_host_user, call.from_user.id),
    )
    await call.answer()


@router.callback_query(F.data == "host_cancel")
async def host_cancel(call: CallbackQuery, state: FSMContext) -> None:
    is_host_user = await is_host_or_admin(call.from_user.id)
    await state.clear()
    await safe_edit(
        call.message,
        "Создание игротеки отменено.",
        reply_markup=main_menu(is_host_user, call.from_user.id),
    )
    await call.answer()