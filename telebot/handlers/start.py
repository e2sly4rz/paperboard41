from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from config import ADMIN_ID
from database.queries import (
    ensure_user,
    set_user_level,
    get_user,
    approve_user,
    revoke_user,
    list_pending_users,
)
from keyboards.menus import main_menu

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    u = message.from_user
    await ensure_user(u.id, u.username, u.first_name, u.last_name)
    user = await get_user(u.id)

    # Админ — сразу видит меню
    if u.id == ADMIN_ID:
        is_host = bool(user and user["subscriber_level"] == "host")
        await message.answer(
            "👑 Вы администратор.\n\n"
            f"Ожидают одобрения: {len(await list_pending_users())} чел.\n"
            "Команды:\n"
            "/approve &lt;id&gt; — одобрить\n"
            "/revoke &lt;id&gt; — отозвать доступ\n"
            "/pending — список заявок\n"
            "/grant &lt;id&gt; host|provodnik|guest — выдать роль",
            reply_markup=main_menu(is_host),
        )
        return

    # Не одобрен — показываем статус заявки
    if not user["is_approved"]:
        await message.answer(
            "⏳ Заявка на доступ отправлена.\n\n"
            "Организатор увидит её и подтвердит доступ. "
            "Вы получите уведомление, когда доступ будет открыт.\n\n"
            f"Ваш ID: <code>{u.id}</code>"
        )
        return

    # Одобренный обычный пользователь
    is_host = user["subscriber_level"] == "host"
    await message.answer(
        f"Привет, {u.first_name}!\n\n"
        "Это бот клуба настольных игр. Здесь можно посмотреть расписание "
        "игротек и записаться на игры.",
        reply_markup=main_menu(is_host),
    )


@router.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery) -> None:
    user = await get_user(call.from_user.id)
    is_host = bool(user and user["subscriber_level"] == "host")
    await call.message.edit_text(
        "Главное меню:",
        reply_markup=main_menu(is_host),
    )
    await call.answer()


# ---------- Админ-команды ----------

@router.message(Command("pending"))
async def cmd_pending(message: Message) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    users = await list_pending_users()
    if not users:
        await message.answer("Заявок нет.")
        return
    lines = ["📋 Заявки на доступ:\n"]
    for u in users:
        name_parts = [u["first_name"] or "", u["last_name"] or ""]
        name = " ".join(p for p in name_parts if p).strip() or "Без имени"
        username = f" (@{u['username']})" if u["username"] else ""
        lines.append(f"• <code>{u['telegram_id']}</code> — {name}{username}")
    lines.append("\nОдобрить: /approve &lt;id&gt;")
    await message.answer("\n".join(lines))


@router.message(Command("approve"))
async def cmd_approve(message: Message) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /approve <telegram_id>")
        return
    target_id = int(parts[1])
    ok = await approve_user(target_id)
    if not ok:
        await message.answer(
            "Пользователь не найден в БД. "
            "Попросите его отправить /start боту."
        )
        return
    await message.answer(f"✅ Пользователь {target_id} одобрен.")
    # Уведомляем пользователя, если можем
    try:
        await message.bot.send_message(
            target_id,
            "✅ Доступ к боту клуба настольных игр открыт. "
            "Отправьте /start, чтобы начать.",
        )
    except Exception:
        # Пользователь мог не начинать диалог с ботом или заблокировал его
        pass


@router.message(Command("revoke"))
async def cmd_revoke(message: Message) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /revoke <telegram_id>")
        return
    target_id = int(parts[1])
    ok = await revoke_user(target_id)
    if not ok:
        await message.answer("Пользователь не найден.")
        return
    await message.answer(f"🚫 Доступ пользователя {target_id} отозван.")


@router.message(Command("grant"))
async def grant_role(message: Message) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer(
            "Использование: /grant <telegram_id> host|provodnik|guest"
        )
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("telegram_id должен быть числом.")
        return
    level = parts[2]
    if level not in ("host", "provodnik", "guest"):
        await message.answer("Уровень должен быть host, provodnik или guest.")
        return
    await set_user_level(target_id, level)
    await message.answer(f"Пользователю {target_id} установлен уровень {level}.")