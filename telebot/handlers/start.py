from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_ID
from database.queries import (
    ensure_user,
    set_user_level,
    get_user,
    approve_user,
    revoke_user,
    list_pending_users,
    list_all_users_grouped,
)
from keyboards.menus import main_menu, admin_help_back
from utils import is_admin, safe_edit

router = Router()

CLUB_NAME = "Картонный Экспресс"


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    u = message.from_user
    await ensure_user(u.id, u.username, u.first_name, u.last_name)
    user = await get_user(u.id)

    if is_admin(u.id):
        pending = await list_pending_users()
        await message.answer(
            f"👑 <b>Добро пожаловать, {u.first_name}!</b>\n\n"
            f"Вы администратор клуба «{CLUB_NAME}».\n"
            f"Заявок на доступ: <b>{len(pending)}</b>\n\n"
            f"Список команд — в разделе «❓ Справка по командам».",
            reply_markup=main_menu(True, u.id),
        )
        return

    if not user["is_approved"]:
        await message.answer(
            f"⏳ <b>Заявка отправлена</b>\n\n"
            f"Организатор клуба «{CLUB_NAME}» увидит её "
            f"и подтвердит доступ.\n\n"
            f"Ваш ID: <code>{u.id}</code>"
        )
        try:
            name = f"{u.first_name or ''} {u.last_name or ''}".strip() or "Без имени"
            username = f" (@{u.username})" if u.username else ""

            kb = InlineKeyboardBuilder()
            kb.button(
                text="✅ Одобрить",
                callback_data=f"approve_user:{u.id}",
            )
            kb.adjust(1)

            await message.bot.send_message(
                ADMIN_ID,
                f"🔔 <b>Новая заявка на доступ</b>\n"
                f"• <code>{u.id}</code> — {name}{username}\n\n"
                f"Одобрить: /approve {u.id}",
                reply_markup=kb.as_markup(),
            )
        except Exception:
            pass
        return

    is_host_user = user["subscriber_level"] == "host"

    if is_host_user:
        await message.answer(
            f"🎩 <b>Привет, {u.first_name}!</b>\n\n"
            f"Добро пожаловать в клуб «{CLUB_NAME}».\n\n"
            f"Вы — организатор. В разделе «🎩 Меню организатора» "
            f"можно создавать игротеки, управлять играми "
            f"и смотреть участников.\n\n"
            f"А в «📅 Расписание» — записаться на игры других хостов.",
            reply_markup=main_menu(True, u.id),
        )
        return

    if user["subscriber_level"] == "guest":
        await message.answer(
            f"🎫 <b>Привет, {u.first_name}!</b>\n\n"
            f"Это бот клуба настольных игр «{CLUB_NAME}».\n\n"
            f"Вы — гость клуба. Можете записываться на бесплатные "
            f"игротеки (отмечены 🆓 в расписании).\n\n"
            f"Для доступа к платным играм обратитесь к организатору.",
            reply_markup=main_menu(False, u.id),
        )
        return

    provodnik_note = ""
    if user["subscriber_level"] == "provodnik":
        provodnik_note = (
            "\n\n🔒 У вас подписка «Проводник» — "
            "доступны игры, отмеченные замком."
        )

    await message.answer(
        f"🎲 <b>Привет, {u.first_name}!</b>\n\n"
        f"Это бот клуба настольных игр «{CLUB_NAME}».\n\n"
        f"Здесь можно посмотреть расписание игротек "
        f"и записаться на игры.{provodnik_note}",
        reply_markup=main_menu(False, u.id),
    )


