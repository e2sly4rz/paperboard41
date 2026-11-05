from datetime import datetime

from config import ADMIN_ID
from database.queries import get_user


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


async def is_host(user_id: int) -> bool:
    user = await get_user(user_id)
    return bool(user and user["subscriber_level"] == "host")


async def is_host_or_admin(user_id: int) -> bool:
    return is_admin(user_id) or await is_host(user_id)


async def is_provodnik_or_higher(user_id: int) -> bool:
    user = await get_user(user_id)
    if not user:
        return False
    return user["subscriber_level"] in ("host", "provodnik")


def fmt_date(iso_date: str) -> str:
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return iso_date or "—"