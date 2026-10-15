from config import ADMIN_ID


def is_admin(user_id: int) -> bool:
    """True, если пользователь — администратор клуба."""
    return user_id == ADMIN_ID