"""Live PDFBox differential parity for ``org.apache.pdfbox.util.DateConverter``.

One Java probe (``DateConvertProbe``), two surfaces:

* **Parse** — ``DateConverter.toCalendar(String)`` (PDFBox) vs pypdfbox's
  :func:`pypdfbox.xmpbox.date_converter.to_calendar`. The probe emits
  ``"<epochMillis> <offsetMillis>"`` for a parsed calendar (pinning both the
  absolute instant and the zone offset PDFBox chose to display), or ``NULL``
  for input PDFBox cannot parse. PDFBox's ``toCalendar(String)`` never throws
  in 3.0.7 — it returns null for unparseable input. pypdfbox mirrors the
  *parsing* of ``org.apache.pdfbox.util.DateConverter`` exactly but, following
  the throwing contract of ``org.apache.xmpbox.DateConverter`` (which the
  module also ports), surfaces a rejected input as :class:`OSError` (or
  ``None`` for empty / whitespace-only / ``"D:"`` input) rather than returning
  null. So "both reject" is the parity condition for the ``NULL`` rows — a
  documented, load-bearing divergence in *form* (exception vs null), never in
  *which inputs are accepted*.

* **Format** — ``DateConverter.toString(Calendar)`` (PDFBox) vs
  :meth:`DateConverter.to_string`. The probe builds a calendar at a fixed
  instant in a fixed-offset zone and emits the canonical
  ``D:yyyyMMddHHmmss(+|-)HH'mm'`` PDF date string.

Covers: well-formed ``+``/``-``/``Z`` offsets, partial dates
(``D:2009`` … ``D:200912311859``), no ``D:`` prefix, missing trailing
apostrophe, ``Z`` followed by an explicit offset, unquoted / partial offsets,
out-of-range TZ designations (folded modulo a day, NOT rejected), GMT/UTC and
named-TZ forms, the ``setLenient(false)`` calendar rejects (second 60, Feb 31,
hour 24, month 13, day 0, year 0), ISO 8601 shapes, alpha-led locale shapes,
trailing-residue rejects, and round-trip (parse -> format -> parse).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pypdfbox.xmpbox.date_converter import DateConverter, to_calendar
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------------- #
# Parse battery
# --------------------------------------------------------------------------- #

_PARSE_INPUTS: tuple[str, ...] = (
    # Well-formed, no offset (UTC default)
    "D:20240315120000",
    "20240315120000",  # no D: prefix
    # Well-formed offsets
    "D:20240315120000Z",
    "D:20240315120000+05'30'",
    "D:20240315120000-08'00'",
    "D:20240315120000+0530",  # unquoted
    "D:20240315120000+05",  # hours only
    "D:20240315120000-05",
    # Missing trailing apostrophe / partial-apostrophe forms
    "D:20240315120000+05'30",
    "D:20240315120000+0530'",
    "D:20240315120000+05'",
    # Z followed by an explicit offset
    "D:20240315120000Z00'00'",
    "D:20240315120000Z05'00'",
    # Partial dates
    "D:2009",
    "D:200912",
    "D:20091231",
    "D:2009123118",
    "D:200912311859",
    "D:20240315",
    "D:1999",
    "2024",  # no prefix, year only
    # GMT / UTC forms
    "D:20240315120000GMT+05:30",
    "D:20240315120000UTC",
    "GMT+05:30",  # bare GMT — PDFBox rejects (null)
    # Out-of-range TZ designations (folded modulo a day, NOT rejected)
    "D:20240315120000+24'00'",
    "D:20240315120000+99'00'",
    "D:20240315120000-99'00'",
    # Edge-but-valid TZ
    "D:20240315120000+14'00'",
    "D:20240315120000+13'00'",
    # setLenient(false) calendar rejects (PDFBox returns null)
    "D:20240315120060",  # second 60
    "D:20240315120060Z",
    "D:20240315235960",  # second 60 at 23:59
    "D:20240231120000",  # Feb 31
    "D:2024031524",  # hour 24
    "D:202413",  # month 13
    "D:20240300",  # day 00
    "D:00001231",  # year 0 (BCE-ish) — both reject
    "D:990101000000",  # 6-digit year shape that PDFBox rejects
    # Valid leap day
    "D:20240229120000",
    # Boundary year
    "D:99991231235959",
    # ISO 8601 shapes
    "2024-03-15T12:00:00Z",
    "2024-03-15T12:00:00+05:30",
    "2024-03-15T12:00:00",
    # Alpha-led / named-TZ shapes
    "26 May 2020 11:25:10",
    "Friday July 6 17:22:1 GMT+08:00 1979",
    "Mon Sept 24 11:22:33 2007",  # PDFBox rejects this shape (null)
    # Trailing residue (PDFBox rejects — index != length)
    "20070430193647+713'00' illegal tz hr",
    "D:20240315120000 trailing",
    # Pure garbage
    "garbage",
    # Empty / whitespace / bare prefix (PDFBox null; pypdfbox returns None)
    "D:",
    "D:    ",
)

_PARSE_IDS = tuple(s.replace(" ", "_").replace("'", "q").replace(":", "c") for s in _PARSE_INPUTS)


def _py_parse_fingerprint(date_str: str) -> str:
    """pypdfbox to_calendar rendered as the probe's ``"<epoch> <offset>"``.

    Returns ``"NULL"`` when pypdfbox rejects the input — either by returning
    ``None`` (empty / whitespace / ``"D:"``) or by raising :class:`OSError`
    (every other unparseable shape). PDFBox returns null for all of these, so
    collapsing both pypdfbox rejection forms to ``"NULL"`` is the parity check.
    """
    try:
        dt = to_calendar(date_str)
    except OSError:
        return "NULL"
    if dt is None:
        return "NULL"
    epoch = int(dt.timestamp() * 1000)
    off = dt.utcoffset()
    off_ms = 0 if off is None else int(off.total_seconds() * 1000)
    return f"{epoch} {off_ms}"


@requires_oracle
@pytest.mark.parametrize("date_str", _PARSE_INPUTS, ids=list(_PARSE_IDS))
def test_to_calendar_matches_pdfbox(date_str: str) -> None:
    java = run_probe_text("DateConvertProbe", "parse", date_str)
    py = _py_parse_fingerprint(date_str)
    assert py == java


# --------------------------------------------------------------------------- #
# Format battery — DateConverter.toString(Calendar)
# --------------------------------------------------------------------------- #

# (epoch_millis, offset_minutes) — a fixed instant displayed in a fixed-offset
# zone. The probe and pypdfbox must format these to the same canonical string.
_FORMAT_CASES: tuple[tuple[int, int], ...] = (
    (1710504000000, 0),  # 2024-03-15 12:00 UTC
    (1710504000000, 330),  # +05:30
    (1710504000000, -480),  # -08:00
    (1710504000000, 60),  # +01:00
    (1710504000000, -300),  # -05:00
    (1710504000000, 840),  # +14:00 (max W3C)
    (1710504000000, -720),  # -12:00
    (1710504000000, 720),  # +12:00
    (0, 0),  # epoch
    (1710504000000, 45),  # +00:45 odd minute offset
    (1710504000000, -570),  # -09:30
    (253402300799000, 0),  # 9999-12-31 23:59:59
    (1710504000000, 900),  # +15:00 -> restrained to -09:00
    (1710504000000, -900),  # -15:00 -> restrained to +09:00
)

_FORMAT_IDS = tuple(f"e{e}_o{o}" for e, o in _FORMAT_CASES)


def _py_format(epoch_ms: int, off_min: int) -> str:
    tz = timezone(timedelta(minutes=off_min))
    dt = datetime.fromtimestamp(epoch_ms / 1000, tz=tz)
    return DateConverter.to_string(dt)


@requires_oracle
@pytest.mark.parametrize(("epoch_ms", "off_min"), _FORMAT_CASES, ids=list(_FORMAT_IDS))
def test_to_string_matches_pdfbox(epoch_ms: int, off_min: int) -> None:
    java = run_probe_text("DateConvertProbe", "format", str(epoch_ms), str(off_min))
    py = _py_format(epoch_ms, off_min)
    assert py == java


# --------------------------------------------------------------------------- #
# Round-trip — parse -> format -> parse must converge to the same instant
# --------------------------------------------------------------------------- #

_ROUNDTRIP_INPUTS: tuple[str, ...] = (
    "D:20240315120000Z",
    "D:20240315120000+05'30'",
    "D:20240315120000-08'00'",
    "D:20231220183040-05'00'",
    "D:19990101000000+12'00'",
    "D:20240315120000+05",
    "D:200912311859",
)

_ROUNDTRIP_IDS = tuple(s.replace("'", "q") for s in _ROUNDTRIP_INPUTS)


@requires_oracle
@pytest.mark.parametrize("date_str", _ROUNDTRIP_INPUTS, ids=list(_ROUNDTRIP_IDS))
def test_parse_format_parse_round_trip_matches_pdfbox(date_str: str) -> None:
    """parse -> to_string -> parse converges, and the final instant matches the
    instant PDFBox parses from the original string."""
    first = to_calendar(date_str)
    assert first is not None
    formatted = DateConverter.to_string(first)
    again = to_calendar(formatted)
    assert again is not None
    # Same absolute instant on both pypdfbox round-trips.
    assert again.timestamp() == first.timestamp()
    # ...and the same instant PDFBox parsed from the original input.
    java = run_probe_text("DateConvertProbe", "parse", date_str)
    java_epoch = int(java.split()[0])
    assert int(first.timestamp() * 1000) == java_epoch
