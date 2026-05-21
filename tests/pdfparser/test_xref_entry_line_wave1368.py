"""Wave 1368 — traditional ``xref`` entry-line parsing edges.

The xref-entry line per ISO 32000-1 §7.5.4 is strictly 20 bytes:
``oooooooooo ggggg t \n``. Real producers often relax that —
trim trailing space, use bare LF, etc. The pypdfbox parser
splits on whitespace rather than slicing fixed widths, so it
tolerates these variants. Tests probe the boundary:

* Standard 20-byte form with trailing space + LF.
* Compact "<offset> <gen> <flag>" with no trailing space.
* Malformed entries (missing flag, extra tokens, non-numeric).
* Tab-separated columns (some hand-edited PDFs).
* CRLF line ending.
* Mixed-width but valid (offset < 10 digits, gen < 5 digits).
"""

from __future__ import annotations

import pytest

from pypdfbox.pdfparser import PDFParseError
from pypdfbox.pdfparser.cos_parser import _parse_xref_entry_line


def test_standard_20_byte_entry_in_use() -> None:
    """Canonical form per spec — 10-digit offset, 5-digit generation,
    flag, space, LF."""
    line = b"0000000123 00000 n "
    offset, gen, flag = _parse_xref_entry_line(line)
    assert offset == 123
    assert gen == 0
    assert flag == "n"


def test_standard_20_byte_entry_free_with_high_generation() -> None:
    """Free-root sentinel form."""
    line = b"0000000000 65535 f "
    offset, gen, flag = _parse_xref_entry_line(line)
    assert offset == 0
    assert gen == 65535
    assert flag == "f"


def test_compact_form_without_trailing_space_accepted() -> None:
    """Compact form (LF only, no trailing space) is common in tooling
    output — the split-on-whitespace parser accepts it."""
    line = b"0000000123 00000 n"
    offset, gen, flag = _parse_xref_entry_line(line)
    assert (offset, gen, flag) == (123, 0, "n")


def test_tab_separated_columns_accepted() -> None:
    """Some hand-rolled producers use tabs instead of spaces. Since the
    parser uses ``bytes.split()`` (no argument), any whitespace works."""
    line = b"0000000007\t00000\tn"
    offset, gen, flag = _parse_xref_entry_line(line)
    assert (offset, gen, flag) == (7, 0, "n")


def test_crlf_terminator_handled() -> None:
    """A CRLF terminator must not pollute the trailing flag token."""
    line = b"0000000999 00001 n \r"
    # The trailing CR is whitespace -> ignored by split().
    offset, gen, flag = _parse_xref_entry_line(line)
    assert (offset, gen, flag) == (999, 1, "n")


def test_missing_flag_field_rejected() -> None:
    """Only two tokens (offset + generation) is malformed — no flag."""
    line = b"0000000099 00000"
    with pytest.raises(PDFParseError, match="malformed xref entry"):
        _parse_xref_entry_line(line)


def test_extra_token_after_flag_rejected() -> None:
    """A fourth token is malformed — the spec only permits three."""
    line = b"0000000099 00000 n EXTRA"
    with pytest.raises(PDFParseError, match="malformed xref entry"):
        _parse_xref_entry_line(line)


def test_non_numeric_offset_rejected() -> None:
    """If the offset isn't decimal, fail loudly."""
    line = b"deadbeef00 00000 n"
    with pytest.raises(PDFParseError, match="malformed xref entry"):
        _parse_xref_entry_line(line)


def test_non_numeric_generation_rejected() -> None:
    line = b"0000000099 abcde n"
    with pytest.raises(PDFParseError, match="malformed xref entry"):
        _parse_xref_entry_line(line)


def test_multi_char_flag_rejected() -> None:
    """The flag column is exactly one character — ``nn`` is malformed."""
    line = b"0000000099 00000 nn"
    with pytest.raises(PDFParseError, match="malformed xref entry flag"):
        _parse_xref_entry_line(line)


def test_shorter_numeric_widths_still_accepted() -> None:
    """Even if a producer skips the zero-padding, the parser must
    accept short forms — the spec doesn't strictly mandate fixed
    widths once the line is whitespace-tokenized."""
    line = b"99 0 n"
    offset, gen, flag = _parse_xref_entry_line(line)
    assert (offset, gen, flag) == (99, 0, "n")
