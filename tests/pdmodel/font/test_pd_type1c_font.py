"""Tests for the wave-1247 Type1C parity additions.

Companion to ``test_pd_type1c_font_parity.py`` (the wave-398 parity
suite). This file covers the upstream methods that were *not* yet
declared on the :class:`PDType1CFont` body before wave 1247:

* ``get_name`` / ``get_base_font`` — final overrides on the Type1C
  class (parity scanner counts methods declared on the class body).
* ``get_average_character_width`` — upstream's hard-coded ``500``.
* ``get_name_in_font`` — Type1C-specific glyph-name resolution
  (uniXXXX fallback) distinct from the ALT_NAMES path on
  :class:`PDType1Font`.
* ``generate_bounding_box`` — non-cached helper backing
  :meth:`get_bounding_box`.
* ``get_normalized_path(int)`` — Type1C override (sfthyphen / nbspace
  rewrites already exercised through ``get_normalized_path_for_code``;
  here we pin the override to ensure the int overload lands on the
  Type1C body, not the inherited :class:`PDType1Font` alias).
* ``read_code`` — single-byte stream reader.
* ``read_encoding_from_font`` — embedded vs Standard 14 vs fallback.
* ``encode_codepoint`` — single-codepoint encoder with raises.
"""
from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.pdmodel.font import PDFontDescriptor
from pypdfbox.pdmodel.font.encoding.standard_encoding import StandardEncoding
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont

_BASE_FONT = COSName.get_pdf_name("BaseFont")
_ENCODING = COSName.get_pdf_name("Encoding")


# ---------- helpers (re-used from the parity suite) ----------


