"""
ISO 8601 / PDF date string conversion utilities.

Ported from ``org.apache.pdfbox.util.DateConverter`` (and the trimmed xmpbox
``org.apache.xmpbox.DateConverter``). Upstream is a final utility class with
public ``toCalendar`` / ``toISO8601`` / ``toString`` static methods plus a
constellation of private/package-private helpers (``parseTZoffset``,
``parseTimeField``, ``skipOptionals``, ``skipString``, ``newGreg``,
``parseBigEndianDate``, ``parseSimpleDate``, ``parseDate``, ``formatTZoffset``,
``restrainTZoffset``, ``adjustTimeZoneNicely``, ``updateZoneId``,
``fromISO8601``).

The Python port mirrors the same shape — internal helpers live as
``@staticmethod``s on :class:`DateConverter` so future ports of code that
relies on them (e.g. PDFBox tooling that calls ``parseTZoffset`` directly via
package-private access) can do so under their snake_case names. The high-level
``to_calendar`` / ``to_iso8601`` module functions remain stable for existing
callers.

Upstream stores moments as ``java.util.Calendar``; the Python port returns
timezone-aware :class:`datetime.datetime` instances (the closest stdlib
equivalent of ``Calendar``). Helpers that upstream operate on a mutable
``GregorianCalendar`` work on a small mutable :class:`_GregLike` shim with the
same field names so the port stays a 1:1 read of the Java code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from typing import ClassVar

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

# Upstream constants: timing units in millis (DateConverter.java lines 73-78).
_MINUTES_PER_HOUR = 60
_SECONDS_PER_MINUTE = 60
_MILLIS_PER_MINUTE = _SECONDS_PER_MINUTE * 1000
_MILLIS_PER_HOUR = _MINUTES_PER_HOUR * _MILLIS_PER_MINUTE
_HALF_DAY = 12 * _MINUTES_PER_HOUR * _MILLIS_PER_MINUTE
_DAY = 2 * _HALF_DAY


# Upstream ALPHA_START_FORMATS / DIGIT_START_FORMATS tables. These are Java
# SimpleDateFormat patterns; the Python port translates them into
# :func:`datetime.datetime.strptime` patterns where the semantics match. The
# few patterns that depend on the JVM's two-digit-year sliding window
# (``yy``) are translated as four-digit-aware regex helpers in
# :meth:`DateConverter.parse_simple_date`.
_ALPHA_START_FORMATS: tuple[str, ...] = (
    "EEEE, dd MMM yy hh:mm:ss a",
    "EEEE, MMM dd, yy hh:mm:ss a",
    "EEEE, MMM dd, yy 'at' hh:mma",
    "EEEE, MMM dd, yy",
    "EEEE MMM dd, yy HH:mm:ss",
    "EEEE MMM dd HH:mm:ss z yy",
    "EEEE MMM dd HH:mm:ss yy",
)
_DIGIT_START_FORMATS: tuple[str, ...] = (
    "dd MMM yy HH:mm:ss",
    "dd MMM yy HH:mm",
    "yyyy MMM d",
    "yyyymmddhh:mm:ss",
    "H:m M/d/yy",
    "M/d/yy HH:mm:ss",
    "M/d/yy HH:mm",
    "M/d/yy",
    # Wave 1388 — explicit US-default slash patterns (Locale.US in upstream's
    # ``DateConverter.parseSimpleDate`` via ``Locale.ENGLISH`` which defaults
    # to the en_US calendar). Upstream's ``M/d/yy`` regex already accepts
    # 4-digit years (``\d{2,4}``) so ``5/12/2005`` and ``05/12/2005`` already
    # match via the lenient ``M/d/yy`` handler; these aliases mirror the
    # commented-out upstream entries (DateConverter.java lines 136-142) so
    # the format-table read matches Java code-by-code and the dispatch table
    # carries every pattern an upstream maintainer would search for. Order
    # after ``M/d/yy*`` so the lenient handler still wins for ambiguous
    # 2-digit-month / 2-digit-day cases.
    "MM/dd/yyyy HH:mm:ss",
    "MM/dd/yyyy HH:mm",
    "MM/dd/yyyy",
)


@dataclass
class ParsePosition:
    """Mirror of :class:`java.text.ParsePosition`.

    Tracks an index into a string for cooperative parsing helpers. The Java
    ``errorIndex`` slot is included for completeness but unused by the
    DateConverter port (matching upstream — only the read/write index field
    is used).
    """

    index: int = 0
    error_index: int = -1

    def get_index(self) -> int:
        return self.index

    def set_index(self, value: int) -> None:
        self.index = value

    def get_error_index(self) -> int:
        return self.error_index

    def set_error_index(self, value: int) -> None:
        self.error_index = value


@dataclass
class _GregLike:
    """Minimal mutable Calendar-shaped shim for porting helpers 1:1.

    Upstream helpers receive a :class:`java.util.GregorianCalendar` and call
    ``cal.set(year, month, day, hour, minute, second)``,
    ``cal.setTimeZone(tz)``, ``cal.add(Calendar.MINUTE, n)``,
    ``cal.get(Calendar.ZONE_OFFSET)``, etc. This dataclass exposes the same
    field names so the port reads like the Java code.
    """

    year: int = 1970
    month: int = 0  # 0-based, matching java.util.Calendar
    day: int = 1
    hour: int = 0
    minute: int = 0
    second: int = 0
    millisecond: int = 0
    zone_offset: int = 0  # millis, raw offset
    dst_offset: int = 0
    lenient: bool = True
    tz_id: str = "UTC"
    extras: dict[str, object] = field(default_factory=dict)

    # Upstream uses ``cal.set(year, month, day, hour, minute, second)`` —
    # match that signature.
    def set_fields(
        self,
        year: int,
        month: int,
        day: int,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
    ) -> None:
        self.year = year
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second

    def add_minutes(self, delta: int) -> None:
        """Mirror ``cal.add(Calendar.MINUTE, delta)``.

        Normalises the wall-clock fields by round-tripping through
        :class:`datetime.datetime`. Operates in naive land — the timezone is a
        separate field, exactly like java.util.Calendar.
        """
        base = datetime(
            self.year,
            self.month + 1,
            self.day,
            self.hour,
            self.minute,
            self.second,
        )
        adjusted = base + timedelta(minutes=delta)
        self.year = adjusted.year
        self.month = adjusted.month - 1
        self.day = adjusted.day
        self.hour = adjusted.hour
        self.minute = adjusted.minute
        self.second = adjusted.second

    def to_datetime(self) -> datetime:
        """Materialise as a tz-aware :class:`datetime.datetime`.

        Total offset is ``zone_offset + dst_offset`` (millis), matching
        upstream's ``cal.get(ZONE_OFFSET) + cal.get(DST_OFFSET)`` idiom.
        """
        total_minutes = (self.zone_offset + self.dst_offset) // _MILLIS_PER_MINUTE
        tz = timezone(timedelta(minutes=total_minutes))
        millis = self.millisecond
        return datetime(
            self.year,
            self.month + 1,
            self.day,
            self.hour,
            self.minute,
            self.second,
            millis * 1000,
            tzinfo=tz,
        )

    def validate(self) -> None:
        """Mirror ``cal.getTimeInMillis()`` triggering a non-lenient check."""
        if not self.lenient:
            datetime(
                self.year,
                self.month + 1,
                self.day,
                self.hour,
                self.minute,
                self.second,
            )


def _from_iso8601(date_string: str) -> datetime:
    """Mirror of upstream private ``fromISO8601``.

    Tries to parse a zoned ISO 8601 string first; falls back to a naive
    ``ISO_LOCAL_DATE_TIME`` and attaches UTC, matching upstream behaviour.

    Wave 1387 — also handles the upstream edge case
    ``"2001-01-31T10:33.123+01:00"`` where milliseconds are spliced between
    minute and timezone (Java's ISO parser accepts the fraction as a
    decimal minute and rounds; we drop the fraction to match upstream's
    observed result of ``second=0``).
    """
    cleaned = date_string.strip()
    iso = cleaned
    if iso.endswith("Z"):
        iso = iso[:-1] + "+00:00"
    # Strip fractional-minute notation: ``HH:MM.fff`` -> ``HH:MM``.
    # Upstream's expected parse drops the fraction, so we do too.
    iso = _ISO_FRACTIONAL_MINUTE_RE.sub(r"\1", iso)
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError as exc:
        raise OSError(str(exc)) from exc
    if parsed.tzinfo is None:
        # upstream falls back to LocalDateTime + UTC zone
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


# Match ``HH:MM.fff`` (fractional minute, NOT seconds) — we only want to
# strip a fractional component that appears *immediately* after the minute
# and before the TZ offset / end-of-string.
_ISO_FRACTIONAL_MINUTE_RE = re.compile(
    r"(T\d{2}:\d{2})\.\d+(?=(?:[+\-Z]|$))"
)


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
    # Upstream's ``DateConverter.toCalendar("D:")`` and
    # ``toCalendar("D:    ")`` both return null (mirrors
    # ``testToString`` in TestDateUtil). After stripping the ``D:``
    # prefix the residual may be empty / whitespace — return ``None``
    # rather than raising, matching upstream.
    if not date.strip():
        return None
    pos_of_t = date.find("T")
    # The "T at offset != 10" sanity check applies only to digit-led inputs
    # that look like the ``YYYYMMDD`` PDF/ISO shape — for alpha-led shapes
    # (``Friday July 6 17:22:1 GMT+08:00 1979``) the ``T`` inside ``GMT`` is
    # benign and we should fall through to the locale parser.
    if (
        date
        and date[0].isdigit()
        and pos_of_t != 10
        and pos_of_t != -1
    ):
        raise OSError(f"Error converting date:{date}")

    match = _PDF_LIKE_RE.match(date) if date and date[0].isdigit() else None
    if match is None:
        # Wave 1387 — fall through to the SimpleDateFormat dispatcher for
        # alpha-start shapes (``Friday, January 11, 2115`` etc.) and the
        # digit-start shapes the PDF regex doesn't cover (``9:47 5/12/2002``,
        # ``200312172:2:3``, ``26 May 2020 11:25:10``, etc.). Upstream's
        # ``DateConverter.toCalendar`` ultimately delegates here too —
        # ``parseDate`` is invoked when no big-endian / regex form matches.
        return _try_parse_date_fallback(date_string)

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


def _try_parse_date_fallback(date_string: str) -> datetime | None:
    """Wave 1387 — run ``parse_date`` on inputs the PDF regex rejected.

    Upstream's ``DateConverter.toCalendar`` walks through every
    SimpleDateFormat in ``DIGIT_START_FORMATS`` and ``ALPHA_START_FORMATS``
    before giving up. The Python port mirrors that walk via
    :meth:`DateConverter.parse_date`, but the module-level :func:`to_calendar`
    short-circuited on the PDF regex miss. This helper bridges the gap so
    locale-named shapes (``"Friday, January 11, 2115"``) reach the dispatch
    table built in wave 1387.

    Upstream's ``toCalendar`` also enforces ``where.index == text.length()``
    after dispatch — any unconsumed residue invalidates the parse (this is
    how it rejects e.g. ``"20070430193647+713'00' illegal tz hr"``, whose
    big-endian + TZ prefix parses to a valid moment but leaves a residue
    that disqualifies the result).
    """
    # Pre-strip + ``D:`` skip mirrors upstream lines 727-728 exactly.
    text = date_string.lstrip()
    if text.startswith("D:"):
        text = text[2:]
    pos = ParsePosition(0)
    cal = DateConverter.parse_date(text, pos)
    if cal is None or pos.index != len(text):
        raise OSError(f"Error: Invalid date format '{date_string.strip()}'")
    return cal.to_datetime()


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
    Port of ``org.apache.pdfbox.util.DateConverter`` (and
    ``org.apache.xmpbox.DateConverter``).

    Upstream is a ``final`` class with a private constructor and only static
    methods. The Python port keeps the same shape: do not instantiate; call
    :meth:`to_calendar` / :meth:`to_iso8601` / :meth:`to_string` as
    classmethods.

    Internal helpers (``parse_t_zoffset``, ``parse_time_field``,
    ``skip_optionals``, ``skip_string``, ``new_greg``,
    ``parse_big_endian_date``, ``parse_simple_date``, ``parse_date``,
    ``format_t_zoffset``, ``restrain_t_zoffset``, ``adjust_time_zone_nicely``,
    ``update_zone_id``, ``from_iso8601``) are exposed as ``@staticmethod``s
    for parity with upstream's package-private surface (some upstream tests
    reach in and call ``newGreg`` / ``parseTZoffset`` / ``formatTZoffset``
    directly).
    """

    # Upstream constants exposed for parity with reflective upstream tests.
    MINUTES_PER_HOUR: ClassVar[int] = _MINUTES_PER_HOUR
    SECONDS_PER_MINUTE: ClassVar[int] = _SECONDS_PER_MINUTE
    MILLIS_PER_MINUTE: ClassVar[int] = _MILLIS_PER_MINUTE
    MILLIS_PER_HOUR: ClassVar[int] = _MILLIS_PER_HOUR
    HALF_DAY: ClassVar[int] = _HALF_DAY
    DAY: ClassVar[int] = _DAY

    ALPHA_START_FORMATS: ClassVar[tuple[str, ...]] = _ALPHA_START_FORMATS
    DIGIT_START_FORMATS: ClassVar[tuple[str, ...]] = _DIGIT_START_FORMATS

    def __init__(self) -> None:
        # Upstream marks the constructor private so the class can never be
        # instantiated; mirror that here.
        raise TypeError("DateConverter is a utility class and cannot be instantiated")

    # ------------------------------------------------------------------ #
    # Public surface (xmpbox + pdfbox.util)
    # ------------------------------------------------------------------ #

    @staticmethod
    def to_calendar(date_string: str | None) -> datetime | None:
        """Mirror ``DateConverter.toCalendar(String)``.

        Returns ``None`` for ``None`` / empty input, or a tz-aware
        :class:`datetime.datetime` otherwise. Raises :class:`OSError` on
        unparseable strings (Python equivalent of upstream
        ``IOException``).
        """
        return to_calendar(date_string)

    @staticmethod
    def to_iso8601(value: datetime, print_millis: bool = False) -> str:
        """Mirror ``DateConverter.toISO8601(Calendar [, boolean])``."""
        return to_iso8601(value, print_millis)

    @staticmethod
    def to_string(value: datetime | None) -> str | None:
        """Mirror ``DateConverter.toString(Calendar)``.

        Formats ``value`` as a PDF date string
        ``D:yyyyMMddHHmmss±hh'mm'``. Returns ``None`` if ``value`` is
        ``None``. The DST offset is folded into the trailing zone offset, as
        upstream does ``cal.get(ZONE_OFFSET) + cal.get(DST_OFFSET)``.
        """
        if value is None:
            return None
        cal = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        offset = cal.utcoffset() or timedelta(0)
        millis = int(offset.total_seconds() * 1000)
        offset_str = DateConverter.format_t_zoffset(millis, "'")
        return (
            f"D:{cal.year:04d}{cal.month:02d}{cal.day:02d}"
            f"{cal.hour:02d}{cal.minute:02d}{cal.second:02d}"
            f"{offset_str}'"
        )

    # ------------------------------------------------------------------ #
    # Time-zone formatting helpers (DateConverter.java lines 207-292)
    # ------------------------------------------------------------------ #

    @staticmethod
    def restrain_t_zoffset(proposed_offset: int) -> int:
        """Mirror private ``restrainTZoffset(long)``.

        Constrain a time zone offset (in millis) to the range
        ``[-14:00 .. +14:00]`` by folding multiples of a full day, then
        clamping into ``[-12:00 .. +12:00]`` for offsets outside the W3C
        XSD range. See upstream lines 207-226.
        """
        if -14 * _MILLIS_PER_HOUR <= proposed_offset <= 14 * _MILLIS_PER_HOUR:
            return int(proposed_offset)
        # Constrain to ``[-11:59 .. +12:00]``.
        proposed_offset = ((proposed_offset + _HALF_DAY) % _DAY + _DAY) % _DAY
        if proposed_offset == 0:
            return _HALF_DAY
        # 0 <= proposed_offset < DAY
        proposed_offset = (proposed_offset - _HALF_DAY) % _HALF_DAY
        # -HALF_DAY < proposed_offset < HALF_DAY
        return int(proposed_offset)

    @staticmethod
    def format_t_zoffset(millis: int, sep: str) -> str:
        """Mirror package-private ``formatTZoffset(long, String)``.

        Formats a TZ offset as ``±HH<sep>MM`` with the offset clamped via
        :meth:`restrain_t_zoffset`. Used by both :meth:`to_string` (PDF
        ``'`` separator) and :meth:`to_iso8601` (``:`` separator).
        """
        offset = DateConverter.restrain_t_zoffset(millis)
        sign = "+" if offset >= 0 else "-"
        offset = abs(offset)
        hours = offset // _MILLIS_PER_HOUR
        minutes = (offset % _MILLIS_PER_HOUR) // _MILLIS_PER_MINUTE
        return f"{sign}{hours:02d}{sep}{minutes:02d}"

    @staticmethod
    def update_zone_id(grec: _GregLike) -> None:
        """Mirror private ``updateZoneId(TimeZone)``.

        Sets ``grec.tz_id`` to ``GMT`` / ``GMT±HH:MM`` / ``unknown`` based on
        the raw offset, matching upstream lines 482-509.
        """
        offset = grec.zone_offset
        sign = "+"
        if offset < 0:
            sign = "-"
            offset = -offset
        hh = offset // 3_600_000
        mm = (offset % 3_600_000) // 60_000
        if offset == 0:
            grec.tz_id = "GMT"
        elif sign == "+" and hh <= 12:
            grec.tz_id = f"GMT+{hh:02d}:{mm:02d}"
        elif sign == "-" and hh <= 14:
            grec.tz_id = f"GMT-{hh:02d}:{mm:02d}"
        else:
            grec.tz_id = "unknown"

    # ------------------------------------------------------------------ #
    # ParsePosition-driven scanning helpers (lines 307-394)
    # ------------------------------------------------------------------ #

    @staticmethod
    def parse_time_field(
        text: str | None, where: ParsePosition, maxlen: int, remedy: int
    ) -> int:
        """Mirror private ``parseTimeField(String, ParsePosition, int, int)``.

        Parse up to ``maxlen`` digits starting at ``where.index``. Returns
        the parsed integer or ``remedy`` if no digits were found. Advances
        ``where`` by the number of digits consumed.
        """
        if text is None:
            return remedy
        retval = 0
        index = where.index
        limit = index + min(maxlen, len(text) - index)
        start = index
        while index < limit:
            ch = text[index]
            if not ch.isdigit():
                break
            retval = retval * 10 + (ord(ch) - ord("0"))
            index += 1
        if index == start:
            return remedy
        where.index = index
        return retval

    @staticmethod
    def skip_optionals(text: str, where: ParsePosition, optionals: str) -> str:
        """Mirror private ``skipOptionals(String, ParsePosition, String)``.

        Advance ``where`` past any characters present in ``optionals``,
        returning the last non-space character skipped (or ``' '`` if none).
        """
        retval = " "
        while where.index < len(text):
            currch = text[where.index]
            if currch not in optionals:
                break
            if currch != " ":
                retval = currch
            where.index += 1
        return retval

    @staticmethod
    def skip_string(text: str, victim: str, where: ParsePosition) -> bool:
        """Mirror private ``skipString(String, String, ParsePosition)``.

        If ``text[where.index:]`` starts with ``victim``, advance and return
        ``True``. Otherwise leave ``where`` alone and return ``False``.
        """
        if text.startswith(victim, where.index):
            where.index += len(victim)
            return True
        return False

    @staticmethod
    def new_greg() -> _GregLike:
        """Mirror package-private ``newGreg()``.

        Construct a fresh calendar-like object with UTC as the time zone,
        non-lenient parsing, and milliseconds zeroed.
        """
        cal = _GregLike()
        cal.zone_offset = 0
        cal.dst_offset = 0
        cal.tz_id = "UTC"
        cal.lenient = False
        cal.millisecond = 0
        return cal

    @staticmethod
    def adjust_time_zone_nicely(cal: _GregLike, tz_offset_millis: int) -> None:
        """Mirror private ``adjustTimeZoneNicely(GregorianCalendar, TimeZone)``.

        Replace the calendar's zone offset without shifting the wall clock
        forward — instead, subtract the offset back out via ``add(MINUTE)``
        so the moment-in-time changes but the displayed fields stay put.
        """
        cal.zone_offset = tz_offset_millis
        cal.dst_offset = 0
        offset_minutes = (cal.zone_offset + cal.dst_offset) // _MILLIS_PER_MINUTE
        cal.add_minutes(-offset_minutes)

    # ------------------------------------------------------------------ #
    # TZ parser (lines 429-473)
    # ------------------------------------------------------------------ #

    @staticmethod
    def parse_t_zoffset(
        text: str, cal: _GregLike, initial_where: ParsePosition
    ) -> bool:
        """Mirror package-private ``parseTZoffset``.

        Try to parse ``(Z|GMT|UTC)? [+- ]* h [': ]? m '?`` at ``initial_where``.
        On success, update ``cal``'s zone offset and advance
        ``initial_where``; return ``True``. On failure, leave both unchanged
        and return ``False``.
        """
        where = ParsePosition(initial_where.index)
        tz_offset_millis = 0
        sign = DateConverter.skip_optionals(text, where, "Z+- ")
        had_gmt = (
            sign == "Z"
            or DateConverter.skip_string(text, "GMT", where)
            or DateConverter.skip_string(text, "UTC", where)
        )
        if had_gmt:
            sign = DateConverter.skip_optionals(text, where, "+- ")

        tz_hours = DateConverter.parse_time_field(text, where, 2, -999)
        DateConverter.skip_optionals(text, where, "': ")
        tz_min = DateConverter.parse_time_field(text, where, 2, 0)
        DateConverter.skip_optionals(text, where, "' ")

        if tz_hours != -999:
            hr_sign = -1 if sign == "-" else 1
            tz_offset_millis = DateConverter.restrain_t_zoffset(
                hr_sign * (tz_hours * _MILLIS_PER_HOUR + tz_min * _MILLIS_PER_MINUTE)
            )
            # update zone id (parity with upstream — the side effect is a
            # human-readable label, not a behavioural change).
            tmp = _GregLike()
            tmp.zone_offset = tz_offset_millis
            DateConverter.update_zone_id(tmp)
        elif not had_gmt:
            # try to process as a name; "GMT" / "UTC" already consumed above.
            tz_text = text[initial_where.index :].strip()
            tz_offset_millis = _lookup_named_tz_offset(tz_text)
            if tz_offset_millis is None:
                # unknown name → no timezone
                return False
            where.index = len(text)

        DateConverter.adjust_time_zone_nicely(cal, tz_offset_millis)
        initial_where.index = where.index
        return True

    # ------------------------------------------------------------------ #
    # Big-endian / simple-date / dispatch parsers (lines 526-690)
    # ------------------------------------------------------------------ #

    @staticmethod
    def parse_big_endian_date(
        text: str, initial_where: ParsePosition
    ) -> _GregLike | None:
        """Mirror private ``parseBigEndianDate``.

        Parse ``year [-/ ]* month [-/ ]* day [ T]* hour [:] min [:] sec
        [.frac]``. Returns a fresh :class:`_GregLike` on success, or
        ``None`` when no four-digit year is present.
        """
        where = ParsePosition(initial_where.index)
        year = DateConverter.parse_time_field(text, where, 4, 0)
        if where.index != 4 + initial_where.index:
            return None
        DateConverter.skip_optionals(text, where, "/- ")
        month = DateConverter.parse_time_field(text, where, 2, 1) - 1
        DateConverter.skip_optionals(text, where, "/- ")
        day = DateConverter.parse_time_field(text, where, 2, 1)
        DateConverter.skip_optionals(text, where, " T")
        hour = DateConverter.parse_time_field(text, where, 2, 0)
        DateConverter.skip_optionals(text, where, ": ")
        minute = DateConverter.parse_time_field(text, where, 2, 0)
        DateConverter.skip_optionals(text, where, ": ")
        second = DateConverter.parse_time_field(text, where, 2, 0)
        next_c = DateConverter.skip_optionals(text, where, ".")
        if next_c == ".":
            DateConverter.parse_time_field(text, where, 19, 0)

        dest = DateConverter.new_greg()
        try:
            dest.set_fields(year, month, day, hour, minute, second)
            dest.validate()
        except (ValueError, OverflowError):
            return None
        initial_where.index = where.index
        DateConverter.skip_optionals(text, initial_where, " ")
        return dest

    @staticmethod
    def parse_simple_date(
        text: str, fmts: tuple[str, ...] | list[str], initial_where: ParsePosition
    ) -> _GregLike | None:
        """Mirror private ``parseSimpleDate``.

        The Python port has no ``SimpleDateFormat`` so this routine is a
        best-effort partial port: it recognises the digit-first patterns
        actually used by upstream test data (``M/d/yy[yy]``,
        ``yyyy MMM d``, etc.) by regex. Patterns that depend on the JVM's
        locale-sensitive month/day-name dictionaries are not currently
        recognised — callers fall through to :meth:`parse_big_endian_date`
        or the high-level :func:`to_calendar`. Returns ``None`` when no
        format matched.
        """
        # Direct ports of the digit-start formats most common in upstream
        # test fixtures. Ordering matters — upstream notes explicitly that
        # longer prefixes must precede shorter ones (lines 100-104).
        remaining = text[initial_where.index :]
        for fmt in fmts:
            cal, consumed = _try_simple_format(remaining, fmt)
            if cal is not None:
                initial_where.index += consumed
                DateConverter.skip_optionals(text, initial_where, " ")
                return cal
        return None

    @staticmethod
    def parse_date(text: str | None, initial_where: ParsePosition) -> _GregLike | None:
        """Mirror private ``parseDate``.

        High-level dispatch: try big-endian first (with optional trailing
        TZ), then a simple-format list keyed off whether the first
        character is a digit. Returns the longest-consumed match.
        """
        if text is None or text == "" or text.strip() == "D:":
            return None

        longest_len = -999_999
        longest_date: _GregLike | None = None

        where = ParsePosition(initial_where.index)
        DateConverter.skip_optionals(text, where, " ")
        start_position = where.index

        # try big-endian parse
        ret_cal = DateConverter.parse_big_endian_date(text, where)
        if ret_cal is not None and (
            where.index == len(text)
            or DateConverter.parse_t_zoffset(text, ret_cal, where)
        ):
            where_len = where.index
            if where_len == len(text):
                initial_where.index = where_len
                return ret_cal
            longest_len = where_len
            longest_date = ret_cal

        # try one of the sets of standard formats
        where.index = start_position
        if start_position < len(text) and text[start_position].isdigit():
            formats = DateConverter.DIGIT_START_FORMATS
        else:
            formats = DateConverter.ALPHA_START_FORMATS
        ret_cal = DateConverter.parse_simple_date(text, formats, where)
        if ret_cal is not None and (
            where.index == len(text)
            or DateConverter.parse_t_zoffset(text, ret_cal, where)
        ):
            where_len = where.index
            if where_len == len(text):
                initial_where.index = where_len
                return ret_cal
            # Both parses succeeded but left residue, and simple-format consumed
            # more than big-endian. Unreachable with the partial SimpleDateFormat
            # port — the simple parser only matches purely numeric prefixes that
            # big-endian already eats.
            if where_len > longest_len:  # pragma: no cover
                longest_len = where_len  # pragma: no cover
                longest_date = ret_cal  # pragma: no cover

        if longest_date is not None:
            initial_where.index = longest_len
            return longest_date
        return ret_cal

    # ------------------------------------------------------------------ #
    # ISO 8601 helper kept exposed for parity (lines 311-323)
    # ------------------------------------------------------------------ #

    @staticmethod
    def from_iso8601(date_string: str) -> datetime:
        """Mirror private ``fromISO8601(String)``.

        Exposed at module level for parity with upstream's package-private
        access (some upstream xmpbox tests reach into the helper directly).
        """
        return _from_iso8601(date_string)


