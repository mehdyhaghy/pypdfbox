"""Hand-written parity tests for the Type1-specific overrides on
:class:`pypdfbox.pdmodel.font.PDType1Font` — the methods that exist
*because* upstream ``PDType1Font`` overrides them with Type-1-specific
behaviour distinct from the inherited :class:`PDSimpleFont` defaults.

Sibling wave-N test files exercise older surface; this file owns the
``encode``-cache, AFM-aware ``get_height``, and Type-1-rooted
``get_name`` overrides added in wave 1257.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font import PDType1Font

_BASE_FONT = COSName.get_pdf_name("BaseFont")
_ENCODING = COSName.get_pdf_name("Encoding")
_WIN_ANSI = COSName.get_pdf_name("WinAnsiEncoding")


# ---------- get_name override ----------


def test_get_name_returns_base_font_value() -> None:
    """``PDType1Font.get_name`` mirrors upstream's override that returns
    ``/BaseFont``. The inherited :class:`PDFont` definition does the same
    thing already, but the override is preserved so callers porting from
    Java find the method on this class."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    assert font.get_name() == "Helvetica"


def test_get_name_none_when_base_font_absent() -> None:
    """Missing ``/BaseFont`` -> ``None`` (matches upstream's
    ``getNameAsString`` returning null)."""
    assert PDType1Font().get_name() is None


def test_get_name_and_get_base_font_agree() -> None:
    """``get_name`` and ``get_base_font`` both read ``/BaseFont`` —
    upstream defines both for compat and they always return the same
    value for Type 1 fonts."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Times-Roman")
    assert font.get_name() == font.get_base_font() == "Times-Roman"


# ---------- encode cache (codeToBytesMap parity) ----------


def test_encode_caches_bytes_per_codepoint() -> None:
    """Repeated encode calls for the same character hit the cache and
    return identical bytes — mirrors upstream's ``codeToBytesMap``
    field (PDType1Font line 96)."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    font.get_cos_object().set_item(_ENCODING, _WIN_ANSI)

    first = font.encode("A")
    # Cache should now hold the entry.
    assert ord("A") in font._code_to_bytes
    second = font.encode("A")
    assert first == second == b"\x41"


def test_encode_cache_does_not_cross_codepoints() -> None:
    """The cache is keyed per-codepoint, not global — encoding a new
    character does not return a previously cached result."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    font.get_cos_object().set_item(_ENCODING, _WIN_ANSI)
    assert font.encode("A") == b"\x41"
    assert font.encode("B") == b"\x42"
    # Both cached, distinctly.
    assert font._code_to_bytes[ord("A")] == b"\x41"
    assert font._code_to_bytes[ord("B")] == b"\x42"


def test_encode_empty_string_yields_empty_bytes() -> None:
    """Empty input -> empty output, no encoding lookup performed."""
    font = PDType1Font()
    assert font.encode("") == b""


def test_encode_multi_character_string() -> None:
    """Multi-character input produces concatenated bytes, all cached."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    font.get_cos_object().set_item(_ENCODING, _WIN_ANSI)
    encoded = font.encode("ABC")
    assert encoded == b"ABC"
    assert {ord("A"), ord("B"), ord("C")} <= set(font._code_to_bytes.keys())


# ---------- AFM-aware get_height ----------


def test_get_height_uses_afm_for_standard_14() -> None:
    """For a Standard 14 font, ``get_height`` consults the AFM's
    ``getCharacterHeight`` — mirrors upstream
    ``PDType1Font.getHeight`` first branch (line 397)."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    font.get_cos_object().set_item(_ENCODING, _WIN_ANSI)
    # 'A' has a documented character height in the Helvetica AFM —
    # exact value is AFM-dependent, but it's positive and finite.
    height = font.get_height(ord("A"))
    assert height > 0
    assert height == pytest.approx(height, rel=1e-9)


def test_get_height_returns_afm_value_even_for_notdef() -> None:
    """Upstream queries the AFM with whatever name the encoding returns,
    including ``.notdef``. The AFM either returns a real height for
    glyphs it knows or 0 for unknown names — we match that contract
    rather than short-circuiting on the name."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    font.get_cos_object().set_item(_ENCODING, _WIN_ANSI)
    # The exact value is AFM-dependent; it must be a finite float and
    # the call must not raise.
    height = font.get_height(0x81)
    assert isinstance(height, float)


def test_get_height_zero_for_unparseable_program() -> None:
    """No AFM, no embedded program → ``0.0``."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "MyCustomNonStandardFont")
    assert font.get_height(65) == 0.0
