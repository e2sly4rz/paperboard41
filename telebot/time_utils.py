from datetime import datetime
from zoneinfo import ZoneInfo

from config import CLUB_TIMEZONE


_TZ = ZoneInfo(CLUB_TIMEZONE)


def session_datetime(iso_date: str, time_str: str) -> datetime | None:
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d")
        t = datetime.strptime(time_str, "%H:%M")
        naive = d.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
        return naive.replace(tzinfo=_TZ)
    except (ValueError, TypeError):
        return None


def club_now() -> datetime:
    return datetime.now(_TZ)