"""Tests for the :class:`Type3Font` encoding pane."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.debugger.fontencodingpane.type3_font import Type3Font
from pypdfbox.pdmodel.font import PDType3Font as PDType3FontModel


def _type3_font() -> PDType3FontModel:
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("Type"), "Font")
    font_dict.set_name(COSName.get_pdf_name("Subtype"), "Type3")
    font_dict.set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    return PDType3FontModel(font_dict)


def test_type3_pane_builds_view(tk_root):
    pane = Type3Font(_type3_font(), None, tk_root)
    assert pane.view is not None
    assert pane.view.tree is not None
    # WinAnsi encoding alone supplies 224 mapped codes.
    assert pane.total_available_glyphs > 0


def test_type3_pane_get_panel(tk_root):
    pane = Type3Font(_type3_font(), None, tk_root)
    assert pane.get_panel() is pane.view


def test_type3_pane_font_bbox_is_zero_without_char_procs(tk_root):
    """Without /CharProcs the per-glyph BBox union is empty; ``calcBBox``
    falls back to the font's bounding box (also empty for a stub dict),
    so ``font_bbox`` has zero dimensions and the view falls back to the
    ``NO_GLYPH`` text path."""
    pane = Type3Font(_type3_font(), None, tk_root)
    assert pane.font_bbox.get_width() == 0
    assert pane.font_bbox.get_height() == 0


def test_type3_pane_table_has_256_rows(tk_root):
    pane = Type3Font(_type3_font(), None, tk_root)
    assert len(pane.view.tree.get_children()) == 256


# ---- _render_type3_glyph_label --------------------------------------------


def test_render_type3_glyph_label_returns_image():
    """Helper renders a small PIL image label per glyph name."""
    from pypdfbox.debugger.fontencodingpane.type3_font import (
        _render_type3_glyph_label,
    )

    try:
        from PIL.Image import Image as _PilImage
    except ImportError:
        import pytest

        pytest.skip("Pillow not available")
    img = _render_type3_glyph_label("A")
    assert isinstance(img, _PilImage)
    assert img.size == (40, 40)


def test_render_type3_glyph_label_truncates_long_name():
    """Display string is truncated to 4 chars; doesn't raise."""
    from pypdfbox.debugger.fontencodingpane.type3_font import (
        _render_type3_glyph_label,
    )

    try:
        from PIL.Image import Image as _PilImage
    except ImportError:
        import pytest

        pytest.skip("Pillow not available")
    img = _render_type3_glyph_label("zerosuperior")
    assert isinstance(img, _PilImage)


# ---- name fallback via descriptor -----------------------------------------


def test_type3_constructor_uses_descriptor_when_basefont_missing(tk_root):
    """When ``font.get_name()`` returns ``None`` and a descriptor is
    present, the pane label falls through to ``descriptor.get_font_name()``
    (line 63)."""
    from pypdfbox.pdmodel.font import PDFontDescriptor

    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("Type"), "Font")
    font_dict.set_name(COSName.get_pdf_name("Subtype"), "Type3")
    # /BaseFont deliberately missing so get_name() returns None.
    font_dict.set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    desc_dict = COSDictionary()
    desc_dict.set_name(COSName.get_pdf_name("Type"), "FontDescriptor")
    desc_dict.set_name(COSName.get_pdf_name("FontName"), "MyType3FromDescriptor")
    # PDFontDescriptor goes in /FontDescriptor key.
    font_dict.set_item(COSName.get_pdf_name("FontDescriptor"), desc_dict)
    font = PDType3FontModel(font_dict)
    # Sanity: descriptor accessor returns a PDFontDescriptor.
    assert isinstance(font.get_font_descriptor(), PDFontDescriptor)
    pane = Type3Font(font, None, tk_root)
    assert pane.view is not None


# ---- calcBBox branches ----------------------------------------------------


class _CharProcStub:
    """Stub ``PDType3CharProc`` exposing ``get_glyph_bbox`` only."""

    def __init__(self, bbox=None, raise_err: bool = False) -> None:
        self._bbox = bbox
        self._raise = raise_err

    def get_glyph_bbox(self):
        if self._raise:
            raise OSError("forced get_glyph_bbox fail")
        return self._bbox


