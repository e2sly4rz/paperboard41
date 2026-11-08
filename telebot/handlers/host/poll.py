from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.queries import (
    get_night,
    create_availability_poll,
    get_active_poll_for_night,
    list_availability_responses,
    close_availability_poll,
    get_users_for_poll_notification,
)
from keyboards.menus import (
    host_night_card_with_poll,
)
from utils import fmt_date, safe_edit, is_host_or_admin
from notifications import notify_poll_created

router = Router()


@router.callback_query(F.data.startswith("poll_create:"))
async def poll_create(call: CallbackQuery) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return

    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not night:
        await call.answer("Игротека не найдена", show_alert=True)
        return

    existing = await get_active_poll_for_night(night_id)
    if existing:
        await call.answer(
            "В этой игротеке уже есть активный опрос. "
            "Другой хост уже его создал — можно посмотреть результаты "
            "или закрыть.",
            show_alert=True,
        )
        return

    await create_availability_poll(night_id, call.from_user.id)

    users = await get_users_for_poll_notification(night_id)
    sent = await notify_poll_created(
        call.bot,
        users,
        call.from_user.id,
        night_date=night["date"],
        night_location=night["location"],
        night_id=night_id,
    )

    await safe_edit(
        call.message,
        f"✅ <b>Опрос создан</b>\n\n"
        f"Игротека {fmt_date(night['date'])} • {night['location']}\n"
        f"Уведомлено игроков: {sent}\n\n"
        f"Игроки увидят опрос в карточке игротеки в «📅 Расписание».",
        parse_mode="HTML",
        reply_markup=host_night_card_with_poll(
            night_id,
            is_owner=False,
            has_active_poll=True,
            has_any_poll=True,
        ),
    )
    await call.answer()


@router.callback_query(F.data.startswith("poll_results:"))
async def poll_results(call: CallbackQuery) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return

    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not night:
        await call.answer("Игротека не найдена", show_alert=True)
        return

    poll = await get_active_poll_for_night(night_id)
    if not poll:
        await call.answer("Активного опроса нет", show_alert=True)
        return

    responses = await list_availability_responses(poll["id"])
    available = [r for r in responses if r["status"] == "available"]
    unavailable = [r for r in responses if r["status"] == "unavailable"]

    if not responses:
        await safe_edit(
            call.message,
            f"📊 <b>Результаты опроса</b>\n\n"
            f"Игротека {fmt_date(night['date'])} • {night['location']}\n\n"
            f"Пока никто не ответил.",
            parse_mode="HTML",
            reply_markup=host_night_card_with_poll(
                night_id, is_owner=False,
                has_active_poll=True, has_any_poll=True,
            ),
        )
        await call.answer()
        return

    hours = list(range(10, 24))
    counts = {}
    for h in hours:
        counts[h] = 0
        for r in available:
            from_h = int(r["time_from"].split(":")[0])
            to_h = int(r["time_to"].split(":")[0])
            if from_h <= h < to_h:
                counts[h] += 1

    max_count = max(counts.values()) or 1

    lines = [
        "📊 <b>Результаты опроса</b>",
        f"Игротека {fmt_date(night['date'])} • {night['location']}",
        f"Ответили: {len(responses)} чел. "
        f"(готовы играть: {len(available)}, не смогут: {len(unavailable)})\n",
    ]

    for h in hours:
        c = counts[h]
        if c == 0:
            continue
        bar_len = round(8 * c / max_count)
        bar = "█" * bar_len + "░" * (8 - bar_len)
        lines.append(f"{h:02d}:00  {bar} {c}")

    if available:
        lines.append("\n<b>Готовы играть:</b>")
        for r in available:
            name = r.get("first_name") or "Без имени"
            lines.append(f"• {name}: {r['time_from']}–{r['time_to']}")

    if unavailable:
        lines.append("\n<b>Не смогут прийти:</b>")
        for r in unavailable:
            name = r.get("first_name") or "Без имени"
            lines.append(f"• {name}")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3990] + "\n\n<i>…список обрезан</i>"

    await safe_edit(
        call.message,
        text,
        parse_mode="HTML",
        reply_markup=host_night_card_with_poll(
            night_id, is_owner=False,
            has_active_poll=True, has_any_poll=True,
        ),
    )
    await call.answer()


@router.callback_query(F.data.startswith("poll_close:"))
async def poll_close(call: CallbackQuery) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return

    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not night:
        await call.answer("Игротека не найдена", show_alert=True)
        return

    poll = await get_active_poll_for_night(night_id)
    if not poll:
        await call.answer("Активного опроса нет", show_alert=True)
        return

    await close_availability_poll(poll["id"])

    await safe_edit(
        call.message,
        f"🔒 <b>Опрос закрыт</b>\n\n"
        f"Игротека {fmt_date(night['date'])} • {night['location']}\n\n"
        f"Результаты больше не принимаются.",
        parse_mode="HTML",
        reply_markup=host_night_card_with_poll(
            night_id, is_owner=False,
            has_active_poll=False, has_any_poll=True,
        ),
    )
    await call.answer()