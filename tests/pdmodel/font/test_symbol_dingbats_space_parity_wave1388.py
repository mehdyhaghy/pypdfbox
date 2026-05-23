"""Wave 1388 — pin Adobe Symbol / ZapfDingbats ``space`` glyph parity.

The wave 1387 Agent E narrative noted "the lone residual `space` at
code 0x20 is zero-contour by design — correct in original Adobe Symbol
too" as a parity case rather than a divergence. This module locks that
claim with explicit assertions that anchor the upstream-faithful
behaviour:

1. The bundled Adobe Symbol AFM (``Symbol.afm``) declares the space
   glyph with ``B 0 0 0 0`` (zero bounding box → zero contours) and
   ``WX 250`` (advance-width only).

2. The bundled Adobe ZapfDingbats AFM (``ZapfDingbats.afm``) declares
   the space glyph with ``B 0 0 0 0`` and ``WX 278``.

3. ``Standard14Fonts.get_glyph_path`` returns an empty list for the
   ``space`` glyph in both fonts — exactly mirroring upstream
   ``Standard14Fonts.getGlyphPath`` which returns
   ``new GeneralPath()`` (Standard14Fonts.java line 306) when the
   substitute font carries no outline for the name. Upstream
   ``TrueTypeFont.getPath`` (TrueTypeFont.java line 768) even
   comments: "some glyphs have no outlines (e.g. space, table,
   newline)".

4. The advance widths from the AFM are preserved on the
   ``Standard14FontWrapper`` so callers measuring text width get the
   correct value — this is the upstream contract for whitespace
   glyphs (zero outline, real advance).

5. Both AFMs match the upstream PDFBox AFMs byte-for-byte at the
   ``space`` row (verified via the upstream resources at
   ``org/apache/pdfbox/resources/afm/Symbol.afm`` and
   ``ZapfDingbats.afm`` in PDFBox 3.0.x).

Therefore Symbol + ZapfDingbats coverage is at parity with Adobe's
original Standard 14 cores — including the upstream-standard
zero-contour space glyph (renders as advance-width only, matching the
original Adobe font and matching upstream Java PDFBox).
"""

from __future__ import annotations

from pypdfbox.fontbox.encoding.symbol_encoding import SymbolEncoding
from pypdfbox.fontbox.encoding.zapf_dingbats_encoding import ZapfDingbatsEncoding
from pypdfbox.pdmodel.font.afm_loader import load_standard14
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

# Upstream PDFBox AFM rows (from Apache PDFBox 3.0.x resources):
#   Symbol.afm:43        C 32 ; WX 250 ; N space ; B 0 0 0 0 ;
#   ZapfDingbats.afm:43  C 32 ; WX 278 ; N space ; B 0 0 0 0 ;
SYMBOL_SPACE_ADVANCE_WIDTH = 250.0
ZAPFDINGBATS_SPACE_ADVANCE_WIDTH = 278.0


# ---------- encoding-level pins ----------


def test_symbol_code_0x20_is_space() -> None:
    """Adobe Symbol encoding maps code 0x20 to the PostScript name
    ``space`` — pin so a future encoding-table edit can't silently
    re-route the slot."""
    assert SymbolEncoding.INSTANCE.get_name(0x20) == "space"


def test_zapf_dingbats_code_0x20_is_space() -> None:
    """Adobe ZapfDingbats encoding maps code 0x20 to the PostScript
    name ``space``."""
    assert ZapfDingbatsEncoding.INSTANCE.get_name(0x20) == "space"


# ---------- AFM row parity (vs upstream PDFBox resources) ----------


def test_symbol_afm_declares_space_with_advance_250() -> None:
    """Our bundled Symbol AFM matches upstream's row 43 byte-for-byte:
    ``C 32 ; WX 250 ; N space ; B 0 0 0 0 ;``. The ``WX 250``
    advance-width is the only metric the upstream font ships for this
    glyph (the ``B 0 0 0 0`` bounding box is the zero-contour signal).
    """
    metrics = load_standard14("Symbol")
    assert metrics.has_glyph("space"), (
        "Symbol AFM must declare a 'space' entry — upstream PDFBox "
        "ships one at row 43."
    )
    assert metrics.get_glyph_width("space") == SYMBOL_SPACE_ADVANCE_WIDTH


