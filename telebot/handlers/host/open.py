from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.queries import (
    get_night,
    open_night_registration,
    get_users_for_registration_notification_by_levels,
    get_active_poll_for_night,
)
from keyboards.menus import host_night_card_with_poll
from utils import fmt_date
from notifications import notify_registration_opened

from ._helpers import can_manage_night

router = Router()


@router.callback_query(F.data.startswith("night_open:"))
async def night_open(call: CallbackQuery) -> None:
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not await can_manage_night(call.from_user.id, night):
        await call.answer("Нет доступа", show_alert=True)
        return

    if night["registration_open"]:
        await call.answer("Запись уже открыта", show_alert=True)
        return

    ok = await open_night_registration(night_id, call.from_user.id)
    if not ok:
        await call.answer("Не удалось открыть запись", show_alert=True)
        return

    # Уведомляем Проводников и хостов
    users = await get_users_for_registration_notification_by_levels(
        night_id, ["provodnik", "host"]
    )
    sent = await notify_registration_opened(
        call.bot,
        users,
        call.from_user.id,
        night_date=night["date"],
        night_location=night["location"],
        night_id=night_id,
        target_level="provodnik",
    )

    night = await get_night(night_id)
    poll = await get_active_poll_for_night(night_id)

    text = (
        f"🔓 <b>Запись открыта</b>\n\n"
        f"📅 {fmt_date(night['date'])}\n"
        f"📍 {night['location']}\n"
        f"Игр: {night['sessions_count']} • Записей: {night['total_taken']}\n\n"
        f"Уведомлено Проводников и хостов: {sent}\n\n"
        f"<i>Пассажиры получат уведомление за 8 часов до начала.</i>"
    )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=host_night_card_with_poll(
            night_id,
            is_owner=True,
            has_active_poll=bool(poll),
            has_any_poll=bool(poll),
            registration_open=True,
        ),
    )
    await call.answer("Запись открыта")