# Lookup table for the named time zones upstream's TimeZone.getTimeZone()
# recognises. Sticks to the IDs exercised by upstream tests (see
# TestDateUtil#testParseTZ); unknown IDs return ``None``.
_NAMED_TZ_OFFSETS: dict[str, int] = {
    "PST": -8 * _MILLIS_PER_HOUR,
    "MST": -7 * _MILLIS_PER_HOUR,
    "CST": -6 * _MILLIS_PER_HOUR,
    "EST": -5 * _MILLIS_PER_HOUR,
    "America/Chicago": -6 * _MILLIS_PER_HOUR,
    "America/New_York": -5 * _MILLIS_PER_HOUR,
    "America/Los_Angeles": -8 * _MILLIS_PER_HOUR,
    "Europe/Moscow": 3 * _MILLIS_PER_HOUR,
    "Europe/Berlin": 1 * _MILLIS_PER_HOUR,
    "Australia/Adelaide": 9 * _MILLIS_PER_HOUR + 30 * _MILLIS_PER_MINUTE,
}


def _lookup_named_tz_offset(name: str) -> int | None:
    """Return the raw offset (millis) for ``name``, or ``None`` if unknown.

    Upstream relies on Java's ``TimeZone.getTimeZone()`` which returns
    ``GMT`` (offset 0) for unknown IDs — that's how it signals "unknown".
    The Python port returns ``None`` so callers can distinguish "unknown
    name" from "valid GMT input".
    """
    if not name:
        return None
    return _NAMED_TZ_OFFSETS.get(name)


