from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.queries import (
    get_night,
    create_availability_poll,
    get_active_poll_for_night,
    list_availability_responses,
    close_availability_poll,
    get_night_participants,
)
from keyboards.menus import (
    host_night_card_with_poll,
)
from utils import fmt_date
from notifications import notify_poll_created

from ._helpers import can_manage_night

router = Router()


@router.callback_query(F.data.startswith("poll_create:"))
async def poll_create(call: CallbackQuery) -> None:
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not await can_manage_night(call.from_user.id, night):
        await call.answer("Нет доступа", show_alert=True)
        return

    existing = await get_active_poll_for_night(night_id)
    if existing:
        await call.answer("Опрос уже создан", show_alert=True)
        return

    await create_availability_poll(night_id, call.from_user.id)

    participants = await get_night_participants(night_id)
    sent = 0
    if participants:
        await notify_poll_created(
            call.bot,
            participants,
            call.from_user.id,
            night_date=night["date"],
            night_location=night["location"],
        )
        sent = len([p for p in participants if p["telegram_id"] != call.from_user.id])

    await call.message.edit_text(
        f"✅ <b>Опрос создан</b>\n\n"
        f"Игротека {fmt_date(night['date'])} • {night['location']}\n"
        f"Уведомлено участников: {sent}\n\n"
        f"Игроки увидят опрос в карточке игротеки в «📅 Расписание».",
        parse_mode="HTML",
        reply_markup=host_night_card_with_poll(
            night_id, is_owner=True,
            has_active_poll=True, has_any_poll=True,
            registration_open=bool(night["registration_open"]),
        ),
    )
    await call.answer()


@router.callback_query(F.data.startswith("poll_results:"))
async def poll_results(call: CallbackQuery) -> None:
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not await can_manage_night(call.from_user.id, night):
        await call.answer("Нет доступа", show_alert=True)
        return

    poll = await get_active_poll_for_night(night_id)
    if not poll:
        await call.answer("Активного опроса нет", show_alert=True)
        return

    responses = await list_availability_responses(poll["id"])
    if not responses:
        await call.message.edit_text(
            f"📊 <b>Результаты опроса</b>\n\n"
            f"Игротека {fmt_date(night['date'])} • {night['location']}\n\n"
            f"Пока никто не ответил.",
            parse_mode="HTML",
            reply_markup=host_night_card_with_poll(
                night_id, is_owner=True,
                has_active_poll=True, has_any_poll=True,
                registration_open=bool(night["registration_open"]),
            ),
        )
        await call.answer()
        return

    # Гистограмма по часам 10–23
    hours = list(range(10, 24))
    counts = {}
    for h in hours:
        counts[h] = 0
        for r in responses:
            from_h = int(r["time_from"].split(":")[0])
            to_h = int(r["time_to"].split(":")[0])
            if from_h <= h < to_h:
                counts[h] += 1

    max_count = max(counts.values()) or 1

    lines = [
        "📊 <b>Результаты опроса</b>",
        f"Игротека {fmt_date(night['date'])} • {night['location']}",
        f"Ответили: {len(responses)} чел.\n",
    ]

    for h in hours:
        c = counts[h]
        if c == 0:
            continue
        bar_len = round(8 * c / max_count)
        bar = "█" * bar_len + "░" * (8 - bar_len)
        lines.append(f"{h:02d}:00  {bar} {c}")

    lines.append("\n<b>Ответы:</b>")
    for r in responses:
        name = r.get("first_name") or "Без имени"
        lines.append(f"• {name}: {r['time_from']}–{r['time_to']}")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3990] + "\n\n<i>…список обрезан</i>"

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=host_night_card_with_poll(
            night_id, is_owner=True,
            has_active_poll=True, has_any_poll=True,
        ),
    )
    await call.answer()


@router.callback_query(F.data.startswith("poll_close:"))
async def poll_close(call: CallbackQuery) -> None:
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not await can_manage_night(call.from_user.id, night):
        await call.answer("Нет доступа", show_alert=True)
        return

    poll = await get_active_poll_for_night(night_id)
    if not poll:
        await call.answer("Активного опроса нет", show_alert=True)
        return

    await close_availability_poll(poll["id"])

    await call.message.edit_text(
        f"🔒 <b>Опрос закрыт</b>\n\n"
        f"Игротека {fmt_date(night['date'])} • {night['location']}\n\n"
        f"Результаты больше не принимаются.",
        parse_mode="HTML",
        reply_markup=host_night_card_with_poll(
            night_id, is_owner=True,
            has_active_poll=False, has_any_poll=True,
        ),
    )
    await call.answer()