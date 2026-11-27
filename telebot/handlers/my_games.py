from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.queries import (
    get_user_registrations_with_players,
    get_user,
)
from keyboards.menus import main_menu
from utils import is_host_or_admin, fmt_date, safe_edit

router = Router()


@router.callback_query(F.data == "my_games")
async def show_my_games(call: CallbackQuery) -> None:
    regs = await get_user_registrations_with_players(call.from_user.id)
    is_host_user = await is_host_or_admin(call.from_user.id)
    user = await get_user(call.from_user.id)
    is_provodnik = bool(user and user["subscriber_level"] in ("provodnik", "host"))

    if not regs:
        await safe_edit(
            call.message,
            "У вас пока нет активных записей.",
            reply_markup=main_menu(is_host_user, call.from_user.id,
                                   is_provodnik=is_provodnik),
        )
        await call.answer()
        return

    # группировка по (дата, место)
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in regs:
        key = (r["date"], r["location"])
        groups.setdefault(key, []).append(r)

    lines = ["🎲 <b>Мои записи</b>"]
    for (date, location), items in groups.items():
        lines.append("")
        lines.append(f"📅 <b>{fmt_date(date)}</b> · 📍 {location}")

        for r in items:
            time_range = f"{r['time_start']}–{r['time_end'] or '?'}"
            lines.append(f"\n🕐 {time_range} · {r['title']}")

            players = r.get("players", [])
            if players:
                player_lines = []
                for p in players:
                    name = p.get("first_name") or "Без имени"
                    username = f" (@{p['username']})" if p.get("username") else ""
                    if p.get("telegram_id") == call.from_user.id:
                        player_lines.append("  • Вы")
                    else:
                        player_lines.append(f"  • {name}{username}")
                lines.append("👥 Записаны:\n" + "\n".join(player_lines))
            else:
                lines.append("👥 Записаны: —")

    text = "\n".join(lines).strip()
    if len(text) > 3900:
        text = text[:3890] + "\n\n<i>…список обрезан</i>"

    await safe_edit(
        call.message,
        text,
        parse_mode="HTML",
        reply_markup=main_menu(is_host_user, call.from_user.id,
                               is_provodnik=is_provodnik),
    )
    await call.answer()


@router.callback_query(F.data.startswith("cancel:"))
async def cancel(call: CallbackQuery) -> None:
    reg_id = int(call.data.split(":")[1])
    cancelled = await cancel_registration(reg_id, call.from_user.id)

    if not cancelled:
        await call.answer("Не удалось отменить запись", show_alert=True)
        return

    await call.answer("Запись отменена", show_alert=True)

    # Уведомление автору игры об отмене записи
    user = await get_user(call.from_user.id)
    player_name = "Без имени"
    if user:
        name_parts = [user["first_name"] or "", user["last_name"] or ""]
        player_name = " ".join(p for p in name_parts if p).strip() or "Без имени"
        if user.get("username"):
            player_name += f" (@{user['username']})"

    await notify_game_author_cancellation(
        call.bot,
        cancelled["session_id"],
        call.from_user.id,
        game_title=cancelled["game_title"],
        date_str=cancelled["date"],
        location=cancelled["location"],
        time_start=cancelled["time_start"],
        time_end=cancelled["time_end"],
        slots_taken=cancelled["slots_taken"],
        max_slots=cancelled["max_slots"],
        player_name=player_name,
    )

    # Обновляем экран «Мои записи»
    is_host_user = await is_host_or_admin(call.from_user.id)
    user = await get_user(call.from_user.id)
    is_provodnik = bool(user and user["subscriber_level"] in ("provodnik", "host"))
    regs = await list_user_registrations(call.from_user.id)
    if not regs:
        await safe_edit(
            call.message,
            "У вас пока нет активных записей.",
            reply_markup=main_menu(is_host_user, call.from_user.id,
                                   is_provodnik=is_provodnik),
        )
    else:
        await safe_edit(
            call.message,
            "Ваши записи (нажмите, чтобы отменить):",
            reply_markup=my_games_list(regs),
        )