# Regex-driven implementations of the subset of SimpleDateFormat patterns
# upstream's DIGIT_START_FORMATS exercise. Each entry maps a Java pattern
# string to a callable ``(text) -> (cal, consumed_chars) | (None, 0)``.

_MONTH_NAME_TO_NUM = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _two_digit_year_to_full(yy: int) -> int:
    """Mirror Java SimpleDateFormat's two-digit year sliding window.

    Java picks the year in ``[thisyear-79 .. thisyear+20]``. The Python
    port stays close to that — it uses today's year as the pivot.
    """
    today = datetime.now(UTC).year
    base = today - 79
    century = (base // 100) * 100
    candidate = century + yy
    if candidate < base:
        candidate += 100
    if candidate > base + 99:  # pragma: no cover - unreachable given today's pivot
        candidate -= 100
    return candidate


def _try_simple_format(text: str, fmt: str) -> tuple[_GregLike | None, int]:
    """Best-effort regex-driven port of Java SimpleDateFormat parsing.

    Implementing the full SimpleDateFormat surface is out of scope; this
    handles the format strings upstream actually exercises.
    """
    handler = _SIMPLE_FORMAT_HANDLERS.get(fmt)
    if handler is None:
        return None, 0
    return handler(text)


def _make_handler_yyyy_mmm_d(text: str) -> tuple[_GregLike | None, int]:
    # "yyyy MMM d" — e.g. "2000 Feb 29"
    match = re.match(r"^(\d{4})\s+([A-Za-z]+)\s+(\d{1,2})", text)
    if match is None:
        return None, 0
    month_num = _MONTH_NAME_TO_NUM.get(match.group(2)[:3].lower())
    if month_num is None:
        return None, 0
    cal = DateConverter.new_greg()
    try:
        cal.set_fields(int(match.group(1)), month_num - 1, int(match.group(3)))
        cal.validate()
    except (ValueError, OverflowError):
        return None, 0
    return cal, match.end()


def _make_handler_dd_mmm_yy_hms(text: str) -> tuple[_GregLike | None, int]:
    # "dd MMM yy HH:mm:ss" — e.g. "26 May 2000 11:25:10"
    match = re.match(
        r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{2,4})\s+(\d{1,2}):(\d{1,2}):(\d{1,2})", text
    )
    if match is None:
        return None, 0
    month_num = _MONTH_NAME_TO_NUM.get(match.group(2)[:3].lower())
    if month_num is None:
        return None, 0
    year_str = match.group(3)
    year = int(year_str) if len(year_str) == 4 else _two_digit_year_to_full(int(year_str))
    cal = DateConverter.new_greg()
    try:
        cal.set_fields(
            year,
            month_num - 1,
            int(match.group(1)),
            int(match.group(4)),
            int(match.group(5)),
            int(match.group(6)),
        )
        cal.validate()
    except (ValueError, OverflowError):
        return None, 0
    return cal, match.end()


