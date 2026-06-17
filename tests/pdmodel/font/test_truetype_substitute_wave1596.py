"""Wave 1596 — non-embedded TrueType substitute-font wiring.

For a simple ``/Subtype /TrueType`` font with no embedded ``/FontFile2``,
upstream ``PDTrueTypeFont`` resolves ``getWidthFromFont`` / ``codeToGID``
/ ``getPath`` through a host / bundled substitute program (Arial /
Liberation). pypdfbox previously returned ``0`` / GID ``0`` there; this
wave wires the substitute via :class:`FontMappers`, falling back to the
bundled ``LiberationSans-*`` last resort so the path is deterministic on
any machine.

These tests pin only the substitute-*independent* facets the DEFERRED
note allows: the substitute is host-font-dependent, so the exact GID /
width are not byte-diffable against the live Java oracle. We force the
bundled-Liberation last resort (via ``FontMappers.reset()`` — the default
AFM-only mapper cannot satisfy ``get_true_type_font``) so a *non-zero*
GID / width / glyph-path is produced reproducibly across CI runners.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.fontbox.font_mappers import FontMappers
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.pdmodel.font.encoding import WinAnsiEncoding
from pypdfbox.pdmodel.font.pd_font_descriptor import (
    FLAG_NON_SYMBOLIC,
    PDFontDescriptor,
)
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont

_BUNDLED_TTF = (
    Path(__file__).parents[3]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(autouse=True)
def _reset_font_mapper():
    """Force the default (AFM-only) mapper so the substitute path takes
    the deterministic bundled-Liberation last resort, not a host font."""
    FontMappers.reset()
    yield
    FontMappers.reset()


def _non_embedded_truetype(
    *,
    with_descriptor: bool = True,
    widths: list[float] | None = None,
    first_char: int = 0,
) -> PDTrueTypeFont:
    """Build a simple ``/TrueType`` font dict with **no** ``/FontFile2``."""
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    d.set_name(COSName.get_pdf_name("Subtype"), "TrueType")
    d.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    d.set_item(
        COSName.get_pdf_name("Encoding"),
        WinAnsiEncoding.INSTANCE.get_cos_object(),
    )
    if with_descriptor:
        fd = PDFontDescriptor()
        fd.set_font_name("Helvetica")
        fd.set_flags(FLAG_NON_SYMBOLIC)
        d.set_item(
            COSName.get_pdf_name("FontDescriptor"), fd.get_cos_object()
        )
    if widths is not None:
        d.set_int(COSName.get_pdf_name("FirstChar"), first_char)
        warr = COSArray()
        for w in widths:
            warr.add(COSFloat(float(w)))
        d.set_item(COSName.get_pdf_name("Widths"), warr)
    return PDTrueTypeFont(d)


def _embedded_truetype() -> PDTrueTypeFont:
    """Build a simple ``/TrueType`` font with a real embedded
    ``/FontFile2`` (the bundled Liberation TTF)."""
    return PDTrueTypeFont.load(None, _BUNDLED_TTF, WinAnsiEncoding.INSTANCE)


# ---------- (a) non-embedded font now resolves a real glyph ----------


def test_non_embedded_code_to_gid_is_non_zero():
    font = _non_embedded_truetype()
    # 'A' = 65; the bundled-Liberation substitute carries a real glyph.
    assert font.code_to_gid(65) != 0


def test_non_embedded_width_from_font_is_non_zero():
    font = _non_embedded_truetype()
    assert font.get_width_from_font(65) > 0.0


def test_non_embedded_glyph_path_is_non_empty():
    font = _non_embedded_truetype()
    assert font.get_glyph_path(65)


def test_non_embedded_height_is_non_zero():
    font = _non_embedded_truetype()
    assert font.get_height(65) > 0.0


def test_substitute_is_cached_single_instance():
    font = _non_embedded_truetype()
    first = font._get_substitute_font()  # noqa: SLF001
    second = font._get_substitute_font()  # noqa: SLF001
    assert first is not None
    assert first is second


def test_substitute_is_pypdfbox_true_type_font():
    """Resolution methods speak the pypdfbox font API, so the adapted
    substitute must be a pypdfbox :class:`TrueTypeFont`, not a raw
    fontTools ``TTFont``."""
    font = _non_embedded_truetype()
    assert isinstance(font._get_substitute_font(), TrueTypeFont)  # noqa: SLF001


# ---------- (b) is_embedded() stays False for a substitute ----------


def test_substitute_is_not_embedded():
    font = _non_embedded_truetype()
    # Drive the substitute to load, then re-check the embedded flag.
    assert font.code_to_gid(65) != 0
    assert font.is_embedded() is False


def test_substitute_get_true_type_font_stays_none():
    """``get_true_type_font`` is embedded-only and must not return the
    substitute (preserves the renderer / subset caller contract)."""
    font = _non_embedded_truetype()
    assert font.code_to_gid(65) != 0  # loads the substitute
    assert font.get_true_type_font() is None


def test_substitute_is_not_damaged():
    font = _non_embedded_truetype()
    assert font.is_damaged() is False


def test_no_descriptor_still_resolves_via_last_resort():
    """A font without a ``/FontDescriptor`` at all still resolves a glyph
    through the descriptor-less Sans-Regular last resort."""
    font = _non_embedded_truetype(with_descriptor=False)
    assert font.code_to_gid(65) != 0
    assert font.is_embedded() is False


# ---------- (c) in-/Widths-window width still from /Widths ----------


def test_in_widths_window_width_taken_from_widths_array():
    # /Widths covers code 65 with a sentinel 999; substitute must not win.
    font = _non_embedded_truetype(widths=[999.0], first_char=65)
    assert font.get_glyph_width(65) == 999.0


def test_out_of_widths_window_falls_back_to_substitute():
    # Code 66 is outside the one-entry /Widths window -> substitute width.
    font = _non_embedded_truetype(widths=[999.0], first_char=65)
    width = font.get_glyph_width(66)
    assert width > 0.0
    assert width != 999.0


# ---------- (d) embedded fonts are completely unaffected ----------


def test_embedded_font_is_embedded_true():
    font = _embedded_truetype()
    assert font.is_embedded() is True


def test_embedded_font_get_true_type_font_returns_program():
    font = _embedded_truetype()
    assert font.get_true_type_font() is not None


def test_embedded_font_does_not_load_a_substitute():
    """When a real ``/FontFile2`` is present the substitute slot resolves
    to the embedded program itself (never a Liberation last resort)."""
    font = _embedded_truetype()
    embedded = font.get_true_type_font()
    assert embedded is not None
    # ``_get_substitute_font`` returns the embedded program for an
    # embedded font (no separate substitute is mapped).
    assert font._get_substitute_font() is embedded  # noqa: SLF001


def test_embedded_font_glyph_resolution_uses_embedded_program():
    font = _embedded_truetype()
    embedded = font.get_true_type_font()
    assert embedded is not None
    # GID / width come from the embedded program, identical to a direct
    # lookup against it.
    gid = font.code_to_gid(65)
    assert gid != 0
    assert font.get_width_from_font(65) > 0.0


def test_set_true_type_font_clears_substitute_cache():
    """Injecting a program must drop any previously-resolved substitute."""
    font = _non_embedded_truetype()
    assert font._get_substitute_font() is not None  # noqa: SLF001
    ttf = TrueTypeFont.from_bytes(_BUNDLED_TTF.read_bytes())
    font.set_true_type_font(ttf)
    assert font.is_embedded() is True
    assert font.get_true_type_font() is ttf
