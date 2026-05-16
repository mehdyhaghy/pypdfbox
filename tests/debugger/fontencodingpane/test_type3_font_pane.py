"""Tests for the promoted public methods on :class:`Type3Font` —
``calc_b_box`` / ``get_glyphs`` / ``render_type3_glyph``.

These cover the upstream-named entry points (as opposed to the
``_calc_bbox`` / ``_get_glyphs`` legacy underscored aliases that
:mod:`test_type3_font` already exercises through the constructor).
"""

from __future__ import annotations

import os

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.debugger.fontencodingpane.type3_font import NO_GLYPH, Type3Font
from pypdfbox.pdmodel.font import PDType3Font as PDType3FontModel
from pypdfbox.pdmodel.font.pd_type3_char_proc import PDType3CharProc
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

# Honour the project-wide Tk opt-out — the constructor builds a
# FontEncodingView which needs a Tk display unless a parent widget is
# supplied via ``tk_root``.
pytestmark = pytest.mark.skipif(
    os.environ.get("PYPDFBOX_SKIP_TK", "") == "1",
    reason="PYPDFBOX_SKIP_TK=1 -- Tk tests opted out",
)


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


def _type3_font_with_char_procs(
    char_procs: dict[str, bytes] | None = None,
) -> PDType3FontModel:
    """Build a hand-rolled :class:`PDType3Font` with a WinAnsi encoding and
    an optional ``/CharProcs`` dictionary mapping glyph name → raw bytes.
    """
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("Type"), "Font")
    font_dict.set_name(COSName.get_pdf_name("Subtype"), "Type3")
    font_dict.set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    if char_procs:
        cp_dict = COSDictionary()
        for name, raw in char_procs.items():
            stream = COSStream()
            stream.create_output_stream().write(raw)
            cp_dict.set_item(COSName.get_pdf_name(name), stream)
        font_dict.set_item(COSName.get_pdf_name("CharProcs"), cp_dict)
    return PDType3FontModel(font_dict)


# ---------------------------------------------------------------------------
# get_glyphs
# ---------------------------------------------------------------------------


def test_get_glyphs_returns_256_rows_4_cols(tk_root):
    """``get_glyphs`` mirrors upstream's ``Object[256][4]`` shape: one
    row per code 0..255, each row carrying ``[code, name, unicode, glyph]``."""
    font = _type3_font_with_char_procs()
    pane = Type3Font(font, None, tk_root)
    rows = pane.get_glyphs(font)
    assert len(rows) == 256
    for row in rows:
        assert len(row) == 4
    # Column 0 is always the code.
    assert [row[0] for row in rows] == list(range(256))


def test_get_glyphs_winansi_a_row_is_populated(tk_root):
    """Code 0x41 (65) maps to glyph name ``"A"`` in WinAnsi; the row's
    name/unicode columns should reflect that."""
    font = _type3_font_with_char_procs()
    pane = Type3Font(font, None, tk_root)
    rows = pane.get_glyphs(font)
    row = rows[0x41]
    assert row[0] == 0x41
    assert row[1] == "A"
    assert row[2] == "A"


def test_get_glyphs_no_glyph_row_for_unmapped_code(tk_root):
    """Codes outside WinAnsi *and* without a ``/ToUnicode`` mapping
    fall through to ``NO_GLYPH``."""
    font = _type3_font_with_char_procs()
    pane = Type3Font(font, None, tk_root)
    rows = pane.get_glyphs(font)
    # 0x00 (NUL) is not assigned a glyph by WinAnsi.
    row = rows[0]
    assert row[1] == NO_GLYPH
    assert row[2] == NO_GLYPH
    assert row[3] == NO_GLYPH


def test_get_glyphs_underscore_alias_matches_public(tk_root):
    """``_get_glyphs`` is preserved as an underscore alias of the
    upstream-named ``get_glyphs`` for internal callers that pre-dated
    the public promotion."""
    font = _type3_font_with_char_procs()
    pane = Type3Font(font, None, tk_root)
    assert Type3Font._get_glyphs is Type3Font.get_glyphs


# ---------------------------------------------------------------------------
# calc_b_box
# ---------------------------------------------------------------------------


def test_calc_b_box_zero_when_no_char_procs(tk_root):
    """A font without ``/CharProcs`` and no ``/FontBBox`` falls all the
    way through to a zero-dimensioned rectangle."""
    font = _type3_font_with_char_procs()
    pane = Type3Font(font, None, tk_root)
    bbox = pane.calc_b_box(font)
    assert isinstance(bbox, PDRectangle)
    assert bbox.get_width() == 0
    assert bbox.get_height() == 0