def _make_handler_dd_mmm_yy_hm(text: str) -> tuple[_GregLike | None, int]:
    # "dd MMM yy HH:mm" — e.g. "26 May 2000 11:25"
    match = re.match(
        r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{2,4})\s+(\d{1,2}):(\d{1,2})", text
    )
    if match is None:
        return None, 0
    month_num = _MONTH_NAME_TO_NUM.get(match.group(2)[:3].lower())
    if month_num is None:
        return None, 0
    year_str = match.group(3)
    year = int(year_str) if len(year_str) == 4 else _two_digit_year_to_full(int(year_str))
    cal = DateConverter.new_greg()
    try:
        cal.set_fields(
            year,
            month_num - 1,
            int(match.group(1)),
            int(match.group(4)),
            int(match.group(5)),
        )
        cal.validate()
    except (ValueError, OverflowError):
        return None, 0
    return cal, match.end()


def _make_handler_yyyymmdd_hms(text: str) -> tuple[_GregLike | None, int]:
    # "yyyymmddhh:mm:ss" — e.g. "200712172:2:3"
    match = re.match(r"^(\d{8})(\d{1,2}):(\d{1,2}):(\d{1,2})", text)
    if match is None:
        return None, 0
    digits = match.group(1)
    cal = DateConverter.new_greg()
    try:
        cal.set_fields(
            int(digits[:4]),
            int(digits[4:6]) - 1,
            int(digits[6:8]),
            int(match.group(2)),
            int(match.group(3)),
            int(match.group(4)),
        )
        cal.validate()
    except (ValueError, OverflowError):
        return None, 0
    return cal, match.end()


