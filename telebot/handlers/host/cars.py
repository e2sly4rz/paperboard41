from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.queries import (
    get_night,
    list_all_upcoming_nights,
    list_cars,
    get_car,
    create_car,
    delete_car,
    assign_session_to_car,
    count_sessions_in_car,
    list_sessions_without_car,
    list_sessions_in_car,
)
from keyboards.menus import (
    host_cars_menu,
    host_car_card,
    confirm_delete_car,
    car_sessions_picker,
    search_prompt_keyboard,
)
from states.states import Car
from utils import is_host_or_admin, fmt_date, safe_edit

from ._helpers import can_manage_night

router = Router()


@router.callback_query(F.data == "host_cars")
async def host_cars(call: CallbackQuery) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return

    nights = await list_all_upcoming_nights()
    if not nights:
        await safe_edit(
            call.message,
            "🚃 <b>Вагоны (столы)</b>\n\n"
            "Сначала создайте игротеку.",
            parse_mode="HTML",
            reply_markup=None,
        )
        await call.answer()
        return

    if len(nights) == 1:
        await _show_cars_for_night(call, nights[0]["id"])
        return

    kb = InlineKeyboardBuilder()
    for n in nights:
        kb.button(
            text=f"{fmt_date(n['date'])} • {n['location']}",
            callback_data=f"host_cars_night:{n['id']}",
        )
    kb.button(text="⬅️ Назад", callback_data="host_menu")
    kb.adjust(1)
    await safe_edit(
        call.message,
        "🚃 <b>Вагоны (столы)</b>\n\nВыберите игротеку:",
        parse_mode="HTML",
        reply_markup=kb.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("host_cars_night:"))
async def host_cars_night(call: CallbackQuery) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return
    night_id = int(call.data.split(":")[1])
    await _show_cars_for_night(call, night_id)


async def _show_cars_for_night(call: CallbackQuery, night_id: int) -> None:
    night = await get_night(night_id)
    if not night:
        await call.answer("Игротека не найдена", show_alert=True)
        return
    cars = await list_cars(night_id)

    lines = [
        f"🚃 <b>Вагоны (столы)</b>",
        f"📅 {fmt_date(night['date'])} • {night['location']}",
    ]
    if not cars:
        lines.append("\n<i>Вагонов пока нет. Создайте первый.</i>")
    else:
        lines.append("")
        for car in cars:
            cnt = await count_sessions_in_car(car["id"])
            lines.append(f"🚃 {car['title']} — игр: {cnt}")

    await safe_edit(
        call.message,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=host_cars_menu(cars, night_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("host_car_create:"))
async def car_create_start(call: CallbackQuery, state: FSMContext) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return
    night_id = int(call.data.split(":")[1])
    night = await get_night(night_id)
    if not night:
        await call.answer("Игротека не найдена", show_alert=True)
        return
    await state.set_state(Car.title)
    await state.update_data(night_id=night_id)
    await safe_edit(
        call.message,
        f"🚃 <b>Новый вагон</b>\n\n"
        f"Игротека: {fmt_date(night['date'])} • {night['location']}\n\n"
        f"Введите название (например, «Новички»):",
        parse_mode="HTML",
        reply_markup=search_prompt_keyboard(f"host_cars_night:{night_id}"),
    )
    await call.answer()


@router.message(Car.title)
async def car_create_title(message: Message, state: FSMContext) -> None:
    title = message.text.strip()
    if len(title) < 2:
        await message.answer("Слишком короткое название. Попробуйте ещё раз:")
        return
    data = await state.get_data()
    night_id = data.get("night_id")
    if not night_id:
        await state.clear()
        await message.answer("Не удалось определить игротеку. Начните заново.")
        return

    await create_car(night_id, title, kind="newbie")
    await state.clear()
    night = await get_night(night_id)
    cars = await list_cars(night_id)

    lines = [
        f"✅ Вагон «{title}» создан.",
        "",
        f"🚃 <b>Вагоны (столы)</b>",
        f"📅 {fmt_date(night['date'])} • {night['location']}",
    ]
    if cars:
        lines.append("")
        for car in cars:
            cnt = await count_sessions_in_car(car["id"])
            lines.append(f"🚃 {car['title']} — игр: {cnt}")

    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=host_cars_menu(cars, night_id),
    )


