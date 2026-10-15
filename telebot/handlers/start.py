from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from config import ADMIN_ID
from database.queries import ensure_user, set_user_level, get_user
from keyboards.menus import main_menu

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    u = message.from_user
    await ensure_user(u.id, u.username, u.first_name, u.last_name)
    user = await get_user(u.id)
    is_host = user["subscriber_level"] == "host"
    await message.answer(
        f"Привет, {u.first_name}!\n\n"
        "Это бот клуба настольных игр. Здесь можно посмотреть расписание "
        "игротек и записаться на игры.",
        reply_markup=main_menu(is_host),
    )


@router.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, user: dict | None = None) -> None:
    is_host = bool(user and user["subscriber_level"] == "host")
    await call.message.edit_text(
        "Главное меню:",
        reply_markup=main_menu(is_host),
    )
    await call.answer()


@router.message(Command("grant"))
async def grant_host(message: Message) -> None:
    """Админ может выдать пользователю роль хоста командой:
       /grant <telegram_id> host|provodnik|guest"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("Недостаточно прав.")
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Использование: /grant <telegram_id> host|provodnik|guest")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("telegram_id должен быть числом.")
        return
    level = parts[2]
    if level not in ("host", "provodnik", "guest"):
        await message.answer("Уровень должен быть host, provodnik или guest.")
        return
    await set_user_level(target_id, level)
    await message.answer(f"Пользователю {target_id} установлен уровень {level}.")