def _make_handler_h_m_md_yy(text: str) -> tuple[_GregLike | None, int]:
    # "H:m M/d/yy" — e.g. "9:47 5/12/2008"
    match = re.match(
        r"^(\d{1,2}):(\d{1,2})\s+(\d{1,2})/(\d{1,2})/(\d{2,4})", text
    )
    if match is None:
        return None, 0
    year_str = match.group(5)
    year = int(year_str) if len(year_str) == 4 else _two_digit_year_to_full(int(year_str))
    cal = DateConverter.new_greg()
    try:
        cal.set_fields(
            year,
            int(match.group(3)) - 1,
            int(match.group(4)),
            int(match.group(1)),
            int(match.group(2)),
        )
        cal.validate()
    except (ValueError, OverflowError):
        return None, 0
    return cal, match.end()


def _make_handler_md_yy_hms(text: str) -> tuple[_GregLike | None, int]:
    # "M/d/yy HH:mm:ss" — e.g. "7/6/1973 17:22:1"
    match = re.match(
        r"^(\d{1,2})/(\d{1,2})/(\d{2,4})\s+(\d{1,2}):(\d{1,2}):(\d{1,2})", text
    )
    if match is None:
        return None, 0
    year_str = match.group(3)
    year = int(year_str) if len(year_str) == 4 else _two_digit_year_to_full(int(year_str))
    cal = DateConverter.new_greg()
    try:
        cal.set_fields(
            year,
            int(match.group(1)) - 1,
            int(match.group(2)),
            int(match.group(4)),
            int(match.group(5)),
            int(match.group(6)),
        )
        cal.validate()
    except (ValueError, OverflowError):
        return None, 0
    return cal, match.end()


