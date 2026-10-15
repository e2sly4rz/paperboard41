from datetime import datetime

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def _fmt_date(iso_date: str) -> str:
    """Преобразует ГГГГ-ММ-ДД в ДД.ММ.ГГГГ. Если формат не тот — возвращает как есть."""
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return iso_date or "—"


def main_menu(is_host: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Расписание", callback_data="schedule")
    kb.button(text="🎲 Мои записи", callback_data="my_games")
    if is_host:
        kb.button(text="🎩 Меню организатора", callback_data="host_menu")
    kb.adjust(1)
    return kb.as_markup()


def nights_list(nights: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for n in nights:
        kb.button(
            text=f"{_fmt_date(n['date'])} • {n['location']} "
                 f"({n['sessions_count']} игр)",
            callback_data=f"night:{n['id']}",
        )
    kb.button(text="⬅️ Назад", callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()


def sessions_list(night_id: int, sessions: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in sessions:
        marker = "🔒 " if s["is_subscriber_only"] else ""
        taken = s["max_slots"] - s["free_slots"]
        kb.button(
            text=f"{marker}{s['time_start']} — {s['title']} "
                 f"({taken}/{s['max_slots']})",
            callback_data=f"session:{s['id']}",
        )
    kb.button(text="⬅️ К расписанию", callback_data="schedule")
    kb.adjust(1)
    return kb.as_markup()


def session_card(session_id: int,
                 can_register: bool,
                 show_participants: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if can_register:
        kb.button(text="✅ Записаться", callback_data=f"reg:{session_id}")
    if show_participants:
        kb.button(text="👥 Участники", callback_data=f"participants:{session_id}")
    kb.button(text="⬅️ Назад", callback_data="schedule")
    kb.adjust(1)
    return kb.as_markup()


def participants_back(session_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ К игре", callback_data=f"session:{session_id}")
    kb.adjust(1)
    return kb.as_markup()


def my_games_list(regs: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for r in regs:
        kb.button(
            text=f"❌ {_fmt_date(r['date'])} {r['time_start']} — {r['title']}",
            callback_data=f"cancel:{r['reg_id']}",
        )
    kb.button(text="⬅️ Назад", callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()


def games_picker(games: list[dict],
                 prefix: str = "pickgame") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for g in games:
        kb.button(text=g["title"], callback_data=f"{prefix}:{g['id']}")
    kb.button(text="✅ Завершить создание", callback_data="host_finish")
    kb.button(text="❌ Отмена", callback_data="host_cancel")
    kb.adjust(1)
    return kb.as_markup()


def confirm_session() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить ещё игру", callback_data="host_add_more")
    kb.button(text="✅ Завершить создание", callback_data="host_finish")
    kb.button(text="❌ Отмена", callback_data="host_cancel")
    kb.adjust(1)
    return kb.as_markup()

def host_menu() -> InlineKeyboardMarkup:
    """Меню хоста: создать новую или управлять существующими."""
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Создать игротеку", callback_data="host_create")
    kb.button(text="✏️ Мои игротеки", callback_data="host_manage_list")
    kb.button(text="⬅️ Назад", callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()


def host_nights_list(nights: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for n in nights:
        kb.button(
            text=f"{_fmt_date(n['date'])} • {n['location']} "
                 f"({n['sessions_count']} игр, {n['total_taken']} записей)",
            callback_data=f"hn:{n['id']}",
        )
    kb.button(text="⬅️ Назад", callback_data="host_menu")
    kb.adjust(1)
    return kb.as_markup()


def host_night_card(night_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="👥 Все участники", callback_data=f"hn_part:{night_id}")
    kb.button(text="📅 Изменить дату", callback_data=f"hn_date:{night_id}")
    kb.button(text="📍 Изменить место", callback_data=f"hn_loc:{night_id}")
    kb.button(text="🎲 Управление играми", callback_data=f"hn_sessions:{night_id}")
    kb.button(text="🗑 Удалить игротеку", callback_data=f"hn_del:{night_id}")
    kb.button(text="⬅️ К списку", callback_data="host_manage_list")
    kb.adjust(1)
    return kb.as_markup()


def night_participants_back(night_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ К игротеке", callback_data=f"hn:{night_id}")
    kb.adjust(1)
    return kb.as_markup()


def host_sessions_list(night_id: int, sessions: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in sessions:
        kb.button(
            text=f"🗑 {s['time_start']} — {s['game_title']} "
                 f"({s['slots_taken']}/{s['max_slots']})",
            callback_data=f"hs_del:{s['id']}",
        )
    kb.button(text="⬅️ К игротеке", callback_data=f"hn:{night_id}")
    kb.adjust(1)
    return kb.as_markup()


def confirm_delete_night(night_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Да, удалить", callback_data=f"hn_del_yes:{night_id}")
    kb.button(text="⬅️ Отмена", callback_data=f"hn:{night_id}")
    kb.adjust(1)
    return kb.as_markup()


def confirm_delete_session(session_id: int, night_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Да, удалить", callback_data=f"hs_del_yes:{session_id}")
    kb.button(text="⬅️ Отмена", callback_data=f"hn_sessions:{night_id}")
    kb.adjust(1)
    return kb.as_markup()


def cancel_edit(night_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data=f"hn:{night_id}")
    kb.adjust(1)
    return kb.as_markup()