@router.callback_query(F.data.startswith("host_car:"))
async def car_card(call: CallbackQuery) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return
    car_id = int(call.data.split(":")[1])
    await _show_car_card(call, car_id)


async def _show_car_card(call: CallbackQuery, car_id: int) -> None:
    car = await get_car(car_id)
    if not car:
        await call.answer("Вагон не найден", show_alert=True)
        return
    night = await get_night(car["game_night_id"])
    sessions = await list_sessions_in_car(car_id)

    lines = [
        f"🚃 <b>{car['title']}</b>",
        f"📅 {fmt_date(night['date'])} • {night['location']}",
        f"Игр: {len(sessions)}",
    ]
    if sessions:
        lines.append("")
        for s in sessions:
            lines.append(
                f"• {s['time_start']}–{s['time_end'] or '?'} — {s['game_title']}"
            )

    await safe_edit(
        call.message,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=host_car_card(car_id, has_sessions=bool(sessions)),
    )


@router.callback_query(F.data.startswith("host_car_attach:"))
async def car_attach_start(call: CallbackQuery) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return
    car_id = int(call.data.split(":")[1])
    car = await get_car(car_id)
    if not car:
        await call.answer("Вагон не найден", show_alert=True)
        return
    sessions = await list_sessions_without_car(car["game_night_id"])
    if not sessions:
        await call.answer("Нет игр без вагона", show_alert=True)
        return
    await safe_edit(
        call.message,
        f"🚃 <b>Привязать игру к «{car['title']}»</b>\n\n"
        f"Выберите игру:",
        parse_mode="HTML",
        reply_markup=car_sessions_picker(car_id, sessions),
    )
    await call.answer()


@router.callback_query(F.data.startswith("host_car_pick_session:"))
async def car_pick_session(call: CallbackQuery) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return
    parts = call.data.split(":")
    car_id = int(parts[1])
    session_id = int(parts[2])
    car = await get_car(car_id)
    if not car:
        await call.answer("Вагон не найден", show_alert=True)
        return
    await assign_session_to_car(session_id, car_id)
    await call.answer("✅ Привязано")
    await _show_car_card(call, car_id)


@router.callback_query(F.data.startswith("host_car_detach_all:"))
async def car_detach_all(call: CallbackQuery) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return
    car_id = int(call.data.split(":")[1])
    car = await get_car(car_id)
    if not car:
        await call.answer("Вагон не найден", show_alert=True)
        return
    from database.db import db
    await db.conn.execute(
        "UPDATE game_sessions SET car_id = NULL WHERE car_id = ?",
        (car_id,),
    )
    await db.conn.commit()
    await call.answer("🔓 Все игры отвязаны")
    await _show_car_card(call, car_id)


@router.callback_query(F.data.startswith("host_car_del:"))
async def car_delete_confirm(call: CallbackQuery) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return
    car_id = int(call.data.split(":")[1])
    car = await get_car(car_id)
    if not car:
        await call.answer("Вагон не найден", show_alert=True)
        return
    cnt = await count_sessions_in_car(car_id)
    warning = ""
    if cnt:
        warning = (
            f"\n\n⚠️ В вагоне {cnt} игр. Они станут «без вагона» "
            f"(не удалятся)."
        )
    await safe_edit(
        call.message,
        f"Удалить вагон «{car['title']}»?{warning}",
        parse_mode="HTML",
        reply_markup=confirm_delete_car(car_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("host_car_del_yes:"))
async def car_delete_yes(call: CallbackQuery) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return
    car_id = int(call.data.split(":")[1])
    car = await get_car(car_id)
    if not car:
        await call.answer("Вагон не найден", show_alert=True)
        return
    night_id = car["game_night_id"]
    await delete_car(car_id)
    await call.answer("🗑 Вагон удалён")
    await _show_cars_for_night(call, night_id)