def test_calc_b_box_unions_two_glyph_bboxes(tk_root, monkeypatch):
    """When two CharProcs have distinct ``d1``-declared glyph bboxes,
    ``calc_b_box`` returns their union, which should match the larger
    of the two when one strictly contains the other.
    """
    font = _type3_font_with_char_procs()

    # Smaller glyph: 10 × 20 box at origin.
    bbox_small = PDRectangle(0.0, 0.0, 10.0, 20.0)
    # Larger glyph: 100 × 80 box that fully contains the small one.
    bbox_large = PDRectangle(0.0, 0.0, 100.0, 80.0)

    class _Stub:
        def __init__(self, b):
            self._b = b

        def get_glyph_bbox(self):
            return self._b

    def _patched(code):
        if code == 0x41:  # "A"
            return _Stub(bbox_large)
        if code == 0x42:  # "B"
            return _Stub(bbox_small)
        return None

    monkeypatch.setattr(font, "get_char_proc", _patched)
    pane = Type3Font(font, None, tk_root)
    bbox = pane.calc_b_box(font)
    # Union of (0..10, 0..20) and (0..100, 0..80) is the larger one.
    assert bbox.get_width() == pytest.approx(100.0)
    assert bbox.get_height() == pytest.approx(80.0)


def test_calc_b_box_underscore_alias_matches_public(tk_root):
    """The underscore-prefixed alias must still resolve to the same
    method object after the promotion."""
    assert Type3Font._calc_bbox is Type3Font.calc_b_box


# ---------------------------------------------------------------------------
# render_type3_glyph
# ---------------------------------------------------------------------------


def test_render_type3_glyph_returns_pil_image(tk_root):
    """``render_type3_glyph(name, size)`` returns a Pillow image of the
    requested size. Mirrors the upstream entry point — the lite-renderer
    deviation note in the source explains why the result is a
    text-label thumbnail rather than a rasterised content stream."""
    try:
        from PIL.Image import Image as _PilImage
    except ImportError:
        pytest.skip("Pillow not available")
    font = _type3_font_with_char_procs()
    pane = Type3Font(font, None, tk_root)
    img = pane.render_type3_glyph("A", 48)
    assert isinstance(img, _PilImage)
    assert img.size == (48, 48)


def test_render_type3_glyph_default_size_is_40(tk_root):
    """The default cell size is 40×40 — historical pane width."""
    try:
        from PIL.Image import Image as _PilImage
    except ImportError:
        pytest.skip("Pillow not available")
    font = _type3_font_with_char_procs()
    pane = Type3Font(font, None, tk_root)
    img = pane.render_type3_glyph("A")
    assert isinstance(img, _PilImage)
    assert img.size == (40, 40)


def test_render_type3_glyph_non_empty_image(tk_root):
    """A trivial Type 3 glyph with a one-line proc still produces a
    Pillow image with non-zero pixel area (i.e. ``getbbox`` either
    returns the white canvas bounds or, when ``draw.text`` succeeded, a
    sub-rectangle inside it)."""
    try:
        from PIL.Image import Image as _PilImage
    except ImportError:
        pytest.skip("Pillow not available")
    # Trivial CharProc — a single moveto/lineto preceded by the spec-
    # required d1 metric op. Width 1000, BBox 0 0 100 100.
    proc_bytes = b"1000 0 0 0 100 100 d1\n0 0 m 100 100 l S\n"
    font = _type3_font_with_char_procs({"A": proc_bytes})
    # Sanity: the CharProc actually parses through PDType3CharProc.
    char_proc = font.get_char_proc(0x41)
    assert isinstance(char_proc, PDType3CharProc)
    assert char_proc.get_glyph_bbox() is not None
    pane = Type3Font(font, None, tk_root)
    img = pane.render_type3_glyph("A", 32)
    assert isinstance(img, _PilImage)
    assert img.size == (32, 32)
    # Total pixel area > 0 confirms a real Pillow canvas was returned.
    assert img.size[0] * img.size[1] > 0


def test_render_type3_glyph_truncates_long_name(tk_root):
    """The label is truncated to 4 characters but rendering does not
    raise on long glyph names (e.g. ``zerosuperior``)."""
    try:
        from PIL.Image import Image as _PilImage
    except ImportError:
        pytest.skip("Pillow not available")
    font = _type3_font_with_char_procs()
    pane = Type3Font(font, None, tk_root)
    img = pane.render_type3_glyph("zerosuperior", 40)
    assert isinstance(img, _PilImage)
    assert img.size == (40, 40)
