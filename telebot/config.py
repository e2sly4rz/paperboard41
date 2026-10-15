import os
from dotenv import load_dotenv

CLUB_TIMEZONE = os.getenv("CLUB_TIMEZONE", "Europe/Moscow")

load_dotenv(override=False)


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Переменная окружения {name} не задана. "
            f"Проверьте файл .env или переменные окружения."
        )
    return value


BOT_TOKEN = _required("BOT_TOKEN")
ADMIN_ID = int(_required("ADMIN_ID"))
DB_PATH = os.getenv("DB_PATH", "club.db")