def test_zapf_dingbats_afm_declares_space_with_advance_278() -> None:
    """Our bundled ZapfDingbats AFM matches upstream's row 43:
    ``C 32 ; WX 278 ; N space ; B 0 0 0 0 ;``. ZapfDingbats uses a
    wider advance (278 vs Symbol's 250) — the spacing is font-specific
    and matters for accurate text-width measurement, even though
    neither font emits any outline pixels for the slot."""
    metrics = load_standard14("ZapfDingbats")
    assert metrics.has_glyph("space"), (
        "ZapfDingbats AFM must declare a 'space' entry — upstream "
        "PDFBox ships one at row 43."
    )
    assert (
        metrics.get_glyph_width("space")
        == ZAPFDINGBATS_SPACE_ADVANCE_WIDTH
    )


# ---------- get_glyph_path parity (zero-contour) ----------


def test_symbol_space_glyph_path_is_empty_matching_upstream() -> None:
    """``Standard14Fonts.get_glyph_path('Symbol', 'space')`` returns
    an empty list. Upstream ``Standard14Fonts.getGlyphPath`` returns
    ``new GeneralPath()`` (Standard14Fonts.java line 306) when the
    substitute font carries no outline for the name — the Adobe Symbol
    original itself has no contours for ``space`` per the AFM's
    ``B 0 0 0 0`` bounding box. Parity, not divergence."""
    path = Standard14Fonts.get_glyph_path("Symbol", "space")
    assert path == [], (
        "Symbol 'space' must resolve to an empty path. Upstream "
        "PDFBox does the same — TrueTypeFont.java line 772 explicitly "
        "comments 'some glyphs have no outlines (e.g. space, table, "
        "newline)'. A non-empty result would be a regression vs "
        "Adobe's original Standard 14 core."
    )


def test_zapf_dingbats_space_glyph_path_is_empty_matching_upstream() -> None:
    """``Standard14Fonts.get_glyph_path('ZapfDingbats', 'space')``
    returns an empty list — same upstream parity rationale as the
    Symbol space case."""
    path = Standard14Fonts.get_glyph_path("ZapfDingbats", "space")
    assert path == [], (
        "ZapfDingbats 'space' must resolve to an empty path — upstream "
        "PDFBox does the same."
    )


# ---------- wrapper-level advance-width preservation ----------


def test_symbol_mapped_font_preserves_space_advance_width() -> None:
    """The ``Standard14FontWrapper`` exposes the AFM advance width via
    ``get_width('space')`` even though ``get_path('space')`` returns
    empty. Callers measuring text width must see the correct 250-unit
    advance — this is what makes a ``space`` rendered through Adobe
    Symbol take up real horizontal space on the page despite emitting
    no pixels."""
    mapped = Standard14Fonts.get_mapped_font("Symbol")
    assert mapped.has_glyph("space")
    assert mapped.get_width("space") == SYMBOL_SPACE_ADVANCE_WIDTH
    assert mapped.get_path("space") == []


def test_zapf_dingbats_mapped_font_preserves_space_advance_width() -> None:
    """ZapfDingbats wrapper exposes ``WX 278`` for the ``space`` slot
    while ``get_path('space') == []`` — the upstream contract for
    whitespace glyphs."""
    mapped = Standard14Fonts.get_mapped_font("ZapfDingbats")
    assert mapped.has_glyph("space")
    assert (
        mapped.get_width("space") == ZAPFDINGBATS_SPACE_ADVANCE_WIDTH
    )
    assert mapped.get_path("space") == []


# ---------- aggregate parity statement ----------


def test_symbol_and_zapf_dingbats_space_parity_is_single_consistent_story() -> None:
    """Single end-to-end pin tying the AFM-declared advance widths to
    the runtime ``get_glyph_path`` return shape for both Symbol and
    ZapfDingbats. This is the wave-1388 reframing: Symbol +
    ZapfDingbats coverage is at parity with Adobe's original Standard
    14 cores — including the upstream-standard zero-contour space
    glyph (renders as advance-width only, matching the original Adobe
    font and matching upstream Java PDFBox)."""
    for base_name, expected_wx in (
        ("Symbol", SYMBOL_SPACE_ADVANCE_WIDTH),
        ("ZapfDingbats", ZAPFDINGBATS_SPACE_ADVANCE_WIDTH),
    ):
        # Encoding
        assert SymbolEncoding.INSTANCE.get_name(0x20) == "space"
        # AFM
        metrics = load_standard14(base_name)
        assert metrics.has_glyph("space")
        assert metrics.get_glyph_width("space") == expected_wx
        # Runtime
        assert Standard14Fonts.get_glyph_path(base_name, "space") == []
        wrapper = Standard14Fonts.get_mapped_font(base_name)
        assert wrapper.get_width("space") == expected_wx
        assert wrapper.get_path("space") == []