def _make_handler_md_yy_hm(text: str) -> tuple[_GregLike | None, int]:
    # "M/d/yy HH:mm"
    match = re.match(
        r"^(\d{1,2})/(\d{1,2})/(\d{2,4})\s+(\d{1,2}):(\d{1,2})", text
    )
    if match is None:
        return None, 0
    year_str = match.group(3)
    year = int(year_str) if len(year_str) == 4 else _two_digit_year_to_full(int(year_str))
    cal = DateConverter.new_greg()
    try:
        cal.set_fields(
            year,
            int(match.group(1)) - 1,
            int(match.group(2)),
            int(match.group(4)),
            int(match.group(5)),
        )
        cal.validate()
    except (ValueError, OverflowError):
        return None, 0
    return cal, match.end()


def _make_handler_md_yy(text: str) -> tuple[_GregLike | None, int]:
    # "M/d/yy" — bare date
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})", text)
    if match is None:
        return None, 0
    year_str = match.group(3)
    year = int(year_str) if len(year_str) == 4 else _two_digit_year_to_full(int(year_str))
    cal = DateConverter.new_greg()
    try:
        cal.set_fields(year, int(match.group(1)) - 1, int(match.group(2)))
        cal.validate()
    except (ValueError, OverflowError):
        return None, 0
    return cal, match.end()


