"""Timezone-safe timestamps for storage, comparisons and browser display.

SQLite's CURRENT_TIMESTAMP is UTC.  The application therefore stores all newly
created timestamps in UTC as well and only converts them for people at the UI
boundary.  Older, offset-less SQLite values are treated as UTC for backwards
compatibility with CURRENT_TIMESTAMP.
"""

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


UTC = timezone.utc
TIMEZONE_NAME = os.getenv("APP_TIMEZONE", "Europe/Vienna")

try:
    APP_TIMEZONE = ZoneInfo(TIMEZONE_NAME)
except ZoneInfoNotFoundError:
    # Keep the service usable when a custom image has no zoneinfo database.
    APP_TIMEZONE = UTC
    TIMEZONE_NAME = "UTC"


def utc_now():
    """Return an aware UTC timestamp suitable for SQLite storage."""
    return datetime.now(UTC)


def parse_stored_datetime(value):
    """Parse a legacy or ISO timestamp and normalize it to an aware instant."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            for format_string in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    parsed = datetime.strptime(text, format_string)
                    break
                except ValueError:
                    continue
            else:
                return None

    # SQLite CURRENT_TIMESTAMP and old application values had no offset. The
    # database default has always been UTC, so retain that documented meaning.
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def format_local_datetime(value):
    """Format a stored timestamp in the configured local timezone."""
    parsed = parse_stored_datetime(value)
    if parsed is None:
        return value
    return parsed.astimezone(APP_TIMEZONE).strftime("%d.%m.%Y, %H:%M:%S %Z")
