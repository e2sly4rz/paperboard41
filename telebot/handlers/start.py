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
from keyboards.menus import main_menu, admin_help_back
from utils import is_admin

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    u = message.from_user
    await ensure_user(u.id, u.username, u.first_name, u.last_name)
    user = await get_user(u.id)

    if is_admin(u.id):
        pending = await list_pending_users()
        is_host = bool(user and user["subscriber_level"] == "host") or True
        await message.answer(
            f"👑 Вы администратор.\n\n"
            f"Заявок на доступ: {len(pending)}",
            reply_markup=main_menu(is_host, u.id),
        )
        return

    if not user["is_approved"]:
        await message.answer(
            "⏳ Заявка на доступ отправлена.\n\n"
            "Организатор увидит её и подтвердит доступ.\n\n"
            f"Ваш ID: <code>{u.id}</code>"
        )
        try:
            name = f"{u.first_name or ''} {u.last_name or ''}".strip() or "Без имени"
            username = f" (@{u.username})" if u.username else ""
            await message.bot.send_message(
                ADMIN_ID,
                f"🔔 Новая заявка на доступ:\n"
                f"• <code>{u.id}</code> — {name}{username}\n\n"
                f"Одобрить: /approve {u.id}",
            )
        except Exception:
            pass
        return

    is_host = user["subscriber_level"] == "host"
    await message.answer(
        f"Привет, {u.first_name}!\n\n"
        "Это бот клуба настольных игр. Здесь можно посмотреть расписание "
        "игротек и записаться на игры.",
        reply_markup=main_menu(is_host, u.id),
    )


@router.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery) -> None:
    user = await get_user(call.from_user.id)
    is_host = (
        bool(user and user["subscriber_level"] == "host")
        or is_admin(call.from_user.id)
    )
    await call.message.edit_text(
        "Главное меню:",
        reply_markup=main_menu(is_host, call.from_user.id),
    )
    await call.answer()


# ---------- Справка по командам ----------

ADMIN_HELP_TEXT = (
    "❓ <b>Справочник команд администратора</b>\n\n"

    "<b>Управление доступом</b>\n"
    "<code>/pending</code> — список заявок на доступ\n"
    "<code>/approve &lt;id&gt;</code> — одобрить пользователя\n"
    "<code>/revoke &lt;id&gt;</code> — отозвать доступ\n\n"

    "<b>Управление ролями</b>\n"
    "<code>/grant &lt;id&gt; host</code> — сделать организатором\n"
    "<code>/grant &lt;id&gt; provodnik</code> — выдать «Проводника»\n"
    "<code>/grant &lt;id&gt; guest</code> — снять привилегии\n\n"

    "<b>Прочее</b>\n"
    "<code>/start</code> — главное меню\n"
    "<code>/id</code> — узнать свой Telegram ID\n"
    "<code>/help</code> — эта справка\n\n"

    "💡 <i>ID пользователя можно узнать через @userinfobot "
    "или командой /id.</i>"
)


@router.callback_query(F.data == "admin_help")
async def admin_help(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Только для администратора", show_alert=True)
        return
    await call.message.edit_text(
        ADMIN_HELP_TEXT,
        parse_mode="HTML",
        reply_markup=admin_help_back(),
    )
    await call.answer()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("Команда доступна только администратору.")
        return
    await message.answer(
        ADMIN_HELP_TEXT,
        parse_mode="HTML",
        reply_markup=admin_help_back(),
    )


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(
        f"Ваш Telegram ID: <code>{message.from_user.id}</code>"
    )


# ---------- Админ-команды ----------

@router.message(Command("pending"))
async def cmd_pending(message: Message) -> None:
    if not is_admin(message.from_user.id):
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
    lines.append("\nОдобрить: <code>/approve &lt;id&gt;</code>")
    await message.answer("\n".join(lines))


@router.message(Command("approve"))
async def cmd_approve(message: Message) -> None:
    if not is_admin(message.from_user.id):
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
    try:
        await message.bot.send_message(
            target_id,
            "✅ Доступ к боту клуба настольных игр открыт. "
            "Отправьте /start, чтобы начать.",
        )
    except Exception:
        pass


@router.message(Command("revoke"))
async def cmd_revoke(message: Message) -> None:
    if not is_admin(message.from_user.id):
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
    if not is_admin(message.from_user.id):
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