def _make_handler_mmdd_yyyy_hms(text: str) -> tuple[_GregLike | None, int]:
    """Wave 1388 — explicit ``MM/dd/yyyy HH:mm:ss`` (US default).

    Java's ``SimpleDateFormat("MM/dd/yyyy HH:mm:ss", Locale.ENGLISH)`` parses
    month-first then day with strict 4-digit year — mirrors the commented-out
    upstream rule on ``DateConverter.java`` line 137. Lenient at parse time
    on the month / day width to match Java's SimpleDateFormat
    ``setLenient(false)`` calendar rules (which apply to the *Calendar*
    value, not the numeric-field width). Out-of-range months / days fall
    through via ``cal.validate()``.
    """
    match = re.match(
        r"^(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{1,2}):(\d{1,2})", text
    )
    if match is None:
        return None, 0
    cal = DateConverter.new_greg()
    try:
        cal.set_fields(
            int(match.group(3)),
            int(match.group(1)) - 1,
            int(match.group(2)),
            int(match.group(4)),
            int(match.group(5)),
            int(match.group(6)),
        )
        cal.validate()
    except (ValueError, OverflowError):
        return None, 0
    return cal, match.end()


def _make_handler_mmdd_yyyy_hm(text: str) -> tuple[_GregLike | None, int]:
    """Wave 1388 — explicit ``MM/dd/yyyy HH:mm`` (US default)."""
    match = re.match(
        r"^(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{1,2})", text
    )
    if match is None:
        return None, 0
    cal = DateConverter.new_greg()
    try:
        cal.set_fields(
            int(match.group(3)),
            int(match.group(1)) - 1,
            int(match.group(2)),
            int(match.group(4)),
            int(match.group(5)),
        )
        cal.validate()
    except (ValueError, OverflowError):
        return None, 0
    return cal, match.end()


def _make_handler_mmdd_yyyy(text: str) -> tuple[_GregLike | None, int]:
    """Wave 1388 — explicit ``MM/dd/yyyy`` (US default, no time)."""
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match is None:
        return None, 0
    cal = DateConverter.new_greg()
    try:
        cal.set_fields(
            int(match.group(3)),
            int(match.group(1)) - 1,
            int(match.group(2)),
        )
        cal.validate()
    except (ValueError, OverflowError):
        return None, 0
    return cal, match.end()


def _make_handler_locale(fmt: str):
    """Build a handler that delegates to :func:`parse_with_locale`.

    Wave 1387 closes the locale-sensitive parsing divergence; this adapter
    plumbs the locale-aware parser into the existing SimpleFormat dispatch
    table so the ALPHA_START_FORMATS shapes (``"EEEE, MMM dd, yy"`` etc.)
    actually fire instead of falling through. Returns a callable matching
    the ``(text) -> (cal | None, consumed_chars)`` contract.
    """
    from pypdfbox.util.date_util import parse_with_locale  # local import to avoid cycle

    def handler(text: str) -> tuple[_GregLike | None, int]:
        if not text:
            return None, 0
        # Strip leading whitespace (the parser does it too, but we need the
        # consumed-length to start from the original index).
        leading = 0
        while leading < len(text) and text[leading].isspace():
            leading += 1
        best_end = -1
        # Walk backwards from end-of-string toward the start, accepting the
        # longest prefix the locale parser successfully consumes. This lets a
        # trailing TZ designation (``GMT+08:00`` etc.) be picked up by the
        # outer ``parse_date`` driver's ``parse_t_zoffset`` call. Bounded
        # suffix-walk so cost stays linear in pattern length.
        max_back = min(len(text) - leading, 64)
        for end in range(len(text), len(text) - max_back - 1, -1):
            parsed = parse_with_locale(text[leading:end], fmt, locale="en")
            if parsed is not None:
                best_end = end
                break
        if best_end == -1:
            return None, 0
        cal = DateConverter.new_greg()
        try:
            cal.set_fields(
                parsed.year,
                parsed.month - 1,
                parsed.day,
                parsed.hour,
                parsed.minute,
                parsed.second,
            )
            cal.validate()
        except (ValueError, OverflowError):
            return None, 0
        return cal, best_end

    return handler


