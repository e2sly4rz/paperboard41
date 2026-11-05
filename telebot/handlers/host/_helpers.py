from database.queries import get_session_author
from utils import is_admin


async def can_manage_night(user_id: int, night: dict | None) -> bool:
    if night is None:
        return False
    if is_admin(user_id):
        return True
    return night["host_telegram_id"] == user_id


async def can_delete_session(user_id: int, session_id: int,
                             night: dict | None) -> bool:
    if night is None:
        return False
    if is_admin(user_id):
        return True
    if night["host_telegram_id"] == user_id:
        return True
    author_id = await get_session_author(session_id)
    return author_id is not None and author_id == user_id


def add_minutes(time_str: str, minutes: int) -> str:
    h, m = map(int, time_str.split(":"))
    total = h * 60 + m + minutes
    new_h = (total // 60) % 24
    new_m = total % 60
    return f"{new_h:02d}:{new_m:02d}"