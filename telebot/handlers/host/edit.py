from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.queries import (
    get_night,
    update_night_date,
    update_night_location,
    get_active_poll_for_night,
)
from keyboards.menus import host_night_card_with_poll, cancel_edit
from states.states import EditNight
from utils import fmt_date

from ._helpers import can_manage_night

router = Router()


@router.callback_query(F.data.startswith("hn_date:"))
async def edit_date(call: CallbackQuery, state: FSMContext) -> None:
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not await can_manage_night(call.from_user.id, night):
        await call.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(EditNight.new_date)
    await state.update_data(night_id=night_id)
    await call.message.edit_text(
        f"Текущая дата: {fmt_date(night['date'])}\n\n"
        f"Введите новую дату в формате ДД.ММ.ГГГГ:",
        reply_markup=cancel_edit(night_id),
    )
    await call.answer()


@router.message(EditNight.new_date)
async def save_date(message: Message, state: FSMContext) -> None:
    try:
        parsed = datetime.strptime(message.text.strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer("Неверный формат. Введите дату как ДД.ММ.ГГГГ:")
        return
    data = await state.get_data()
    night_id = data["night_id"]

    night = await get_night(night_id)
    if not await can_manage_night(message.from_user.id, night):
        await state.clear()
        await message.answer("Нет доступа к этой игротеке.")
        return

    await update_night_date(night_id, parsed.strftime("%Y-%m-%d"))
    await state.clear()

    night = await get_night(night_id)
    poll = await get_active_poll_for_night(night_id)
    text = (
        f"✅ Дата обновлена: {fmt_date(night['date'])}\n\n"
        f"🎲 Игротека\n"
        f"Дата: {fmt_date(night['date'])}\n"
        f"Место: {night['location']}\n"
        f"Игр: {night['sessions_count']}\n"
        f"Записей: {night['total_taken']}"
    )
    can_manage = await can_manage_night(message.from_user.id, night)
    await message.answer(
        text,
        reply_markup=host_night_card_with_poll(
            night_id,
            is_owner=can_manage,
            has_active_poll=bool(poll),
            has_any_poll=bool(poll),
        ),
    )


@router.callback_query(F.data.startswith("hn_loc:"))
async def edit_location(call: CallbackQuery, state: FSMContext) -> None:
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not await can_manage_night(call.from_user.id, night):
        await call.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(EditNight.new_location)
    await state.update_data(night_id=night_id)
    await call.message.edit_text(
        f"Текущее место: {night['location']}\n\n"
        f"Введите новое место проведения:",
        reply_markup=cancel_edit(night_id),
    )
    await call.answer()


@router.message(EditNight.new_location)
async def save_location(message: Message, state: FSMContext) -> None:
    new_location = message.text.strip()
    if len(new_location) < 3:
        await message.answer("Слишком короткое название. Попробуйте ещё раз:")
        return
    data = await state.get_data()
    night_id = data["night_id"]

    night = await get_night(night_id)
    if not await can_manage_night(message.from_user.id, night):
        await state.clear()
        await message.answer("Нет доступа к этой игротеке.")
        return

    await update_night_location(night_id, new_location)
    await state.clear()

    night = await get_night(night_id)
    poll = await get_active_poll_for_night(night_id)
    text = (
        f"✅ Место обновлено.\n\n"
        f"🎲 Игротека\n"
        f"Дата: {fmt_date(night['date'])}\n"
        f"Место: {night['location']}\n"
        f"Игр: {night['sessions_count']}\n"
        f"Записей: {night['total_taken']}"
    )
    can_manage = await can_manage_night(message.from_user.id, night)
    await message.answer(
        text,
        reply_markup=host_night_card_with_poll(
            night_id,
            is_owner=can_manage,
            has_active_poll=bool(poll),
            has_any_poll=bool(poll),
        ),
    )