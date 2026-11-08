from datetime import datetime

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_ID


def _fmt_date(iso_date: str) -> str:
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return iso_date or "—"


def _short_title(title: str, max_len: int = 28) -> str:
    if len(title) <= max_len:
        return title
    return title[:max_len - 1].rstrip() + "…"


def main_menu(is_host: bool, user_id: int | None = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Расписание", callback_data="schedule")
    kb.button(text="🎲 Мои записи", callback_data="my_games")
    if is_host:
        kb.button(text="🎩 Меню организатора", callback_data="host_menu")
    if user_id is not None and user_id == ADMIN_ID:
        kb.button(text="❓ Справка по командам", callback_data="admin_help")
    kb.adjust(1)
    return kb.as_markup()


def admin_help_back() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ В главное меню", callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()


def nights_list(nights: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for n in nights:
        status = "🔓" if n.get("registration_open") else "🔒"
        kb.button(
            text=f"{status} {_fmt_date(n['date'])} • {n['location']} "
                 f"(игр: {n['sessions_count']})",
            callback_data=f"night:{n['id']}",
        )
    kb.button(text="⬅️ Назад", callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()


def sessions_list(night_id: int, sessions: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in sessions:
        taken = s["max_slots"] - s["free_slots"]
        total = s["max_slots"]

        if total <= 0:
            fill_pct = 0
        else:
            fill_pct = taken / total

        if fill_pct >= 1.0:
            marker = "⛔ "
        elif fill_pct >= 0.76:
            marker = "🔴 "
        elif fill_pct >= 0.51:
            marker = "🟠 "
        elif fill_pct >= 0.26:
            marker = "🟡 "
        else:
            marker = "🟢 "

        title = _short_title(s["title"])
        kb.button(
            text=f"{marker}{s['time_start']} · {title} · {taken}/{total}",
            callback_data=f"session:{s['id']}",
        )

    kb.button(text="⬅️ К расписанию", callback_data="schedule")
    kb.adjust(1)
    return kb.as_markup()


def session_card(session_id: int, night_id: int,
                 can_register: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if can_register:
        kb.button(text="✅ Записаться", callback_data=f"reg:{session_id}")
    kb.button(text="⬅️ Назад", callback_data=f"night:{night_id}")
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


# ---------- Меню организатора ----------

def host_menu_with_nights(nights: list[dict],
                          own_ids: set[int] | None = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Создать игротеку", callback_data="host_create")
    kb.button(text="📚 Добавить игру в каталог", callback_data="host_add_game")

    for n in nights:
        is_own = own_ids is None or n["id"] in own_ids
        prefix = "🎩" if is_own else "👀"
        kb.button(
            text=f"{prefix} {_fmt_date(n['date'])} • {n['location']} "
                 f"(игр: {n['sessions_count']}, записей: {n['total_taken']})",
            callback_data=f"hn:{n['id']}",
        )

    kb.button(text="⬅️ Назад", callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()


def host_menu_empty() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Создать игротеку", callback_data="host_create")
    kb.button(text="📚 Добавить игру в каталог", callback_data="host_add_game")
    kb.button(text="⬅️ Назад", callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()


# ---------- Клавиатуры хоста ----------

def host_night_card(night_id: int, is_owner: bool = True) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить игру", callback_data=f"hn_add:{night_id}")
    kb.button(text="🎲 Управление играми", callback_data=f"hn_sessions:{night_id}")
    if is_owner:
        kb.button(text="📅 Изменить дату", callback_data=f"hn_date:{night_id}")
        kb.button(text="📍 Изменить место", callback_data=f"hn_loc:{night_id}")
        kb.button(text="🗑 Удалить игротеку", callback_data=f"hn_del:{night_id}")
    kb.button(text="⬅️ К списку", callback_data="host_menu")
    kb.adjust(1)
    return kb.as_markup()


def host_night_card_with_poll(night_id: int, is_owner: bool = True,
                              has_active_poll: bool = False,
                              has_any_poll: bool = False,
                              registration_open: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить игру", callback_data=f"hn_add:{night_id}")
    kb.button(text="🎲 Управление играми", callback_data=f"hn_sessions:{night_id}")

    if is_owner and not registration_open:
        kb.button(text="🔓 Открыть запись",
                  callback_data=f"night_open:{night_id}")

    if has_active_poll:
        kb.button(text="📊 Результаты опроса",
                  callback_data=f"poll_results:{night_id}")
        kb.button(text="🔒 Закрыть опрос",
                  callback_data=f"poll_close:{night_id}")
    elif has_any_poll:
        kb.button(text="📊 Результаты опроса",
                  callback_data=f"poll_results:{night_id}")
        kb.button(text="📊 Создать новый опрос",
                  callback_data=f"poll_create:{night_id}")
    else:
        kb.button(text="📊 Создать опрос о времени",
                  callback_data=f"poll_create:{night_id}")

    if is_owner:
        kb.button(text="📅 Изменить дату", callback_data=f"hn_date:{night_id}")
        kb.button(text="📍 Изменить место", callback_data=f"hn_loc:{night_id}")
        kb.button(text="🗑 Удалить игротеку", callback_data=f"hn_del:{night_id}")
    kb.button(text="⬅️ К списку", callback_data="host_menu")
    kb.adjust(1)
    return kb.as_markup()


def host_sessions_list(night_id: int, sessions: list[dict],
                       can_delete_all: bool = False,
                       user_id: int | None = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in sessions:
        can_delete = (
            can_delete_all
            or (user_id is not None and s.get("created_by_user_id") == user_id)
        )
        prefix = "🗑" if can_delete else "•"
        callback = f"hs_del:{s['id']}" if can_delete else "noop"
        kb.button(
            text=f"{prefix} {s['time_start']} — {s['game_title']} "
                 f"({s['slots_taken']}/{s['max_slots']})",
            callback_data=callback,
        )
    kb.button(text="➕ Добавить игру", callback_data=f"hn_add:{night_id}")
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


# ---------- Поиск игр ----------

def games_search_results(night_id: int,
                         games: list[dict],
                         prefix: str = "addgame") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for g in games:
        kb.button(
            text=g["title"],
            callback_data=f"{prefix}:{g['id']}",
        )
    kb.button(text="🔍 Искать снова", callback_data=f"hn_add:{night_id}")
    kb.button(text="❌ Отмена", callback_data=f"hn_sessions:{night_id}")
    kb.adjust(1)
    return kb.as_markup()


def games_search_create(games: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for g in games:
        kb.button(
            text=g["title"],
            callback_data=f"pickgame:{g['id']}",
        )
    kb.button(text="🔍 Искать снова", callback_data="host_create_search_again")
    kb.button(text="❌ Отмена", callback_data="host_cancel")
    kb.adjust(1)
    return kb.as_markup()


def search_prompt_keyboard(cancel_callback: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data=cancel_callback)
    kb.adjust(1)
    return kb.as_markup()


# ---------- Ввод времени и мест ----------

def time_start_picker() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for hour in range(10, 24):
        t = f"{hour:02d}:00"
        kb.button(text=t, callback_data=f"pickstart:{t}")
    kb.button(text="✏️ Ввести вручную", callback_data="pickstart:manual")
    kb.adjust(4)
    return kb.as_markup()


def duration_picker(game: dict) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    dmin = game.get("duration_min") or 0
    dmax = game.get("duration_max") or 999

    for hours in range(1, 7):
        minutes = hours * 60
        label = f"{hours} ч"
        if dmin <= minutes <= dmax:
            label += " ✓"
        kb.button(text=label, callback_data=f"pickdur:{minutes}")

    kb.button(text="✏️ Ввести вручную", callback_data="pickdur:manual")
    kb.adjust(3)
    return kb.as_markup()


def slots_picker_autofill(game: dict,
                          default_slots: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    kb.button(
        text=f"✅ Поставить {default_slots} мест",
        callback_data=f"pickslots:{default_slots}",
    )

    min_p = game.get("min_players") or 1
    max_p = game.get("max_players") or default_slots
    for n in range(min_p, max_p + 1):
        if n == default_slots:
            continue
        kb.button(text=f"{n} мест", callback_data=f"pickslots:{n}")

    kb.button(text="✏️ Ввести вручную", callback_data="pickslots:manual")
    kb.adjust(1)
    return kb.as_markup()


# ---------- Опрос о времени ----------

def poll_time_grid(prefix: str, start_hour: int = 10,
                   end_hour: int = 23) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for hour in range(start_hour, end_hour + 1):
        t = f"{hour:02d}:00"
        kb.button(text=t, callback_data=f"{prefix}:{t}")
    kb.button(text="❌ Отмена", callback_data="back_main")
    kb.adjust(4)
    return kb.as_markup()


def poll_time_grid_after(prefix: str, after: str,
                         start_hour: int = 10,
                         end_hour: int = 23) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    after_h = int(after.split(":")[0])
    for hour in range(max(start_hour, after_h + 1), end_hour + 1):
        t = f"{hour:02d}:00"
        kb.button(text=t, callback_data=f"{prefix}:{t}")
    kb.button(text="❌ Отмена", callback_data="back_main")
    kb.adjust(4)
    return kb.as_markup()