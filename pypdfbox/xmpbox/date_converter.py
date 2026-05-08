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
_PDF_LIKE_RE = re.compile(
    r"^(?P<year>\d{4})"
    r"(?:-?(?P<month>\d{2})"
    r"(?:-?(?P<day>\d{2})"
    r"(?:T?(?P<hour>\d{2})"
    r"(?::?(?P<minute>\d{2})"
    r"(?::?(?P<second>\d{2})?)?"
    r")?)?)?)?"
    r"(?P<tz>Z|[+-]\d{2}(?::?'?\d{2}'?)?)?$"
)


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

    match = _PDF_LIKE_RE.match(date)
    if match is None:
        raise OSError(f"Error: Invalid date format '{date}'")

    try:
        year = int(match.group("year"))
        if match.group("month") is not None:
            month = int(match.group("month"))
        if match.group("day") is not None:
            day = int(match.group("day"))
        if match.group("hour") is not None:
            hour = int(match.group("hour"))
        if match.group("minute") is not None:
            minute = int(match.group("minute"))
        if match.group("second") is not None:
            second = int(match.group("second"))

        tz_text = match.group("tz")
        tz: timezone | None = None
        if tz_text == "Z":
            tz = UTC
        elif tz_text is not None:
            offset_text = tz_text[1:].replace(":", "").replace("'", "")
            hours = int(offset_text[0:2])
            minutes = int(offset_text[2:4]) if len(offset_text) >= 4 else 0
            offset = timedelta(hours=hours, minutes=minutes)
            if tz_text[0] == "-":
                offset = -offset
            tz = timezone(offset)
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
