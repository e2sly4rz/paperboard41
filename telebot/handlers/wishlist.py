from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.queries import (
    get_user,
    search_games,
    count_active_wishlist,
    add_wishlist_item,
    list_user_wishlist,
    remove_wishlist_item,
    close_wishlist_item,
    list_all_wishlists,
    wishlist_summary,
    WISHLIST_LIMIT,
)
from keyboards.menus import (
    main_menu,
    wishlist_view,
    wishlist_search_results,
    search_prompt_keyboard,
    host_wishlists,
    close_reason_picker,
)
from states.states import Wishlist
from utils import is_admin, is_host_or_admin, safe_edit
from notifications import notify_wishlist_closed

router = Router()


async def _is_wishlist_allowed(user_id: int) -> bool:
    """Проводник, хост или админ."""
    if is_admin(user_id):
        return True
    user = await get_user(user_id)
    return bool(user and user["subscriber_level"] in ("provodnik", "host"))


def _wishlist_text(items: list[dict], count: int) -> str:
    lines = [f"⭐ <b>Мой вишлист</b> ({count} из {WISHLIST_LIMIT})"]
    if not items:
        lines.append("\n<i>Пока пусто. Добавьте игру из каталога.</i>")
    else:
        for i, item in enumerate(items, 1):
            lines.append(f"{i}. {item['title']}")
    return "\n".join(lines)


# ---------- Проводник/хост: свой вишлист ----------

@router.callback_query(F.data == "wishlist")
async def show_wishlist(call: CallbackQuery) -> None:
    if not await _is_wishlist_allowed(call.from_user.id):
        await call.answer("Доступно с уровня Проводник", show_alert=True)
        return

    items = await list_user_wishlist(call.from_user.id)
    count = len(items)
    is_full = count >= WISHLIST_LIMIT

    await safe_edit(
        call.message,
        _wishlist_text(items, count),
        parse_mode="HTML",
        reply_markup=wishlist_view(items, is_full),
    )
    await call.answer()


@router.callback_query(F.data == "wishlist_add")
async def wishlist_add_start(call: CallbackQuery, state: FSMContext) -> None:
    if not await _is_wishlist_allowed(call.from_user.id):
        await call.answer("Доступно с уровня Проводник", show_alert=True)
        return

    if await count_active_wishlist(call.from_user.id) >= WISHLIST_LIMIT:
        await call.answer(
            f"Вишлист полон ({WISHLIST_LIMIT} из {WISHLIST_LIMIT}). "
            f"Удалите что-то, чтобы добавить новое.",
            show_alert=True,
        )
        return

    await state.set_state(Wishlist.searching_game)
    await safe_edit(
        call.message,
        "🔍 <b>Поиск игры</b>\n\n"
        "Введите название или его часть:",
        parse_mode="HTML",
        reply_markup=search_prompt_keyboard("wishlist"),
    )
    await call.answer()


@router.message(Wishlist.searching_game)
async def wishlist_search(message: Message, state: FSMContext) -> None:
    query = message.text.strip()
    if len(query) < 2:
        await message.answer("Введите хотя бы 2 символа:")
        return

    games = await search_games(query, limit=10)
    if not games:
        await message.answer(
            f"🔍 По запросу «{query}» ничего не найдено.\n\n"
            f"Попробуйте другое название:",
            reply_markup=search_prompt_keyboard("wishlist"),
        )
        return

    await state.set_state(Wishlist.picking_game)
    await message.answer(
        f"🔍 Найдено: {len(games)}\n\nВыберите игру:",
        reply_markup=wishlist_search_results(games),
    )


@router.callback_query(Wishlist.picking_game, F.data.startswith("wishlist_pick:"))
async def wishlist_pick(call: CallbackQuery, state: FSMContext) -> None:
    game_id = int(call.data.split(":")[1])
    item_id = await add_wishlist_item(call.from_user.id, game_id)
    await state.clear()

    if item_id is None:
        await call.answer(
            "Не удалось добавить: вишлист полон или игра уже есть.",
            show_alert=True,
        )
    else:
        await call.answer("✅ Добавлено в вишлист")

    items = await list_user_wishlist(call.from_user.id)
    count = len(items)
    is_full = count >= WISHLIST_LIMIT

    await safe_edit(
        call.message,
        _wishlist_text(items, count),
        parse_mode="HTML",
        reply_markup=wishlist_view(items, is_full),
    )


