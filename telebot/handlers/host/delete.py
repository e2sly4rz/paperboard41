from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.queries import (
    get_night,
    delete_night,
    count_registrations_for_night,
    list_all_upcoming_nights,
)
from keyboards.menus import (
    confirm_delete_night,
    host_menu_with_nights,
    host_menu_empty,
)
from utils import fmt_date

from ._helpers import can_manage_night

router = Router()


@router.callback_query(F.data.startswith("hn_del:"))
async def night_delete_confirm(call: CallbackQuery) -> None:
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not await can_manage_night(call.from_user.id, night):
        await call.answer("Нет доступа", show_alert=True)
        return

    reg_count = await count_registrations_for_night(night_id)
    warning = ""
    if reg_count > 0:
        warning = (
            f"\n\n⚠️ На игры этой игротеки записано {reg_count} чел. "
            "Все записи будут удалены без уведомления."
        )

    await call.message.edit_text(
        f"Удалить игротеку?\n\n"
        f"Дата: {fmt_date(night['date'])}\n"
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
    if not await can_manage_night(call.from_user.id, night):
        await call.answer("Нет доступа", show_alert=True)
        return

    await delete_night(night_id)

    nights = await list_all_upcoming_nights()
    own_ids = {
        n["id"] for n in nights
        if n["host_telegram_id"] == call.from_user.id
    }

    if not nights:
        await call.message.edit_text(
            "✅ Игротека удалена.\n\nПредстоящих игротек больше нет.",
            reply_markup=host_menu_empty(),
        )
    else:
        await call.message.edit_text(
            "✅ Игротека удалена.\n\n"
            "Выберите игротеку или создайте новую:",
            reply_markup=host_menu_with_nights(nights, own_ids),
        )
    await call.answer("Игротека удалена")