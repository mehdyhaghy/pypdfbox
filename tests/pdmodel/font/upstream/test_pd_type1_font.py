"""Upstream-derived tests for ``PDType1Font``.

PDFBox does not ship a dedicated ``PDType1FontTest`` class — the Type 1
specific behaviour is exercised inside the broader ``PDFontTest`` and via
``TestFontEmbedding`` / ``TestFontEncoding``. This file ports the focused
Type 1 cases from those suites along with the static-helper tests that
guard the ``repairLength1`` / ``repairLength2`` / ``findBinaryOffsetAfterExec``
helpers (PDFBOX-2350, PDFBOX-3475, PDFBOX-3677).

Skipped (Java-only plumbing):

* ``testPDFox4318`` (caching of the IllegalArgumentException across
  ``encode`` calls) — relies on the embedded ``PDType1FontEmbedder``
  pipeline which the Python port does not yet wire up; behaviour is
  covered indirectly by ``test_get_glyph_width`` /
  ``test_encode_unmapped_codepoint``.
* TrueType-collection tests in PDFontTest.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font import PDType1Font

_BASE_FONT = COSName.get_pdf_name("BaseFont")


# ---------- repairLength1 / findBinaryOffsetAfterExec (PDFBOX-2350 / 3677) ----------


def test_find_binary_offset_after_exec_locates_token() -> None:
    """When the buffer carries an ``exec`` token, the helper returns the
    offset of the first non-whitespace byte after it. Mirrors upstream
    ``PDType1Font.findBinaryOffsetAfterExec``."""
    payload = b"...exec\r\n\x80binary"
    offset = PDType1Font.find_binary_offset_after_exec(payload, len(payload) - 4)
    # 'exec' starts at index 3; offset returned is past the CR/LF whitespace.
    assert offset == payload.index(b"\x80")


def test_find_binary_offset_after_exec_returns_zero_when_missing() -> None:
    """No ``exec`` token in the search window → returns 0 to signal
    that the caller should try the brute-force scan."""
    assert PDType1Font.find_binary_offset_after_exec(b"....NOEXEC...", 8) == 0


def test_find_binary_offset_after_exec_skips_whitespace_run() -> None:
    """Trailing CR / LF / SP / HT after ``exec`` are all consumed."""
    payload = b"  exec\r\n \t\x42rest"
    offset = PDType1Font.find_binary_offset_after_exec(payload, len(payload) - 4)
    assert offset == payload.index(b"\x42")


def test_repair_length1_returns_input_when_consistent() -> None:
    """When ``length1`` already coincides with the ``exec`` boundary,
    no repair is performed."""
    # A short cleartext-only buffer where length1 already lines up with
    # the byte after exec + whitespace.
    payload = b"%!PS\n... currentfile eexec\r\n"
    font = PDType1Font()
    repaired = font.repair_length1(payload, len(payload))
    assert repaired == len(payload)


def test_repair_length1_repairs_truncated_length(caplog) -> None:
    """A length1 that overshoots the real ``exec`` boundary is replaced
    by the helper-discovered offset and a warning is logged."""
    cleartext = b"%! Type1\n... currentfile eexec\r\n"
    payload = cleartext + b"\x80\x01\x02\x03\x04binary-segment"
    font = PDType1Font()
    # Pretend /Length1 lies past the real boundary.
    repaired = font.repair_length1(payload, len(payload))
    assert repaired == cleartext.index(b"eexec\r\n") + len(b"eexec") + 2
    assert repaired < len(payload)


# ---------- repairLength2 (PDFBOX-3475) ----------


def test_repair_length2_returns_input_when_in_range() -> None:
    payload = b"x" * 100
    font = PDType1Font()
    assert font.repair_length2(payload, 40, 30) == 30


def test_repair_length2_repairs_negative_length() -> None:
    """A negative ``/Length2`` triggers a fallback to ``len(data) - length1``."""
    payload = b"x" * 100
    font = PDType1Font()
    assert font.repair_length2(payload, 40, -7) == 60


def test_repair_length2_repairs_oversized_length() -> None:
    """``/Length2`` larger than the available tail is clamped."""
    payload = b"x" * 100
    font = PDType1Font()
    assert font.repair_length2(payload, 40, 9999) == 60


# ---------- get_font_box_font alias ----------


def test_get_font_box_font_aliases_get_type1_font() -> None:
    """``get_font_box_font`` and ``get_type1_font`` resolve to the same
    embedded program. Mirrors upstream ``PDType1Font.getFontBoxFont``
    which returns the ``FontBoxFont`` interface — in our port both
    funnel through :class:`Type1Font`."""
    font = PDType1Font()
    assert font.get_font_box_font() is font.get_type1_font()


# ---------- get_normalized_path(int) overload ----------


def test_get_normalized_path_aliases_for_code_variant() -> None:
    """``get_normalized_path(code)`` is the upstream-named alias of
    :meth:`get_normalized_path_for_code`."""
    font = PDType1Font()
    # No /Encoding → both return [].
    assert font.get_normalized_path(65) == font.get_normalized_path_for_code(65)


# ---------- get_font_matrix default ----------


def test_get_font_matrix_default_for_no_program() -> None:
    """No embedded program → 1/1000 default per PDF 32000-1 §9.2.4.
    Mirrors upstream ``PDType1Font.getFontMatrix`` fallback."""
    font = PDType1Font()
    matrix = font.get_font_matrix()
    assert matrix == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


def test_get_font_matrix_cached_across_calls() -> None:
    """Repeated calls return equal lists (cached internally)."""
    font = PDType1Font()
    first = font.get_font_matrix()
    second = font.get_font_matrix()
    assert first == second
    # Independent list copies so mutation by callers doesn't poison the cache.
    first[0] = 999.0
    assert font.get_font_matrix()[0] == 0.001


# ---------- get_bounding_box ----------


def test_get_bounding_box_returns_descriptor_bbox_when_non_zero() -> None:
    """A non-zero ``/FontBBox`` on the descriptor is returned verbatim.
    Mirrors upstream ``PDType1Font.generateBoundingBox`` first branch."""
    from pypdfbox.pdmodel.font import PDFontDescriptor
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    font = PDType1Font()
    fd = PDFontDescriptor()
    # PDRectangle uses (llx, lly, urx, ury) — direct 4-corner form.
    fd.set_font_bounding_box(PDRectangle(-100.0, -200.0, 1000.0, 1500.0))
    font.set_font_descriptor(fd)
    bbox = font.get_bounding_box()
    assert bbox is not None
    assert bbox.get_lower_left_x() == -100.0
    assert bbox.get_lower_left_y() == -200.0
    assert bbox.get_upper_right_x() == 1000.0
    assert bbox.get_upper_right_y() == 1500.0


def test_get_bounding_box_none_when_nothing_resolvable() -> None:
    """No descriptor, no program → ``None``."""
    assert PDType1Font().get_bounding_box() is None


def test_get_bounding_box_cached() -> None:
    """Result is cached on first access (mirrors upstream ``fontBBox``)."""
    from pypdfbox.pdmodel.font import PDFontDescriptor
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    font = PDType1Font()
    fd = PDFontDescriptor()
    fd.set_font_bounding_box(PDRectangle(0.0, 0.0, 1000.0, 1000.0))
    font.set_font_descriptor(fd)
    first = font.get_bounding_box()
    second = font.get_bounding_box()
    assert first is second


# ---------- read_encoding_from_font (Standard 14 family-default) ----------


def test_read_encoding_from_font_standard_14_returns_win_ansi_encoding() -> None:
    """Non-embedded Standard 14 (non-Symbol/Dingbats) → WinAnsiEncoding.

    Verified against the live PDFBox 3.0.7 oracle (Std14MetricsProbe):
    ``new PDType1Font(FontName.HELVETICA).getEncoding()`` is
    ``WinAnsiEncoding``, not StandardEncoding — Acrobat treats the
    unembedded Latin core fonts as WinAnsi, so code 39 -> ``quotesingle``
    (191) and code 96 -> ``grave`` (333). Using StandardEncoding mapped
    those to ``quoteright`` (222) / ``quoteleft`` (222) and broke the AFM
    per-glyph advance for every disagreeing code."""
    from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import WinAnsiEncoding

    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    enc = font.read_encoding_from_font()
    assert enc is WinAnsiEncoding.INSTANCE


def test_read_encoding_from_font_symbol_returns_symbol_encoding() -> None:
    """Standard 14 Symbol → SymbolEncoding (the AFM's built-in encoding)."""
    from pypdfbox.pdmodel.font.encoding.symbol_encoding import SymbolEncoding

    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Symbol")
    enc = font.read_encoding_from_font()
    assert enc is SymbolEncoding.INSTANCE


def test_read_encoding_from_font_zapf_dingbats_returns_dingbats_encoding() -> None:
    """Standard 14 ZapfDingbats → ZapfDingbatsEncoding."""
    from pypdfbox.pdmodel.font.encoding.zapf_dingbats_encoding import (
        ZapfDingbatsEncoding,
    )

    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "ZapfDingbats")
    enc = font.read_encoding_from_font()
    assert enc is ZapfDingbatsEncoding.INSTANCE