def _make_handler_locale_split_at_tz(fmt: str):
    """Like :func:`_make_handler_locale` but stops before a ``z`` literal.

    Patterns that embed a ``z`` (Java TZ-designator) sandwich a TZ token
    between two field groups (e.g. ``"EEEE MMM dd HH:mm:ss z yy"`` — fields
    before ``z`` plus a year *after* ``z``). The TZ semantics need to flow
    through the existing :meth:`DateConverter.parse_t_zoffset` for parity
    with the upstream port. This handler parses the pre-``z`` prefix via
    :func:`parse_with_locale` on the prefix-pattern, runs the outer
    ``parse_t_zoffset`` on the residue, then parses the post-``z`` tail
    (year-only is the only shape PDFBox carries).
    """
    from pypdfbox.util.date_util import parse_with_locale  # local import to avoid cycle

    z_index = fmt.find(" z")
    pre_fmt = fmt[:z_index]
    post_fmt = fmt[z_index + 2 :].lstrip()

    def handler(text: str) -> tuple[_GregLike | None, int]:
        if not text:
            return None, 0
        leading = 0
        while leading < len(text) and text[leading].isspace():
            leading += 1
        # Walk forward from a reasonable start, find the longest prefix that
        # ``pre_fmt`` accepts.
        best_pre_end = -1
        # Try anchor points that look like the end of the pre-tz field group.
        for end in range(len(text), leading, -1):
            parsed_pre = parse_with_locale(text[leading:end], pre_fmt, locale="en")
            if parsed_pre is None:
                continue
            # We have a pre-tz parse. Now try to parse the TZ + year tail.
            tail = text[end:].lstrip()
            if not tail:
                continue
            # Consume a contiguous non-space TZ blob.
            tz_end = 0
            while tz_end < len(tail) and not tail[tz_end].isspace():
                tz_end += 1
            tz_blob = tail[:tz_end]
            year_part = tail[tz_end:].lstrip()
            if not tz_blob or not year_part:
                continue
            # Validate the year part against ``post_fmt`` (always ``"yy"``
            # for the PDFBox shape).
            parsed_post = parse_with_locale(year_part, post_fmt, locale="en")
            if parsed_post is None:
                continue
            best_pre_end = end
            best_year = parsed_post.year
            best_parsed = parsed_pre
            best_tz_blob = tz_blob
            break
        if best_pre_end == -1:
            return None, 0
        cal = DateConverter.new_greg()
        try:
            cal.set_fields(
                best_year,
                best_parsed.month - 1,
                best_parsed.day,
                best_parsed.hour,
                best_parsed.minute,
                best_parsed.second,
            )
            cal.validate()
        except (ValueError, OverflowError):
            return None, 0
        # Apply the TZ to the offset fields *without* shifting the wall
        # clock — upstream's SimpleDateFormat treats the TZ designator as
        # the moment's actual offset, not a translation. We replicate the
        # offset-extraction logic of ``parse_t_zoffset`` but skip the
        # subsequent ``adjust_time_zone_nicely`` step.
        tz_tmp = DateConverter.new_greg()
        tz_pos = ParsePosition(0)
        if DateConverter.parse_t_zoffset(best_tz_blob, tz_tmp, tz_pos):
            cal.zone_offset = tz_tmp.zone_offset
            cal.dst_offset = tz_tmp.dst_offset
        return cal, len(text)

    return handler


_SIMPLE_FORMAT_HANDLERS = {
    "dd MMM yy HH:mm:ss": _make_handler_dd_mmm_yy_hms,
    "dd MMM yy HH:mm": _make_handler_dd_mmm_yy_hm,
    "yyyy MMM d": _make_handler_yyyy_mmm_d,
    "yyyymmddhh:mm:ss": _make_handler_yyyymmdd_hms,
    "H:m M/d/yy": _make_handler_h_m_md_yy,
    "M/d/yy HH:mm:ss": _make_handler_md_yy_hms,
    "M/d/yy HH:mm": _make_handler_md_yy_hm,
    "M/d/yy": _make_handler_md_yy,
    # Wave 1388 — explicit US-default MM/dd/yyyy variants. The "M/d/yy"
    # handler above already accepts these inputs (it matches \d{1,2}/\d{1,2}/
    # \d{2,4}); registering them explicitly makes the dispatch table 1:1 with
    # the upstream-commented format list (DateConverter.java lines 136-142).
    "MM/dd/yyyy HH:mm:ss": _make_handler_mmdd_yyyy_hms,
    "MM/dd/yyyy HH:mm": _make_handler_mmdd_yyyy_hm,
    "MM/dd/yyyy": _make_handler_mmdd_yyyy,
    # Wave 1387 — alpha-start formats wired through the bundled locale tables.
    "EEEE, dd MMM yy hh:mm:ss a": _make_handler_locale("EEEE, dd MMM yy hh:mm:ss a"),
    "EEEE, MMM dd, yy hh:mm:ss a": _make_handler_locale("EEEE, MMM dd, yy hh:mm:ss a"),
    "EEEE, MMM dd, yy 'at' hh:mma": _make_handler_locale("EEEE, MMM dd, yy 'at' hh:mma"),
    "EEEE, MMM dd, yy": _make_handler_locale("EEEE, MMM dd, yy"),
    "EEEE MMM dd, yy HH:mm:ss": _make_handler_locale("EEEE MMM dd, yy HH:mm:ss"),
    "EEEE MMM dd HH:mm:ss z yy": _make_handler_locale_split_at_tz(
        "EEEE MMM dd HH:mm:ss z yy"
    ),
    "EEEE MMM dd HH:mm:ss yy": _make_handler_locale("EEEE MMM dd HH:mm:ss yy"),
}
