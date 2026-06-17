"""Live PDFBox differential parse-fuzz for the COS dictionary date-parsing
entry point ``COSDictionary.getDate`` (pypdfbox parity wave 1510).

This pins the COS *layer* date parser as it is actually reached from a parsed
PDF, not the isolated ``DateConverter`` (already covered by
``tests/xmpbox/oracle/test_date_convert_oracle.py``). In PDFBox 3.0.7
``COSDictionary.getDate(COSName)`` delegates straight to
``org.apache.pdfbox.util.DateConverter.toCalendar(COSString)`` — confirmed by
bytecode disassembly (``getDate`` → ``DateConverter.toCalendar``). The full
leniency of the production date parser is therefore visible through ``getDate``.

The Java probe (``CosLexFuzzProbe``) builds a ``COSDictionary`` with a
``COSString`` under ``/D`` and calls ``getDate``. pypdfbox builds the identical
dictionary and calls :meth:`COSDictionary.get_date`. Both emit the same
projection — ``"<epochMillis> <offsetMillis>"`` for a parsed instant (pinning
both the absolute instant and the zone offset PDFBox chose to display) or
``"NULL"`` for input PDFBox cannot parse.

Date strings are passed to the probe as hex of their raw byte form so that
embedded NULs, control bytes, and the ``'`` apostrophes inside PDF timezone
designations survive the shell intact.

WAVE 1510 DIVERGENCE FIXED — before this wave pypdfbox's ``get_date`` used a
private regex (``_PDF_DATE_RE``) that only handled the ``D:YYYYMMDD…`` subset.
It rejected (returned ``None`` where PDFBox parses) every other lenient shape
``DateConverter`` accepts: GMT/UTC-prefixed offsets (``D:…GMT+05:30``,
``D:…UTC``), ISO 8601 (``2024-03-15T12:00:00Z``), named-month forms
(``26 May 2020 11:25:10``), and a ``Z`` followed by an explicit offset
(``…Z05'00'``, which the old regex mis-parsed as UTC instead of +05:00).
``get_date`` now delegates to the faithful
``pypdfbox.xmpbox.date_converter.to_calendar`` port, matching ``getDate``.

The COSString literal/hex/name parse surface and the number-token surface this
wave's brief also lists are already comprehensively oracle-pinned —
``test_parse_literal_name_oracle`` (escapes / octal overflow / line
continuation / name ``#``-hex), ``test_hex_string_parse_oracle`` (odd digits /
whitespace / garbage / missing ``>``), ``test_scalar_parse_edge_oracle`` and
``test_cos_number_oracle`` / ``test_cos_number_overflow_oracle`` /
``test_exp_notation_oracle`` (signs / dots / exponent leniency / huge ints) —
so this wave targets the one unpinned sub-surface: the COS-layer date entry.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_string import COSString
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------------- #
# Corpus. Each entry is (id, raw date bytes). The raw bytes are exactly what a
# COSString parsed out of a PDF would hold; both sides build COSString(raw) and
# read it back via getDate / get_date.
# --------------------------------------------------------------------------- #


def _b(s: str) -> bytes:
    return s.encode("latin-1")


_CASES: tuple[tuple[str, bytes], ...] = (
    # ---- well-formed PDF date strings (the subset the old regex handled) ----
    ("plain_utc", _b("D:20240315120000")),
    ("no_prefix", _b("20240315120000")),
    ("trailing_Z", _b("D:20240315120000Z")),
    ("offset_quoted_pos", _b("D:20240315120000+05'30'")),
    ("offset_quoted_neg", _b("D:20240315120000-08'00'")),
    ("offset_unquoted", _b("D:20240315120000+0530")),
    ("offset_hours_only", _b("D:20240315120000+05")),
    ("offset_hours_only_neg", _b("D:20240315120000-05")),
    # ---- missing / partial apostrophes ----
    ("offset_missing_trail_apos", _b("D:20240315120000+05'30")),
    ("offset_trail_apos_no_min", _b("D:20240315120000+0530'")),
    ("offset_hour_then_apos", _b("D:20240315120000+05'")),
    # ---- Z followed by an explicit offset (old regex mis-parsed as UTC) ----
    ("Z_then_zero_offset", _b("D:20240315120000Z00'00'")),
    ("Z_then_offset", _b("D:20240315120000Z05'00'")),
    # ---- partial dates (truncated trailing fields default) ----
    ("year_only", _b("D:2009")),
    ("year_month", _b("D:200912")),
    ("year_month_day", _b("D:20091231")),
    ("through_hour", _b("D:2009123118")),
    ("through_minute", _b("D:200912311859")),
    ("ymd_only", _b("D:20240315")),
    ("year_only_no_prefix", _b("2024")),
    # ---- GMT / UTC-prefixed forms (old regex REJECTED these) ----
    ("gmt_colon_offset", _b("D:20240315120000GMT+05:30")),
    ("utc_suffix", _b("D:20240315120000UTC")),
    ("bare_gmt_only", _b("GMT+05:30")),  # PDFBox rejects (null)
    # ---- out-of-range TZ designations: folded modulo a day, NOT rejected ----
    ("tz_plus_24", _b("D:20240315120000+24'00'")),
    ("tz_plus_99", _b("D:20240315120000+99'00'")),
    ("tz_minus_99", _b("D:20240315120000-99'00'")),
    # ---- edge-but-valid TZ ----
    ("tz_plus_14", _b("D:20240315120000+14'00'")),
    ("tz_plus_13", _b("D:20240315120000+13'00'")),
    # ---- setLenient(false) calendar rejects (PDFBox returns null) ----
    ("second_60", _b("D:20240315120060")),
    ("second_60_Z", _b("D:20240315120060Z")),
    ("second_60_at_2359", _b("D:20240315235960")),
    ("feb_31", _b("D:20240231120000")),
    ("hour_24", _b("D:2024031524")),
    ("month_13", _b("D:202413")),
    ("day_00", _b("D:20240300")),
    ("year_0", _b("D:00001231")),
    ("six_digit_year_shape", _b("D:990101000000")),
    # ---- valid leap day + boundary year ----
    ("leap_day", _b("D:20240229120000")),
    ("max_year", _b("D:99991231235959")),
    # ---- ISO 8601 shapes (old regex REJECTED these) ----
    ("iso_Z", _b("2024-03-15T12:00:00Z")),
    ("iso_offset", _b("2024-03-15T12:00:00+05:30")),
    ("iso_naive", _b("2024-03-15T12:00:00")),
    # ---- alpha-led / named-TZ shapes (old regex REJECTED the parseable one) ----
    ("named_month", _b("26 May 2020 11:25:10")),
    ("full_named", _b("Friday July 6 17:22:1 GMT+08:00 1979")),
    ("named_rejected", _b("Mon Sept 24 11:22:33 2007")),  # PDFBox rejects (null)
    # ---- trailing residue (PDFBox rejects — index != length) ----
    ("trailing_residue", _b("20070430193647+713'00' illegal tz hr")),
    ("trailing_word", _b("D:20240315120000 trailing")),
    # ---- pure garbage / non-date strings (getDate returns null) ----
    ("pure_garbage", _b("garbage")),
    ("not_a_date_text", _b("not a date at all")),
    ("empty", b""),
    ("bare_prefix", _b("D:")),
    ("prefix_then_spaces", _b("D:    ")),
    ("whitespace_only", _b("   ")),
    # ---- embedded control / NUL bytes (real-world corruption) ----
    ("leading_nul", b"\x00" + _b("D:20240315120000")),
    ("trailing_nul", _b("D:20240315120000") + b"\x00"),
    ("nul_mid_date", _b("D:202403") + b"\x00" + _b("15120000")),
    ("tab_in_date", _b("D:2024\t0315120000")),
    # ---- leading / trailing whitespace around an otherwise valid date ----
    ("leading_ws", _b("  D:20240315120000")),
    ("trailing_ws", _b("D:20240315120000  ")),
    # ---- lowercase z (NOT the uppercase Z marker) ----
    ("lowercase_z", _b("D:20240315120000z")),
    # ---- offset with seconds-ish over-long field ----
    ("offset_overlong", _b("D:20240315120000+0530000")),
)

_IDS = [c[0] for c in _CASES]
_RAW = [c[1] for c in _CASES]


def _py_fingerprint(raw: bytes) -> str:
    """pypdfbox ``COSDictionary.get_date`` rendered as the probe projection.

    Returns ``"NULL"`` when ``get_date`` returns ``None`` (absent / not a
    COSString / unparseable), else ``"<epochMillis> <offsetMillis>"`` matching
    the Java ``getDate`` calendar's instant + displayed offset.
    """
    dictionary = COSDictionary()
    dictionary.set_item(COSName.get_pdf_name("D"), COSString(raw))
    parsed = dictionary.get_date("D")
    if parsed is None:
        return "NULL"
    epoch = int(parsed.timestamp() * 1000)
    off = parsed.utcoffset() or timedelta()
    return f"{epoch} {int(off.total_seconds() * 1000)}"


@requires_oracle
@pytest.mark.parametrize("raw", _RAW, ids=_IDS)
def test_get_date_matches_pdfbox(raw: bytes) -> None:
    java = run_probe_text("CosLexFuzzProbe", raw.hex())
    py = _py_fingerprint(raw)
    assert py == java


# --------------------------------------------------------------------------- #
# Focused regression pins for the wave-1510 delegation fix — these are the
# shapes the old private regex got wrong; assert the concrete parsed value so
# the pin documents the fixed behaviour even on a machine without the oracle.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "expected_offset_minutes"),
    [
        (_b("D:20240315120000GMT+05:30"), 330),
        (_b("D:20240315120000Z05'00'"), 300),
        (_b("2024-03-15T12:00:00+05:30"), 330),
        (_b("D:20240315120000UTC"), 0),
        (_b("26 May 2020 11:25:10"), 0),
    ],
    ids=["gmt_offset", "Z_then_offset", "iso_offset", "utc_suffix", "named_month"],
)
def test_lenient_shapes_now_parsed(raw: bytes, expected_offset_minutes: int) -> None:
    dictionary = COSDictionary()
    dictionary.set_item(COSName.get_pdf_name("D"), COSString(raw))
    parsed = dictionary.get_date("D")
    assert parsed is not None
    off = parsed.utcoffset() or timedelta()
    assert int(off.total_seconds() // 60) == expected_offset_minutes


def test_non_cos_string_value_returns_default() -> None:
    """A non-COSString value (or absent key) yields the default, mirroring
    PDFBox's ``getDate`` which only parses ``COSString`` entries."""
    from datetime import UTC, datetime

    from pypdfbox.cos.cos_integer import COSInteger

    fallback = datetime(2000, 1, 1, tzinfo=UTC)
    dictionary = COSDictionary()
    dictionary.set_item(COSName.get_pdf_name("D"), COSInteger.get(123))
    assert dictionary.get_date("D") is None
    assert dictionary.get_date("D", fallback) is fallback
    assert dictionary.get_date("Missing", fallback) is fallback
