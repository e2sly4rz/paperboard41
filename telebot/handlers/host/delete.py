from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.queries import (
    get_night,
    delete_night,
    count_registrations_for_night,
    list_all_upcoming_nights,
    get_all_night_registrations,
)
from keyboards.menus import (
    confirm_delete_night,
    host_menu_with_nights,
    host_menu_empty,
)
from utils import fmt_date
from notifications import notify_night_deleted

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
            "Все записи будут удалены, записанным придёт уведомление."
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

    # NEW: собираем записанных ДО удаления (каскад снесёт registrations)
    rows = await get_all_night_registrations(night_id)

    games_by_user: dict[int, list[dict]] = {}
    registrants_map: dict[int, dict] = {}
    for r in rows:
        uid = r["telegram_id"]
        if not uid:
            continue
        registrants_map[uid] = r
        games_by_user.setdefault(uid, []).append({
            "game_title": r["game_title"],
            "time_start": r["time_start"],
            "time_end": r["time_end"],
        })

    night_date = night["date"]
    night_location = night["location"]

    await delete_night(night_id)

    # NEW: уведомляем записанных
    if registrants_map:
        await notify_night_deleted(
            call.bot,
            list(registrants_map.values()),
            call.from_user.id,
            night_date=night_date,
            night_location=night_location,
            games_by_user=games_by_user,
        )

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