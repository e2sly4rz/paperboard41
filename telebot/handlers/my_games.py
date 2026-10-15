from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.queries import (
    list_user_registrations,
    cancel_registration,
    get_user,
)
from keyboards.menus import my_games_list, main_menu

router = Router()


async def _is_host(user_id: int) -> bool:
    user = await get_user(user_id)
    return bool(user and user["subscriber_level"] == "host")


@router.callback_query(F.data == "my_games")
async def show_my_games(call: CallbackQuery) -> None:
    regs = await list_user_registrations(call.from_user.id)
    is_host = await _is_host(call.from_user.id)
    if not regs:
        await call.message.edit_text(
            "У вас пока нет активных записей.",
            reply_markup=main_menu(is_host),
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

    is_host = await _is_host(call.from_user.id)
    regs = await list_user_registrations(call.from_user.id)
    if not regs:
        await call.message.edit_text(
            "У вас пока нет активных записей.",
            reply_markup=main_menu(is_host),
        )
    else:
        await call.message.edit_text(
            "Ваши записи (нажмите, чтобы отменить):",
            reply_markup=my_games_list(regs),
        )