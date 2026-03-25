from datetime import datetime
from zoneinfo import ZoneInfo


BUSINESS_TIMEZONE = ZoneInfo("Europe/Moscow")
BUSINESS_HOUR_START = 6
BUSINESS_HOUR_END = 23


def get_business_now() -> datetime:
    """Return current datetime in the business timezone."""
    return datetime.now(BUSINESS_TIMEZONE)


def is_business_hours(dt: datetime | None = None) -> bool:
    """
    Allow automated messages only from 06:00 inclusive to 23:00 exclusive.
    """
    current = dt.astimezone(BUSINESS_TIMEZONE) if dt else get_business_now()
    return BUSINESS_HOUR_START <= current.hour < BUSINESS_HOUR_END