@router.callback_query(F.data.startswith("wishlist_remove:"))
async def wishlist_remove(call: CallbackQuery) -> None:
    item_id = int(call.data.split(":")[1])
    ok = await remove_wishlist_item(item_id, call.from_user.id)
    if not ok:
        await call.answer("Не удалось удалить", show_alert=True)
        return

    await call.answer("🗑 Удалено")

    items = await list_user_wishlist(call.from_user.id)
    count = len(items)
    is_full = count >= WISHLIST_LIMIT

    await safe_edit(
        call.message,
        _wishlist_text(items, count),
        parse_mode="HTML",
        reply_markup=wishlist_view(items, is_full),
    )


# ---------- Проводник: сводка ----------

@router.callback_query(F.data == "wishlist_summary")
async def show_wishlist_summary(call: CallbackQuery) -> None:
    if not await _is_wishlist_allowed(call.from_user.id):
        await call.answer("Доступно с уровня Проводник", show_alert=True)
        return

    summary = await wishlist_summary()
    if not summary:
        text = "⭐ <b>Чего хотят проводники</b>\n\n<i>Пока пусто.</i>"
    else:
        lines = ["⭐ <b>Чего хотят проводники</b>\n"]
        for s in summary:
            lines.append(f"• {s['title']} — {s['cnt']} чел. ({s['names']})")
        text = "\n".join(lines)

    if len(text) > 3900:
        text = text[:3890] + "\n\n<i>…список обрезан</i>"

    user = await get_user(call.from_user.id)
    is_host_user = await is_host_or_admin(call.from_user.id)
    is_provodnik = bool(user and user["subscriber_level"] in ("provodnik", "host"))

    await safe_edit(
        call.message,
        text,
        parse_mode="HTML",
        reply_markup=main_menu(is_host_user, call.from_user.id,
                               is_provodnik=is_provodnik),
    )
    await call.answer()


# ---------- Хост: вишлисты проводников ----------

@router.callback_query(F.data == "host_wishlists")
async def host_wishlists_view(call: CallbackQuery) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return

    items = await list_all_wishlists()
    if not items:
        await safe_edit(
            call.message,
            "⭐ <b>Вишлисты проводников</b>\n\n"
            "<i>Пока никто ничего не добавил.</i>",
            parse_mode="HTML",
            reply_markup=host_wishlists([]),
        )
        await call.answer()
        return

    lines = ["⭐ <b>Вишлисты проводников</b>\n"]
    current_user = None
    for item in items:
        uid = item["user_id"]
        if uid != current_user:
            name = item["first_name"] or "Без имени"
            username = f" (@{item['username']})" if item["username"] else ""
            lines.append(f"\n👤 <b>{name}</b>{username}:")
            current_user = uid
        lines.append(f"  • {item['title']}")

    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3890] + "\n\n<i>…список обрезан</i>"

    await safe_edit(
        call.message,
        text,
        parse_mode="HTML",
        reply_markup=host_wishlists(items),
    )
    await call.answer()


@router.callback_query(F.data.startswith("host_wishlist_close:"))
async def host_wishlist_close_start(call: CallbackQuery) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return

    item_id = int(call.data.split(":")[1])
    await safe_edit(
        call.message,
        "Закрыть пункт вишлиста?\n\nВыберите причину:",
        reply_markup=close_reason_picker(item_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("wishlist_close:"))
async def host_wishlist_close(call: CallbackQuery) -> None:
    if not await is_host_or_admin(call.from_user.id):
        await call.answer("Только для организаторов", show_alert=True)
        return

    parts = call.data.split(":")
    item_id = int(parts[1])
    reason = parts[2]

    result = await close_wishlist_item(item_id, call.from_user.id, reason)
    if not result:
        await call.answer("Пункт уже закрыт", show_alert=True)
        return

    await call.answer("✅ Закрыто")

    await notify_wishlist_closed(
        call.bot,
        result["user_id"],
        game_title=result["game_title"],
        reason=result["reason"],
    )

    items = await list_all_wishlists()
    if not items:
        await safe_edit(
            call.message,
            "⭐ <b>Вишлисты проводников</b>\n\n"
            "<i>Пока никто ничего не добавил.</i>",
            parse_mode="HTML",
            reply_markup=host_wishlists([]),
        )
        return

    lines = ["⭐ <b>Вишлисты проводников</b>\n"]
    current_user = None
    for item in items:
        uid = item["user_id"]
        if uid != current_user:
            name = item["first_name"] or "Без имени"
            username = f" (@{item['username']})" if item["username"] else ""
            lines.append(f"\n👤 <b>{name}</b>{username}:")
            current_user = uid
        lines.append(f"  • {item['title']}")

    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3890] + "\n\n<i>…список обрезан</i>"

    await safe_edit(
        call.message,
        text,
        parse_mode="HTML",
        reply_markup=host_wishlists(items),
    )