@router.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery) -> None:
    user = await get_user(call.from_user.id)
    is_host_user = (
        bool(user and user["subscriber_level"] == "host")
        or is_admin(call.from_user.id)
    )
    await safe_edit(
        call.message,
        "Главное меню:",
        reply_markup=main_menu(is_host_user, call.from_user.id),
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
    "<code>/grant &lt;id&gt; passenger</code> — сделать пассажиром\n"
    "<code>/grant &lt;id&gt; guest</code> — сделать гостем\n\n"

    "<b>Пользователи</b>\n"
    "<code>/users</code> — список всех пользователей с уровнями\n\n"

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
    await safe_edit(
        call.message,
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
            f"✅ <b>Доступ открыт!</b>\n\n"
            f"Организатор клуба «{CLUB_NAME}» подтвердил вашу заявку.\n"
            f"Отправьте /start, чтобы начать.",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("approve_user:"))
async def cb_approve_user(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Только для администратора", show_alert=True)
        return

    target_id = int(call.data.split(":")[1])
    ok = await approve_user(target_id)
    if not ok:
        await call.answer(
            "Пользователь не найден в БД. "
            "Попросите его отправить /start боту.",
            show_alert=True,
        )
        return

    await call.answer("✅ Пользователь одобрен")

    try:
        await call.message.edit_text(
            f"✅ <b>Заявка одобрена</b>\n\nID: <code>{target_id}</code>",
            parse_mode="HTML",
            reply_markup=None,
        )
    except Exception:
        pass

    try:
        await call.bot.send_message(
            target_id,
            f"✅ <b>Доступ открыт!</b>\n\n"
            f"Организатор клуба «{CLUB_NAME}» подтвердил вашу заявку.\n"
            f"Отправьте /start, чтобы начать.",
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
            "Использование: /grant <telegram_id> host|provodnik|passenger|guest"
        )
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("telegram_id должен быть числом.")
        return
    level = parts[2]
    if level not in ("host", "provodnik", "passenger", "guest"):
        await message.answer(
            "Уровень должен быть host, provodnik, passenger или guest."
        )
        return
    await set_user_level(target_id, level)
    await message.answer(f"Пользователю {target_id} установлен уровень {level}.")


@router.message(Command("users"))
async def cmd_users(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return

    groups = await list_all_users_grouped()

    def _fmt_user(u: dict) -> str:
        name_parts = [u["first_name"] or "", u["last_name"] or ""]
        name = " ".join(p for p in name_parts if p).strip() or "Без имени"
        username = f" (@{u['username']})" if u["username"] else ""
        return f"<code>{u['telegram_id']}</code> {name}{username}"

    lines = []
    total = sum(len(v) for v in groups.values())
    lines.append(f"👥 <b>Пользователи ({total})</b>\n")

    if groups["host"]:
        lines.append(f"🎩 <b>Хосты ({len(groups['host'])}):</b>")
        for u in groups["host"]:
            lines.append(f"• {_fmt_user(u)}")
        lines.append("")

    if groups["provodnik"]:
        lines.append(f"🔒 <b>Проводники ({len(groups['provodnik'])}):</b>")
        for u in groups["provodnik"]:
            lines.append(f"• {_fmt_user(u)}")
        lines.append("")

    if groups["passenger"]:
        lines.append(f"🎲 <b>Пассажиры ({len(groups['passenger'])}):</b>")
        for u in groups["passenger"]:
            lines.append(f"• {_fmt_user(u)}")
        lines.append("")

    if groups["guest"]:
        lines.append(f"🎫 <b>Гости ({len(groups['guest'])}):</b>")
        for u in groups["guest"]:
            lines.append(f"• {_fmt_user(u)}")
        lines.append("")

    if groups["pending"]:
        lines.append(f"⏳ <b>Ожидают одобрения ({len(groups['pending'])}):</b>")
        for u in groups["pending"]:
            lines.append(f"• {_fmt_user(u)}")
        lines.append("")
        lines.append("<i>Одобрить: /approve &lt;id&gt;</i>")

    text = "\n".join(lines).strip()
    if len(text) > 4000:
        text = text[:3990] + "\n\n<i>…список обрезан</i>"

    await message.answer(text, parse_mode="HTML")