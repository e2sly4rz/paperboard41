from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.queries import (
    create_game,
    get_user,
    game_title_exists,
    list_all_upcoming_nights,
)
from keyboards.menus import host_menu_with_nights, host_menu_empty
from states.states import AddGame
from utils import is_host_or_admin

router = Router()


async def _host_menu_for(user_id: int):
    """Меню организатора с актуальным списком игротек."""
    nights = await list_all_upcoming_nights()
    if not nights:
        return host_menu_empty()

    own_ids = {
        n["id"] for n in nights
        if n["host_telegram_id"] == user_id
    }
    return host_menu_with_nights(nights, own_ids)


@router.callback_query(F.data == "host_add_game")
async def start_add_game(call: CallbackQuery, state: FSMContext) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return

    await state.clear()
    await state.set_state(AddGame.title)
    await call.message.edit_text(
        "➕ <b>Добавление игры в каталог</b>\n\n"
        "Введите название игры:",
        parse_mode="HTML",
    )
    await call.answer()


@router.message(AddGame.title)
async def enter_title(message: Message, state: FSMContext) -> None:
    title = message.text.strip()
    if len(title) < 2:
        await message.answer("Слишком короткое название. Попробуйте ещё раз:")
        return

    if await game_title_exists(title):
        await message.answer(
            f"⚠️ Игра с названием «{title}» уже есть в каталоге.\n\n"
            f"Введите другое название:"
        )
        return

    await state.update_data(title=title)
    await state.set_state(AddGame.players)
    await message.answer(
        f"Название: «{title}»\n\n"
        f"Введите количество игроков в формате «мин-макс» (например, 3-5):"
    )


@router.message(AddGame.players)
async def enter_players(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    try:
        parts = text.split("-")
        if len(parts) != 2:
            raise ValueError
        min_p = int(parts[0].strip())
        max_p = int(parts[1].strip())
        if min_p < 1 or max_p < min_p:
            raise ValueError
    except (ValueError, IndexError):
        await message.answer(
            "Неверный формат. Введите как «мин-макс», например 3-5:"
        )
        return
    await state.update_data(min_players=min_p, max_players=max_p)
    await state.set_state(AddGame.duration)
    await message.answer(
        "Введите длительность в минутах в формате «от-до» (например, 60-120):"
    )


@router.message(AddGame.duration)
async def enter_duration(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    try:
        parts = text.split("-")
        if len(parts) != 2:
            raise ValueError
        dmin = int(parts[0].strip())
        dmax = int(parts[1].strip())
        if dmin < 1 or dmax < dmin:
            raise ValueError
    except (ValueError, IndexError):
        await message.answer(
            "Неверный формат. Введите как «от-до», например 60-120:"
        )
        return
    await state.update_data(duration_min=dmin, duration_max=dmax)
    await state.set_state(AddGame.subscriber_only)

    kb = InlineKeyboardBuilder()
    kb.button(text="Нет, для всех", callback_data="game_sub:0")
    kb.button(text="Да, только Проводники", callback_data="game_sub:1")
    kb.button(text="❌ Отмена", callback_data="game_cancel")
    kb.adjust(1)

    await message.answer(
        "Игра только для подписчиков «Проводник»?",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data.startswith("game_sub:"))
async def enter_subscriber_only(call: CallbackQuery, state: FSMContext) -> None:
    is_sub = int(call.data.split(":")[1])
    data = await state.get_data()

    if not data.get("title"):
        await call.answer("Сессия устарела. Начните заново.", show_alert=True)
        await state.clear()
        menu = await _host_menu_for(call.from_user.id)
        await call.message.edit_text(
            "Добавление игры отменено.",
            reply_markup=menu,
        )
        return

    user = await get_user(call.from_user.id)
    owner_name = "Хост"
    if user:
        name_parts = [user["first_name"] or "", user["last_name"] or ""]
        owner_name = " ".join(p for p in name_parts if p).strip() or "Хост"

    game_id = await create_game(
        title=data["title"],
        genre=None,
        min_players=data["min_players"],
        max_players=data["max_players"],
        duration_min=data["duration_min"],
        duration_max=data["duration_max"],
        is_subscriber_only=is_sub,
        owner_user_id=call.from_user.id,
        owner_label=owner_name,
    )
    await state.clear()

    menu = await _host_menu_for(call.from_user.id)

    await call.message.edit_text(
        f"✅ <b>Игра добавлена в каталог</b>\n\n"
        f"🎲 {data['title']}\n"
        f"Игроков: {data['min_players']}–{data['max_players']}\n"
        f"Длительность: {data['duration_min']}–{data['duration_max']} мин\n"
        f"Только для Проводников: {'да' if is_sub else 'нет'}\n"
        f"Владелец: {owner_name}\n\n"
        f"ID игры: <code>{game_id}</code>",
        parse_mode="HTML",
        reply_markup=menu,
    )
    await call.answer()


@router.callback_query(F.data == "game_cancel")
async def cancel_add_game(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    menu = await _host_menu_for(call.from_user.id)
    await call.message.edit_text(
        "Добавление игры отменено.",
        reply_markup=menu,
    )
    await call.answer()