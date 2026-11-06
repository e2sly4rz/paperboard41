from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.queries import (
    list_user_registrations,
    cancel_registration,
    get_user,
)
from keyboards.menus import my_games_list, main_menu
from utils import is_host_or_admin
from notifications import notify_game_author_cancellation

router = Router()


@router.callback_query(F.data == "my_games")
async def show_my_games(call: CallbackQuery) -> None:
    regs = await list_user_registrations(call.from_user.id)
    is_host_user = await is_host_or_admin(call.from_user.id)
    if not regs:
        await call.message.edit_text(
            "У вас пока нет активных записей.",
            reply_markup=main_menu(is_host_user, call.from_user.id),
        )
        await call.answer()
        return
    await call.message.edit_text(
        "Ваши записи (нажмите, чтобы отменить):",
        reply_markup=my_games_list(regs),
    )
    await call.answer()


@router.callback_query(F.data.startswith("cancel:"))
async def cancel(call: CallbackQuery) -> None:
    reg_id = int(call.data.split(":")[1])
    cancelled = await cancel_registration(reg_id, call.from_user.id)

    if not cancelled:
        await call.answer("Не удалось отменить запись", show_alert=True)
        return

    await call.answer("Запись отменена", show_alert=True)

    # Уведомление автору игры об отмене записи
    user = await get_user(call.from_user.id)
    player_name = "Без имени"
    if user:
        name_parts = [user["first_name"] or "", user["last_name"] or ""]
        player_name = " ".join(p for p in name_parts if p).strip() or "Без имени"
        if user.get("username"):
            player_name += f" (@{user['username']})"

    await notify_game_author_cancellation(
        call.bot,
        cancelled["session_id"],
        call.from_user.id,
        game_title=cancelled["game_title"],
        date_str=cancelled["date"],
        location=cancelled["location"],
        time_start=cancelled["time_start"],
        time_end=cancelled["time_end"],
        slots_taken=cancelled["slots_taken"],
        max_slots=cancelled["max_slots"],
        player_name=player_name,
    )

    # Обновляем экран «Мои записи»
    is_host_user = await is_host_or_admin(call.from_user.id)
    regs = await list_user_registrations(call.from_user.id)
    if not regs:
        await call.message.edit_text(
            "У вас пока нет активных записей.",
            reply_markup=main_menu(is_host_user, call.from_user.id),
        )
    else:
        await call.message.edit_text(
            "Ваши записи (нажмите, чтобы отменить):",
            reply_markup=my_games_list(regs),
        )