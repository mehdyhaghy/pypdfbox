"""
ISO 8601 / PDF date string conversion utilities.

Ported from ``org.apache.xmpbox.DateConverter``. Upstream is a final
package-level utility class with two static methods, ``toCalendar(String)`` and
``toISO8601(Calendar [, boolean])``. The Python port exposes them as both
module-level functions and ``DateConverter`` classmethods so existing call
sites that use ``DateConverter.to_calendar(...)`` (mirroring the upstream
``DateConverter.toCalendar(...)`` shape) keep working.

Upstream stores moments in time as ``java.util.Calendar``; the Python port
returns timezone-aware :class:`datetime.datetime` instances (the closest
stdlib equivalent of ``Calendar``).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone

# Mirrors upstream's regex check that distinguishes a leading-ISO-style date
# (``YYYY-MM-DDT...``) from the ``D:YYYYMMDD...`` PDF dictionary form.
_ISO_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T.*")


def _from_iso8601(date_string: str) -> datetime:
    """Mirror of upstream private ``fromISO8601``.

    Tries to parse a zoned ISO 8601 string first; falls back to a naive
    ``ISO_LOCAL_DATE_TIME`` and attaches UTC, matching upstream behaviour.
    """
    cleaned = date_string.strip()
    iso = cleaned
    if iso.endswith("Z"):
        iso = iso[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError as exc:
        raise OSError(str(exc)) from exc
    if parsed.tzinfo is None:
        # upstream falls back to LocalDateTime + UTC zone
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def to_calendar(date_string: str | None) -> datetime | None:
    """Convert a date string into a timezone-aware :class:`datetime.datetime`.

    Mirrors ``DateConverter.toCalendar(String)``. Accepts:

    * ``None`` or empty / whitespace-only strings — returns ``None``.
    * ISO 8601 strings (``YYYY-MM-DDT...``).
    * PDF date strings (``D:YYYYMMDDhhmmss[+|-]hh'mm'``).
    * Partial dates (``YYYY``, ``YYYY-MM``, ``YYYY-MM-DD``).

    Raises :class:`OSError` (Python equivalent of Java ``IOException``) when
    the input cannot be parsed.
    """
    if date_string is None:
        return None
    date = date_string.strip()
    if not date:
        return None

    # Default values match upstream's locals.
    month = 1
    day = 1
    hour = 0
    minute = 0
    second = 0

    if _ISO_PREFIX_RE.match(date):
        return _from_iso8601(date)

    if date.startswith("D:"):
        date = date[2:]
    pos_of_t = date.find("T")
    if pos_of_t != 10 and pos_of_t != -1:
        raise OSError(f"Error converting date:{date}")

    date = re.sub(r"[-:T]", "", date)

    if len(date) < 4:
        raise OSError(f"Error: Invalid date format '{date}'")

    try:
        year = int(date[0:4])
        if len(date) >= 6:
            month = int(date[4:6])
        if len(date) >= 8:
            day = int(date[6:8])
        if len(date) >= 10:
            hour = int(date[8:10])
        if len(date) >= 12:
            minute = int(date[10:12])

        time_zone_pos = 12
        if (
            len(date) == 14
            or len(date) - 12 > 5
            or (len(date) - 12 == 3 and date.endswith("Z"))
        ):
            second = int(date[12:14])
            time_zone_pos = 14

        tz: timezone | None = None
        if len(date) >= (time_zone_pos + 1):
            sign = date[time_zone_pos]
            if sign == "Z":
                tz = UTC
            else:
                hours = 0
                minutes = 0
                if len(date) >= (time_zone_pos + 3):
                    if sign == "+":
                        hours = int(date[time_zone_pos + 1 : time_zone_pos + 3])
                    else:
                        hours = -int(date[time_zone_pos : time_zone_pos + 2])
                if sign == "+":
                    if len(date) >= (time_zone_pos + 5):
                        minutes = int(
                            date[time_zone_pos + 3 : time_zone_pos + 5]
                        )
                else:
                    if len(date) >= (time_zone_pos + 4):
                        minutes = int(
                            date[time_zone_pos + 2 : time_zone_pos + 4]
                        )
                # Upstream: hours * 3600s + minutes * 60s (additive, no
                # sign-mirroring on minutes — matches Java SimpleTimeZone arg).
                offset_seconds = hours * 3600 + minutes * 60
                tz = timezone(timedelta(seconds=offset_seconds))
    except ValueError as exc:
        raise OSError(f"Error converting date:{date}") from exc

    if tz is None:
        # upstream uses local default GregorianCalendar; for parity with the
        # ISO fallback (which attaches UTC) we attach UTC here too. Callers
        # that need local time can re-zone the result.
        tz = UTC

    return datetime(year, month, day, hour, minute, second, tzinfo=tz)


def to_iso8601(value: datetime, print_millis: bool = False) -> str:
    """Format a :class:`datetime.datetime` as an ISO 8601 string.

    Mirrors ``DateConverter.toISO8601(Calendar [, boolean])``. Naive
    datetimes are treated as UTC, matching the upstream ``GregorianCalendar``
    default zone after ``fromISO8601`` fallback.
    """
    cal = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    out = (
        f"{cal.year:04d}-{cal.month:02d}-{cal.day:02d}T"
        f"{cal.hour:02d}:{cal.minute:02d}:{cal.second:02d}"
    )
    if print_millis:
        millis = cal.microsecond // 1000
        out += f".{millis:03d}"
    offset = cal.utcoffset() or timedelta(0)
    total_minutes = int(offset.total_seconds() // 60)
    sign = "-" if total_minutes < 0 else "+"
    total_minutes = abs(total_minutes)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    out += f"{sign}{hours:02d}:{minutes:02d}"
    return out


class DateConverter:
    """
    Port of ``org.apache.xmpbox.DateConverter``.

    Upstream is a ``final`` class with a private constructor and only static
    methods. The Python port keeps the same shape: do not instantiate; call
    :meth:`to_calendar` / :meth:`to_iso8601` as classmethods.
    """

    def __init__(self) -> None:
        # Upstream marks the constructor private so the class can never be
        # instantiated; mirror that here.
        raise TypeError("DateConverter is a utility class and cannot be instantiated")

    @staticmethod
    def to_calendar(date_string: str | None) -> datetime | None:
        return to_calendar(date_string)

    @staticmethod
    def to_iso8601(value: datetime, print_millis: bool = False) -> str:
        return to_iso8601(value, print_millis)
