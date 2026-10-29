"""Utilitas waktu. Semua jadwal memakai WIB (UTC+7, tanpa DST)."""
from datetime import datetime, timedelta, timezone

WIB = timezone(timedelta(hours=7), "WIB")
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def now():
    return datetime.now(WIB)


def iso(dt):
    return dt.isoformat(timespec="seconds") if dt else ""


def parse(value):
    """Parse ISO string; string tanpa zona dianggap WIB."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=WIB)
    return dt


def fmt_dt(value):
    dt = value if isinstance(value, datetime) else parse(value)
    if not dt:
        return "-"
    return "%d %s %d %02d:%02d WIB" % (dt.day, _MONTHS[dt.month - 1], dt.year, dt.hour, dt.minute)


def fmt_date(value):
    dt = value if isinstance(value, datetime) else parse(value)
    if not dt:
        return "-"
    return "%d %s %d" % (dt.day, _MONTHS[dt.month - 1], dt.year)


def hhmm(value, fallback="18:30"):
    try:
        hour, minute = str(value).strip().split(":")
        hour, minute = int(hour), int(minute)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
    except (ValueError, AttributeError):
        pass
    hour, minute = fallback.split(":")
    return int(hour), int(minute)


def today_str(at=None):
    return (at or now()).strftime("%Y-%m-%d")