def test_read_encoding_from_font_no_program_returns_standard() -> None:
    """No embedded program and not Standard 14 → StandardEncoding fallback
    (the safe default for Type 1 substitutes per upstream)."""
    from pypdfbox.pdmodel.font.encoding.standard_encoding import StandardEncoding

    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "MyCustomFont")
    enc = font.read_encoding_from_font()
    assert enc is StandardEncoding.INSTANCE


# ---------- encode (PDFBOX-4318: throws on unmapped codepoint) ----------
# This is the one upstream PDType1Font test we can sensibly translate.
# pypdfbox's PDSimpleFont.encode falls back to '?' for unmapped codepoints
# rather than throwing, which is a deliberate divergence (CHANGES.md);
# we verify the divergence here so a regression to throwing wakes us up.


def test_encode_unmapped_codepoint_uses_question_mark() -> None:
    """U+0080 has no glyph in WinAnsiEncoding. Upstream's
    ``PDType1FontEmbedder``-driven encode would throw
    ``IllegalArgumentException``; pypdfbox's encoder falls back to
    ``b'?'`` (matches PDSimpleFont's writer-side fallback)."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica-Bold")
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    encoded = font.encode("")
    # The exact replacement is implementation-detail (currently '?'),
    # but it must NOT raise — that would violate the PDSimpleFont contract.
    assert isinstance(encoded, bytes)
    assert len(encoded) == 1


@pytest.mark.parametrize(
    "char,expected_byte",
    [
        ("A", 0x41),  # WinAnsi A
        ("€", 0x80),  # WinAnsi euro
        (" ", 0x20),
    ],
)
def test_encode_winansi_codepoints(char: str, expected_byte: int) -> None:
    """Smoke-test WinAnsi encode for a handful of codepoints. Mirrors
    the second half of upstream ``testPDFox4318`` (the line that
    successfully encodes ``"€"``)."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    encoded = font.encode(char)
    assert encoded == bytes([expected_byte])


# ---------- get_name override (PDType1Font line 550) ----------


def test_get_name_returns_base_font_value() -> None:
    """``PDType1Font.getName`` is overridden in upstream to return
    ``getBaseFont()`` (line 550). Both methods read the dict's
    ``/BaseFont`` entry."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica-Bold")
    assert font.get_name() == "Helvetica-Bold"
    assert font.get_name() == font.get_base_font()


# ---------- encode cache parity (codeToBytesMap, PDType1Font line 96) ----------


def test_encode_uses_per_codepoint_cache() -> None:
    """Upstream caches the encoded byte for each unicode in
    ``codeToBytesMap`` so repeated encode calls don't re-walk the
    encoding's name->code inverse table. The Python port mirrors this
    exactly via ``_code_to_bytes``."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    # Exercise the cache; second call should pull from `_code_to_bytes`.
    a1 = font.encode("A")
    assert ord("A") in font._code_to_bytes
    a2 = font.encode("A")
    assert a1 == a2 == b"A"
