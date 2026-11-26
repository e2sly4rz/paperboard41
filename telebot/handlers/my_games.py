from aiogram import F, Router
from aiogram.types import CallbackQuery

from database.queries import (
    cancel_registration,
    get_user,
    list_user_registrations,
)
from keyboards.menus import main_menu, my_games_list
from notifications import notify_game_author_cancellation
from utils import is_host_or_admin, safe_edit

router = Router()


@router.callback_query(F.data == "my_games")
async def show_my_games(call: CallbackQuery) -> None:
    regs = await list_user_registrations(call.from_user.id)
    is_host_user = await is_host_or_admin(call.from_user.id)
    user = await get_user(call.from_user.id)
    is_provodnik = bool(user and user["subscriber_level"] in ("provodnik", "host"))
    if not regs:
        await safe_edit(
            call.message,
            "У вас пока нет активных записей.",
            reply_markup=main_menu(is_host_user, call.from_user.id,
                                   is_provodnik=is_provodnik),
        )
        await call.answer()
        return
    await safe_edit(
        call.message,
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
    user = await get_user(call.from_user.id)
    is_provodnik = bool(user and user["subscriber_level"] in ("provodnik", "host"))
    regs = await list_user_registrations(call.from_user.id)
    if not regs:
        await safe_edit(
            call.message,
            "У вас пока нет активных записей.",
            reply_markup=main_menu(is_host_user, call.from_user.id,
                                   is_provodnik=is_provodnik),
        )
    else:
        await safe_edit(
            call.message,
            "Ваши записи (нажмите, чтобы отменить):",
            reply_markup=my_games_list(regs),
        )