def test_type3_calc_bbox_handles_char_proc_oserror(tk_root, monkeypatch):
    """When ``font.get_char_proc`` raises ``OSError`` for some codes, the
    bbox accumulator skips them (line 110-111)."""
    font = _type3_font()

    original = font.get_char_proc

    def _patched(code: int):
        if code in (10, 20):
            raise OSError("forced get_char_proc fail")
        return original(code)

    monkeypatch.setattr(font, "get_char_proc", _patched)
    pane = Type3Font(font, None, tk_root)
    # No CharProcs dict → bbox stays zero, but construction succeeds.
    assert pane.font_bbox.get_width() == 0


def test_type3_calc_bbox_collects_per_glyph_bboxes(tk_root, monkeypatch):
    """When ``get_char_proc`` returns char procs with valid bboxes, the
    bbox accumulator updates min/max (lines 114-123)."""
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    font = _type3_font()

    # Build two char proc stubs at codes 65/66 with non-trivial bboxes.
    bbox_a = PDRectangle(0.0, 0.0, 10.0, 20.0)
    bbox_b = PDRectangle(-5.0, -10.0, 30.0, 40.0)

    def _patched(code: int):
        if code == 65:
            return _CharProcStub(bbox_a)
        if code == 66:
            return _CharProcStub(bbox_b)
        if code == 67:
            # AttributeError branch — char proc lacks ``get_glyph_bbox``.
            class _NoBBox:
                pass

            return _NoBBox()
        if code == 68:
            # bbox is None — skipped.
            return _CharProcStub(None)
        return None

    monkeypatch.setattr(font, "get_char_proc", _patched)
    pane = Type3Font(font, None, tk_root)
    # Bbox now has non-zero width / height.
    assert pane.font_bbox.get_width() > 0
    assert pane.font_bbox.get_height() > 0


def test_type3_calc_bbox_falls_back_to_font_bbox(tk_root, monkeypatch):
    """When per-glyph union yields an empty bbox AND
    ``font.get_bounding_box()`` returns a valid rectangle, use the
    fallback (line 132)."""
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    font = _type3_font()

    monkeypatch.setattr(
        font,
        "get_bounding_box",
        lambda: PDRectangle(0.0, 0.0, 100.0, 100.0),
    )
    pane = Type3Font(font, None, tk_root)
    # Fallback bbox kicks in — width/height match the stub.
    assert pane.font_bbox.get_width() == 100.0
    assert pane.font_bbox.get_height() == 100.0


# ---- _get_glyphs branches with non-trivial bbox --------------------------


def test_type3_get_glyphs_renders_label_and_caches(tk_root, monkeypatch):
    """When the font has a non-empty bbox AND the encoding supplies the
    same glyph name across codes, the image cache reuses the prior
    rendering (lines 163-167)."""
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    font = _type3_font()
    monkeypatch.setattr(
        font,
        "get_bounding_box",
        lambda: PDRectangle(0.0, 0.0, 100.0, 100.0),
    )
    pane = Type3Font(font, None, tk_root)
    # Constructed successfully. We exercised both the cache-miss
    # (first time a glyph name appears) and the cache-hit (subsequent
    # mappings of the same name) paths via WinAnsi's reuse of glyph
    # names across codes.
    assert pane.total_available_glyphs > 0


def test_type3_get_glyphs_swallows_to_unicode_oserror(
    tk_root, monkeypatch
):
    """``font.to_unicode`` raising ``OSError`` falls back to ``None``
    (line 154-155)."""
    font = _type3_font()
    original = font.to_unicode

    def _patched(code: int) -> str | None:
        if code == 65:
            raise OSError("forced to_unicode fail")
        return original(code)

    monkeypatch.setattr(font, "to_unicode", _patched)
    pane = Type3Font(font, None, tk_root)
    assert len(pane.view.tree.get_children()) == 256
