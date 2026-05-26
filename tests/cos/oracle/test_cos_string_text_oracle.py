"""Live PDFBox differential parity for COSString text decoding + PDF dates.

Two surfaces, one Java probe (``CosStrTextDateProbe``):

* **Text-string decode** — ``COSString.parseHex(hex).getString()`` (PDFBox)
  vs ``COSString.parse_hex(hex).get_string()`` (pypdfbox), compared as the
  hex of each Unicode *code point* (so a UTF-16BE supplementary char that
  Java holds as a surrogate pair and Python holds as one code point compares
  equal). Covers UTF-16BE BOM, UTF-16LE BOM, the full PDFDocEncoding high
  range (bullet / dagger / em-dash / euro / ligatures), ASCII, the two
  undefined slots (0x7F / 0x9F → U+FFFD), the NUL-defaulted 0xAD, and
  truncated / malformed UTF-16 (lenient replacement, not an exception).

* **PDF date parse** — ``DateConverter.toCalendar(str)`` (PDFBox) vs
  pypdfbox's ``_parse_pdf_date`` (the ``D:YYYYMMDDHHmmSSOHH'mm'`` parser
  behind ``COSDictionary.get_date``), both normalised to ISO-8601. Covers
  full / partial dates, ``Z`` / ``+HH'mm'`` / ``-HH'mm'`` / unquoted offsets,
  partial offsets, the leap-second reject, the Feb-31 reject, and the
  modular-reduction of out-of-range TZ offsets.

Documented divergence (asserted as pypdfbox-side, NOT against Java): pypdfbox
strips a UTF-8 BOM (``EF BB BF``) and decodes the remainder as UTF-8 — a
forward-port of PDF 2.0 §7.9.2.2 / PDFBox 4.0; the pinned 3.0.7 baseline has
no such branch and decodes those bytes as PDFDocEncoding. Recorded in
CHANGES.md.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_dictionary import _parse_pdf_date
from pypdfbox.cos.cos_string import COSString
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------------- #
# Text-string decode battery (hex input → expected code-point fingerprint)
# --------------------------------------------------------------------------- #

# Each entry is just a hex byte string; the oracle supplies the expectation.
_TEXT_HEXES: tuple[str, ...] = (
    # UTF-16BE BOM
    "feff0041",  # 'A'
    "feff00410042",  # 'AB'
    "feff004100200042",  # 'A B'
    "feff",  # BOM only → empty
    "feff004100",  # odd trailing byte → lenient U+FFFD
    "feffd83dde00",  # supplementary (emoji) via surrogate pair
    "feff00e9",  # é
    # UTF-16LE BOM
    "fffe4100",  # 'A'
    "fffe41004200",  # 'AB'
    "fffe",  # BOM only → empty
    "fffe41",  # odd trailing byte → lenient U+FFFD
    "fffe3dd800de",  # supplementary via LE surrogate pair
    # ASCII / PDFDocEncoding identity
    "41424300",  # 'ABC' + NUL
    "48656c6c6f",  # 'Hello'
    "00",  # NUL
    "e9",  # é (ISO-8859-1 identity slot)
    # PDFDocEncoding high range deviations (0x80-0xA0)
    "80",  # bullet U+2022
    "81",  # dagger U+2020
    "82",  # double dagger U+2021
    "83",  # horizontal ellipsis U+2026
    "84",  # em dash U+2014
    "85",  # en dash U+2013
    "86",  # script f U+0192
    "8a",  # minus sign U+2212
    "8b",  # per mille U+2030
    "92",  # trade mark U+2122
    "93",  # fi ligature U+FB01
    "95",  # L with stroke U+0141
    "a0",  # euro U+20AC
    "80818283848586",  # run
    # PDFDocEncoding block-1 deviations (0x18-0x1F)
    "18191a1b1c1d1e1f",
    # Undefined slots
    "7f",  # → U+FFFD
    "9f",  # → U+FFFD
    "ad",  # SOFT HYPHEN undefined → U+0000 (int[] default)
    # No-BOM bytes that look like a partial BOM
    "fe",  # single 0xFE → PDFDocEncoding thorn
    "ff",  # single 0xFF → PDFDocEncoding ydieresis
)


def _py_decode_codepoint_hex(hex_text: str) -> str:
    """pypdfbox getString() rendered as space-separated code-point hex."""
    s = COSString.parse_hex(hex_text).get_string()
    return " ".join(format(ord(ch), "x") for ch in s)


@requires_oracle
@pytest.mark.parametrize("hex_text", _TEXT_HEXES, ids=list(_TEXT_HEXES))
def test_cos_string_get_string_matches_pdfbox(hex_text: str) -> None:
    java = run_probe_text("CosStrTextDateProbe", "str", hex_text)
    py = _py_decode_codepoint_hex(hex_text)
    assert py == java


@requires_oracle
def test_utf8_bom_is_documented_divergence() -> None:
    """pypdfbox strips a UTF-8 BOM (PDF 2.0 forward-port); PDFBox 3.0.7 does
    not. We assert the pypdfbox behaviour and confirm Java genuinely differs
    so the divergence stays load-bearing (CHANGES.md)."""
    hex_text = "efbbbf41"  # UTF-8 BOM + 'A'
    py = _py_decode_codepoint_hex(hex_text)
    assert py == "41"  # pypdfbox: BOM stripped, 'A'
    java = run_probe_text("CosStrTextDateProbe", "str", hex_text)
    # PDFBox 3.0.7 decodes the BOM bytes as PDFDocEncoding (ef bb bf 41).
    assert java != py
    assert java == "ef bb bf 41"


# --------------------------------------------------------------------------- #
# PDF date-parse battery
# --------------------------------------------------------------------------- #

_DATE_STRINGS: tuple[str, ...] = (
    # Full date, no offset (UTC default)
    "D:20240315120000",
    "20240315123045",  # no D: prefix
    # Partial dates
    "D:2024",
    "D:202403",
    "D:20240315",
    "D:2024031512",
    "D:202403151230",
    "D:20240315123045",
    # Explicit Z
    "D:20240315123045Z",
    "D:20240315120000Z00'00'",
    # Quoted offsets
    "D:20240315123045+05'30'",
    "D:20240315123045-08'00'",
    "D:20231220183040-05'00'",
    "D:19990101000000+12'00'",
    "D:20240315120000-12'00'",
    "D:20240315120000+14'00'",
    "D:20240315120000+13'00'",
    # Unquoted / partial offsets
    "D:20240315123045+0530",
    "D:20240315123045+05",
    # Out-of-range offsets (modular reduction, NOT an error)
    "D:20240315120000+24'00'",
    "D:20240315120000+99'00'",
    "D:20240315120000-99'00'",
    "D:20240315120000+25'00'",
    "D:20240315120000+48'30'",
    "D:20240315120000+05'99'",
    # Calendar-invalid (setLenient(false) → null)
    "D:20240315123060",  # second 60 (leap-second-style) → null
    "D:20240315123060Z",
    "D:20240231120000",  # Feb 31 → null
    "D:20240229120000",  # Feb 29 2024 (leap) → valid
    "D:2024031524",  # hour 24 → null
    "D:202413",  # month 13 → null
    "D:20240300",  # day 00 → null
    "D:20240015",  # month 00 → null
    # Boundary years
    "D:99991231235959",
    # Unparseable
    "garbage",
    "D:",
)


def _py_date_iso(date_str: str) -> str:
    """pypdfbox _parse_pdf_date normalised to the probe's ISO shape."""
    dt = _parse_pdf_date(date_str)
    if dt is None:
        return "NULL"
    base = dt.strftime("%Y-%m-%dT%H:%M:%S")
    off = dt.utcoffset()
    total_min = 0 if off is None else int(off.total_seconds() // 60)
    sign = "-" if total_min < 0 else "+"
    total_min = abs(total_min)
    return f"{base}{sign}{total_min // 60:02d}:{total_min % 60:02d}"


@requires_oracle
@pytest.mark.parametrize("date_str", _DATE_STRINGS, ids=list(_DATE_STRINGS))
def test_pdf_date_parse_matches_pdfbox(date_str: str) -> None:
    java = run_probe_text("CosStrTextDateProbe", "date", date_str)
    py = _py_date_iso(date_str)
    assert py == java


@requires_oracle
def test_year_zero_is_documented_python_limitation() -> None:
    """Year 0 / BCE is not representable in Python's ``datetime`` (min year 1),
    so pypdfbox returns ``None``. PDFBox likewise returns null here because
    its ``setLenient(false)`` Gregorian calendar rejects a four-zero year, so
    the observable result happens to agree — but the *reason* differs and is
    a standing Python limitation (kept per task brief)."""
    assert _parse_pdf_date("D:00001231") is None
    java = run_probe_text("CosStrTextDateProbe", "date", "D:00001231")
    assert java == "NULL"
