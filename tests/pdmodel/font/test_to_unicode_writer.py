"""Tests for :mod:`pypdfbox.pdmodel.font.to_unicode_writer`.

Ports ``TestToUnicodeWriter.java`` from upstream PDFBox
(``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/TestToUnicodeWriter.java``)
to pytest, plus a small set of hand-written tests for behaviour
upstream covers indirectly.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.pdmodel.font.to_unicode_writer import ToUnicodeWriter

# ---------------------------------------------------------------------------
# Ported upstream tests.
# ---------------------------------------------------------------------------


def test_cmap_ligatures() -> None:
    """Port of upstream ``testCMapLigatures`` (TestToUnicodeWriter line 36)."""
    writer = ToUnicodeWriter()
    writer.add(0x400, "a")
    writer.add(0x401, "b")
    writer.add(0x402, "ff")
    writer.add(0x403, "fi")
    writer.add(0x404, "ffl")
    out = io.BytesIO()
    writer.write_to(out)
    output = out.getvalue().decode("ascii")
    assert "4 beginbfrange" in output
    assert "<0402> <0402> <00660066>" in output
    assert "<0403> <0403> <00660069>" in output
    assert "<0404> <0404> <00660066006C>" in output


def test_cmap_cid_overflow() -> None:
    """Port of upstream ``testCMapCIDOverflow``."""
    writer = ToUnicodeWriter()
    writer.add(0x3FF, "6")
    writer.add(0x400, "7")
    out = io.BytesIO()
    writer.write_to(out)
    output = out.getvalue().decode("ascii")
    assert "2 beginbfrange" in output
    assert "<03FF> <03FF> <0036>" in output
    assert "<0400> <0400> <0037>" in output


def test_cmap_string_overflow() -> None:
    """Port of upstream ``testCMapStringOverflow``."""
    writer = ToUnicodeWriter()
    writer.add(0x3FF, chr(0x04FF))
    writer.add(0x400, chr(0x0500))
    out = io.BytesIO()
    writer.write_to(out)
    output = out.getvalue().decode("ascii")
    assert "2 beginbfrange" in output
    assert "<03FF> <03FF> <04FF>" in output
    assert "<0400> <0400> <0500>" in output


def test_cmap_surrogates() -> None:
    """Port of upstream ``testCMapSurrogates``."""
    writer = ToUnicodeWriter()
    writer.add(0x300, chr(0x2F874))
    writer.add(0x301, chr(0x2F876))
    writer.add(0x304, chr(0x2F884))
    writer.add(0x305, chr(0x2F885))
    writer.add(0x306, chr(0x2F886))
    out = io.BytesIO()
    writer.write_to(out)
    output = out.getvalue().decode("ascii")
    assert "3 beginbfrange" in output
    assert "<0300> <0300> <D87EDC74>" in output
    assert "<0301> <0301> <D87EDC76>" in output
    assert "<0304> <0306> <D87EDC84>" in output


def test_allow_cid_to_unicode_range() -> None:
    """Port of upstream ``testAllowCIDToUnicodeRange``."""
    six = (0x03FF, "6")
    seven = (0x0400, "7")
    eight = (0x0401, "8")
    assert ToUnicodeWriter.allow_cid_to_unicode_range(None, seven) is False
    assert ToUnicodeWriter.allow_cid_to_unicode_range(six, None) is False
    assert ToUnicodeWriter.allow_cid_to_unicode_range(six, seven) is False
    assert ToUnicodeWriter.allow_cid_to_unicode_range(seven, eight) is True


def test_allow_code_range() -> None:
    """Port of upstream ``testAllowCodeRange``."""
    # Denied progressions (negative).
    assert ToUnicodeWriter.allow_code_range(0x000F, 0x0007) is False
    assert ToUnicodeWriter.allow_code_range(0x00FF, 0x0000) is False
    assert ToUnicodeWriter.allow_code_range(0x03FF, 0x0300) is False
    assert ToUnicodeWriter.allow_code_range(0x0401, 0x0400) is False
    assert ToUnicodeWriter.allow_code_range(0xFFFF, 0x0000) is False
    # Denied (non sequential).
    assert ToUnicodeWriter.allow_code_range(0x0000, 0x0000) is False
    assert ToUnicodeWriter.allow_code_range(0x0000, 0x000F) is False
    assert ToUnicodeWriter.allow_code_range(0x0000, 0x007F) is False
    assert ToUnicodeWriter.allow_code_range(0x0000, 0x00FF) is False
    assert ToUnicodeWriter.allow_code_range(0x0007, 0x000F) is False
    assert ToUnicodeWriter.allow_code_range(0x007F, 0x00FF) is False
    assert ToUnicodeWriter.allow_code_range(0x00FF, 0x00FF) is False
    # Denied (overflow).
    assert ToUnicodeWriter.allow_code_range(0x00FF, 0x0100) is False
    assert ToUnicodeWriter.allow_code_range(0x01FF, 0x0200) is False
    assert ToUnicodeWriter.allow_code_range(0x03FF, 0x0400) is False
    assert ToUnicodeWriter.allow_code_range(0x07FF, 0x0800) is False
    assert ToUnicodeWriter.allow_code_range(0x0FFF, 0x1000) is False
    assert ToUnicodeWriter.allow_code_range(0x1FFF, 0x2000) is False
    assert ToUnicodeWriter.allow_code_range(0x3FFF, 0x4000) is False
    assert ToUnicodeWriter.allow_code_range(0x7FFF, 0x8000) is False
    # Allowed.
    for prev, nxt in [
        (0x00, 0x01),
        (0x01, 0x02),
        (0x03, 0x04),
        (0x07, 0x08),
        (0x0E, 0x0F),
        (0x1F, 0x20),
        (0x3F, 0x40),
        (0x7F, 0x80),
        (0xFE, 0xFF),
        (0x03FE, 0x03FF),
        (0x0400, 0x0401),
        (0xFFFE, 0xFFFF),
    ]:
        assert ToUnicodeWriter.allow_code_range(prev, nxt) is True


def test_allow_destination_range() -> None:
    """Port of upstream ``testAllowDestinationRange``."""
    assert ToUnicodeWriter.allow_destination_range("", "") is False
    assert ToUnicodeWriter.allow_destination_range("0", "") is False
    assert ToUnicodeWriter.allow_destination_range("", "0") is False
    assert ToUnicodeWriter.allow_destination_range("0", "A") is False
    assert ToUnicodeWriter.allow_destination_range("A", "a") is False
    # Overflow across byte boundary.
    assert ToUnicodeWriter.allow_destination_range("ÿ", "Ā") is False
    # Sequential.
    for prev, nxt in [
        (" ", "!"),
        ("(", ")"),
        ("0", "1"),
        ("a", "b"),
        ("A", "B"),
        ("À", "Á"),
        ("þ", "ÿ"),
    ]:
        assert ToUnicodeWriter.allow_destination_range(prev, nxt) is True
    # Ligatures (multi-char dest strings).
    assert ToUnicodeWriter.allow_destination_range("ff", "fi") is False


# ---------------------------------------------------------------------------
# Hand-written tests covering behaviour upstream tests only touch indirectly.
# ---------------------------------------------------------------------------


def test_add_rejects_out_of_range_cid() -> None:
    writer = ToUnicodeWriter()
    with pytest.raises(ValueError):
        writer.add(-1, "x")
    with pytest.raises(ValueError):
        writer.add(0x10000, "x")


def test_add_rejects_empty_text() -> None:
    writer = ToUnicodeWriter()
    with pytest.raises(ValueError):
        writer.add(0, "")


def test_write_to_emits_header_and_footer() -> None:
    writer = ToUnicodeWriter()
    writer.add(0x10, "A")
    out = io.BytesIO()
    writer.write_to(out)
    text = out.getvalue().decode("ascii")
    assert "/CIDInit /ProcSet findresource begin" in text
    assert "begincmap" in text
    assert "endcmap" in text
    assert "CMapName currentdict /CMap defineresource pop" in text


def test_set_w_mode_emits_vertical_directive() -> None:
    writer = ToUnicodeWriter()
    writer.set_w_mode(1)
    writer.add(0x10, "A")
    out = io.BytesIO()
    writer.write_to(out)
    text = out.getvalue().decode("ascii")
    assert "/WMode /1 def" in text