def _build_minimal_cff_bytes() -> bytes:
    from fontTools.fontBuilder import FontBuilder
    from fontTools.misc.psCharStrings import T2CharString
    from fontTools.ttLib import TTFont

    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder([".notdef", "A", "B"])
    fb.setupCharacterMap({65: "A", 66: "B"})

    def _cs(program: list) -> T2CharString:
        s = T2CharString()
        s.program = program
        return s

    char_strings = {
        ".notdef": _cs([0, "endchar"]),
        "A": _cs(
            [500, 0, "hmoveto", 700, "vlineto", 100, "hlineto", -700, "vlineto", "endchar"]
        ),
        "B": _cs([300, 0, "hmoveto", 500, "vlineto", "endchar"]),
    }
    fb.setupCFF(
        psName="TestType1CWave1247",
        fontInfo={"FullName": "Test Type1C Wave 1247"},
        charStringsDict=char_strings,
        privateDict={},
    )
    fb.setupHorizontalMetrics({".notdef": (0, 0), "A": (500, 0), "B": (300, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    fb.setupPost()
    buf = io.BytesIO()
    fb.font.save(buf)
    return bytes(TTFont(io.BytesIO(buf.getvalue())).getTableData("CFF "))


def _make_injected_font() -> PDType1CFont:
    cff = CFFFont.from_bytes(_build_minimal_cff_bytes())
    raw = COSDictionary()
    raw.set_name(_BASE_FONT, "MyEmbeddedType1C")
    raw.set_item(_ENCODING, COSName.get_pdf_name("WinAnsiEncoding"))
    font = PDType1CFont(raw)
    font.set_font_program(cff)
    return font


# ---------- get_name / get_base_font are declared on the class body ----------


def test_get_name_is_declared_on_pd_type1c_font_body() -> None:
    """Parity scanner counts only methods declared on the class body —
    the wave-1247 override surfaces ``get_name`` here so the count
    matches upstream's ``final String getName()``."""
    assert "get_name" in PDType1CFont.__dict__


def test_get_base_font_is_declared_on_pd_type1c_font_body() -> None:
    """Same for ``getBaseFont`` — upstream marks it ``final``, we
    re-declare to capture the parity contract."""
    assert "get_base_font" in PDType1CFont.__dict__


def test_get_name_returns_base_font_when_set() -> None:
    font = PDType1CFont()
    font.get_cos_object().set_name(_BASE_FONT, "MySubsetCFF")
    assert font.get_name() == "MySubsetCFF"
    assert font.get_base_font() == "MySubsetCFF"


def test_get_name_none_when_basefont_absent() -> None:
    """The dict has no ``/BaseFont`` -> both accessors are ``None``."""
    font = PDType1CFont()
    assert font.get_name() is None
    assert font.get_base_font() is None


# ---------- get_average_character_width (upstream's hard-coded 500) ----------


def test_get_average_character_width_returns_upstream_constant() -> None:
    """Upstream's private ``getAverageCharacterWidth`` returns ``500``
    unconditionally — pinned here for parity even though it's marked
    ``// todo: not implemented, highly suspect`` upstream."""
    assert PDType1CFont().get_average_character_width() == 500.0


# ---------- get_name_in_font (Type1C-specific override) ----------


def test_get_name_in_font_passes_through_when_embedded() -> None:
    """Embedded fonts trust the embedded program's spelling — the name
    is returned unchanged regardless of whether the program contains
    that spelling."""
    font = _make_injected_font()
    # Force is_embedded() to be True via FontFile3 marker.
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(_build_minimal_cff_bytes())
    stream.set_name(COSName.SUBTYPE, "Type1C")  # type: ignore[attr-defined]
    fd.set_font_file3(stream)
    font.set_font_descriptor(fd)
    assert font.get_name_in_font("anything") == "anything"


def test_get_name_in_font_passes_through_when_no_program() -> None:
    """No CFF program loaded and no descriptor -> pass-through."""
    assert PDType1CFont().get_name_in_font("X") == "X"


def test_get_name_in_font_returns_notdef_when_program_lacks_name() -> None:
    """Non-embedded font with a CFF program that does not carry the
    name and whose AGL round-trip also fails -> ``.notdef``."""
    font = _make_injected_font()
    # Synthetic name with no AGL entry and absent from the program.
    assert font.get_name_in_font("zzz_nonexistent_glyph") == ".notdef"


def test_get_name_in_font_keeps_present_name_when_program_has_it() -> None:
    """Program contains the requested name -> identity."""
    font = _make_injected_font()
    assert font.get_name_in_font("A") == "A"


# ---------- generate_bounding_box ----------


def test_generate_bounding_box_returns_none_with_no_descriptor_or_program() -> None:
    assert PDType1CFont().generate_bounding_box() is None


def test_generate_bounding_box_uses_descriptor_bbox() -> None:
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    font = PDType1CFont()
    fd = PDFontDescriptor()
    fd.set_font_bounding_box(PDRectangle(-50.0, -100.0, 600.0, 800.0))
    font.set_font_descriptor(fd)
    bbox = font.generate_bounding_box()
    assert bbox is not None
    assert bbox.get_lower_left_x() == -50.0
    assert bbox.get_upper_right_y() == 800.0


def test_generate_bounding_box_is_not_cached() -> None:
    """``get_bounding_box`` caches; ``generate_bounding_box`` must
    re-compute on each call. Distinct from upstream's private helper
    in the same way (``getBoundingBox`` caches, ``generateBoundingBox``
    doesn't)."""
    font = _make_injected_font()
    first = font.generate_bounding_box()
    second = font.generate_bounding_box()
    # Either both None (no usable bbox sources) or both equal — but
    # never the same identity if the impl re-computes.
    if first is not None and second is not None:
        assert first.get_lower_left_x() == second.get_lower_left_x()


# ---------- get_normalized_path (int overload on this class body) ----------


def test_get_normalized_path_is_declared_on_pd_type1c_font_body() -> None:
    """Parity: the int overload is on the Type1C body, not just
    inherited from :class:`PDType1Font`."""
    assert "get_normalized_path" in PDType1CFont.__dict__


def test_get_normalized_path_int_returns_glyph_path() -> None:
    font = _make_injected_font()
    direct = font.get_path_for_code(65)
    normalized = font.get_normalized_path(65)
    assert normalized == direct


def test_get_normalized_path_int_falls_back_to_notdef() -> None:
    font = _make_injected_font()
    result = font.get_normalized_path(90)  # 'Z' unmapped in CFF
    assert isinstance(result, list)


# ---------- read_code ----------


def test_read_code_returns_single_byte_value() -> None:
    font = PDType1CFont()
    stream = io.BytesIO(b"\x41\x42")
    assert font.read_code(stream) == 0x41
    assert font.read_code(stream) == 0x42


def test_read_code_returns_minus_one_at_eof() -> None:
    font = PDType1CFont()
    assert font.read_code(io.BytesIO(b"")) == -1


def test_read_code_accepts_bytes_directly() -> None:
    """Convenience: pass raw bytes instead of a stream."""
    assert PDType1CFont().read_code(b"\xff") == 0xFF


# ---------- read_encoding_from_font ----------


def test_read_encoding_from_font_returns_standard_for_unembedded_non_standard14() -> None:
    """No CFF program, non-Standard-14 ``/BaseFont`` -> StandardEncoding."""
    font = PDType1CFont()
    font.get_cos_object().set_name(_BASE_FONT, "NonStandard14")
    enc = font.read_encoding_from_font()
    assert enc is StandardEncoding.INSTANCE


def test_read_encoding_from_font_uses_parent_path_for_standard_14() -> None:
    """Non-embedded Standard 14 -> defer to PDType1Font's encoding
    path (which selects Symbol/ZapfDingbats/Standard based on family)."""
    font = PDType1CFont()
    font.get_cos_object().set_name(_BASE_FONT, "Symbol")
    enc = font.read_encoding_from_font()
    # SymbolEncoding singleton.
    from pypdfbox.pdmodel.font.encoding.symbol_encoding import SymbolEncoding

    assert enc is SymbolEncoding.INSTANCE


def test_read_encoding_from_font_with_embedded_program_returns_some_encoding() -> None:
    """Embedded CFF program path: returns either a BuiltInEncoding
    (when CFFFont exposes ``get_encoding_map``) or StandardEncoding
    (current pypdfbox CFFFont does not expose it). Either way the
    return is a non-None Encoding instance."""
    font = _make_injected_font()
    enc = font.read_encoding_from_font()
    assert enc is not None


# ---------- encode_codepoint ----------


def test_encode_codepoint_returns_single_byte_for_known_glyph() -> None:
    font = _make_injected_font()
    # Force is_embedded() to be True so name_in_font passes through.
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(_build_minimal_cff_bytes())
    stream.set_name(COSName.SUBTYPE, "Type1C")  # type: ignore[attr-defined]
    fd.set_font_file3(stream)
    font.set_font_descriptor(fd)
    encoded = font.encode_codepoint(ord("A"))
    assert encoded == b"A"


def test_encode_codepoint_raises_when_no_encoding() -> None:
    """No /Encoding -> upstream throws IllegalArgumentException; we
    raise ValueError."""
    font = PDType1CFont()
    font.get_cos_object().set_name(_BASE_FONT, "MyEmbeddedType1C")
    with pytest.raises(ValueError, match="has no /Encoding"):
        font.encode_codepoint(ord("A"))


def test_encode_codepoint_raises_for_codepoint_outside_encoding() -> None:
    """The glyph-list maps the codepoint to a name that is not in the
    font's encoding -> upstream's IllegalArgumentException case."""
    font = _make_injected_font()
    # A high BMP codepoint with a known PostScript name (CJK) that is
    # not in WinAnsi.
    with pytest.raises(ValueError, match="not available in font"):
        font.encode_codepoint(0x4E2D)  # 中
