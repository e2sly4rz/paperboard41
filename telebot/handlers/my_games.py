from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.queries import (
    list_user_registrations,
    cancel_registration,
)
from keyboards.menus import my_games_list, main_menu
from utils import is_host_or_admin

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
    ok = await cancel_registration(reg_id, call.from_user.id)
    if ok:
        await call.answer("Запись отменена", show_alert=True)
    else:
        await call.answer("Не удалось отменить запись", show_alert=True)

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