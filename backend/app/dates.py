from datetime import date, datetime
from zoneinfo import ZoneInfo

MSK_TZ = ZoneInfo("Europe/Moscow")


def get_current_moscow_date() -> date:
    return datetime.now(MSK_TZ).date()
