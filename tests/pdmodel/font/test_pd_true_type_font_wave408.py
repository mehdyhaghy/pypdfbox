from __future__ import annotations

from typing import Any, cast

import pytest

from pypdfbox.cos import COSName
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.pdmodel.font import PDFontDescriptor, PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_true_type_font import (
    _draw_glyph_by_gid,
    _draw_glyph_by_name,
    _embed_subset_bytes,
    _fonttools_glyph_set,
    _gid_to_glyph_name,
    _glyph_bbox_height,
)


class _CMapStub:
    def __init__(self, mapping: dict[int, int] | None = None) -> None:
        self.mapping = mapping or {}

    def get_glyph_id(self, code_point: int) -> int:
        return self.mapping.get(code_point, 0)


class _GlyphStub:
    def __init__(self, *, fail: bool = False, draw_bounds: bool = True) -> None:
        self.fail = fail
        self.draw_bounds = draw_bounds

    def draw(self, pen: Any) -> None:
        if self.fail:
            raise RuntimeError("draw failed")
        if not self.draw_bounds:
            return
        pen.moveTo((0, 0))
        pen.lineTo((0, 10))
        pen.lineTo((10, 10))
        pen.closePath()


class _GlyphSet(dict[str, _GlyphStub]):
    pass


class _InnerStub:
    def __init__(
        self,
        *,
        glyph_order: list[str] | None = None,
        glyph_set: _GlyphSet | None = None,
        fail_glyph_order: bool = False,
        fail_glyph_set: bool = False,
        glyf: dict[str, Any] | None = None,
    ) -> None:
        self._glyph_order = glyph_order or [".notdef", "A"]
        self._glyph_set = glyph_set or _GlyphSet()
        self._fail_glyph_order = fail_glyph_order
        self._fail_glyph_set = fail_glyph_set
        if glyf is not None:
            self.glyf = glyf

    def getGlyphOrder(self) -> list[str]:  # noqa: N802
        if self._fail_glyph_order:
            raise RuntimeError("glyph order failed")
        return self._glyph_order

    def getGlyphSet(self) -> _GlyphSet:  # noqa: N802
        if self._fail_glyph_set:
            raise RuntimeError("glyph set failed")
        return self._glyph_set

    def __contains__(self, key: object) -> bool:
        return key == "glyf" and hasattr(self, "glyf")

    def __getitem__(self, key: str) -> Any:
        if key == "glyf":
            return self.glyf
        raise KeyError(key)


class _TTFStub:
    def __init__(
        self,
        *,
        cmap: _CMapStub | None = None,
        inner: _InnerStub | None = None,
        units_per_em: int = 1000,
        advances: dict[int, int] | None = None,
        fail_cmap: bool = False,
    ) -> None:
        self._cmap = cmap
        self._tt = inner
        self._units_per_em = units_per_em
        self._advances = advances or {}
        self._fail_cmap = fail_cmap

    def get_unicode_cmap_subtable(self) -> _CMapStub | None:
        if self._fail_cmap:
            raise RuntimeError("cmap failed")
        return self._cmap

    def get_units_per_em(self) -> int:
        return self._units_per_em

    def get_advance_width(self, gid: int) -> int:
        return self._advances.get(gid, 0)

    def get_number_of_glyphs(self) -> int:
        return 2

    def get_post_script(self):  # noqa: ANN201 — stub
        # Wave-1434: a no-/Encoding TrueType now resolves its encoding via
        # read_encoding_from_font(), which consults the post table for glyph
        # names. A real TTF has one; this minimal stub has none (the production
        # path handles ``post is None`` by falling back to GID pseudo-names).
        return None


class _BBoxGlyph:
    yMin = -2
    yMax = 8


def test_internal_true_type_font_alias_delegates_to_public_accessor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDTrueTypeFont()
    sentinel = object()
    monkeypatch.setattr(font, "get_true_type_font", lambda: sentinel)

    assert font._get_true_type_font() is sentinel


def test_add_text_and_iterable_codepoints_are_collected() -> None:
    font = PDTrueTypeFont()

    font.add_text_to_subset("Az")

    assert font._collect_subset_codepoints([ord("B")], (ord("C"),)) == {
        ord("A"),
        ord("z"),
        ord("B"),
        ord("C"),
    }


def test_glyph_width_prefers_width_array_and_handles_zero_units(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDTrueTypeFont()
    font.set_first_char(65)
    font.set_widths([321.0])
    assert font.get_glyph_width(65) == 321.0

    no_units = cast(
        TrueTypeFont,
        _TTFStub(cmap=_CMapStub({65: 1}), units_per_em=0, advances={1: 500}),
    )
    font = PDTrueTypeFont()
    monkeypatch.setattr(font, "get_true_type_font", lambda: no_units)
    assert font.get_glyph_width(65) == 0.0


def test_path_and_glyph_path_empty_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    # Disable the wave-1596 non-embedded substitute so the genuine
    # "no program at all" branch is exercised (no host / bundled fallback).
    monkeypatch.setattr(
        PDTrueTypeFont, "_get_substitute_font", lambda self: None
    )
    assert PDTrueTypeFont().get_path("A") == []

    font = PDTrueTypeFont()
    empty = cast(TrueTypeFont, _TTFStub(cmap=_CMapStub()))
    monkeypatch.setattr(font, "get_true_type_font", lambda: empty)
    assert font.get_glyph_path(65) == []


def test_glyph_path_falls_back_to_direct_gid(monkeypatch: pytest.MonkeyPatch) -> None:
    font = PDTrueTypeFont()
    ttf = cast(
        TrueTypeFont,
        _TTFStub(
            cmap=_CMapStub({65: 1}),
            inner=_InnerStub(glyph_set=_GlyphSet(A=_GlyphStub())),
        ),
    )
    monkeypatch.setattr(font, "get_true_type_font", lambda: ttf)

    assert font.get_glyph_path(65)


def test_get_height_zero_when_code_does_not_resolve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDTrueTypeFont()
    ttf = cast(TrueTypeFont, _TTFStub(cmap=_CMapStub()))
    monkeypatch.setattr(font, "get_true_type_font", lambda: ttf)

    assert font.get_height(65) == 0.0


def test_glyph_name_for_code_suppresses_notdef() -> None:
    font = PDTrueTypeFont()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )

    assert font.get_glyph_name_for_code(0) is None


def test_unicode_cmap_parse_failure_is_cached() -> None:
    font = PDTrueTypeFont()
    ttf = cast(TrueTypeFont, _TTFStub(fail_cmap=True))

    assert font._get_unicode_cmap(ttf) is None
    assert font._cmap_resolved is True
    assert font._get_unicode_cmap(ttf) is None


def test_fonttools_glyph_helpers_handle_missing_and_failing_inners() -> None:
    no_inner = cast(TrueTypeFont, object())
    assert _fonttools_glyph_set(no_inner) is None
    assert _gid_to_glyph_name(no_inner, 1) is None
    assert _glyph_bbox_height(no_inner, 1) == 0.0

    fail_glyph_set = cast(TrueTypeFont, _TTFStub(inner=_InnerStub(fail_glyph_set=True)))
    assert _fonttools_glyph_set(fail_glyph_set) is None

    fail_order = cast(TrueTypeFont, _TTFStub(inner=_InnerStub(fail_glyph_order=True)))
    assert _gid_to_glyph_name(fail_order, 1) is None
    assert _draw_glyph_by_gid(fail_order, 1) == []

    out_of_range = cast(TrueTypeFont, _TTFStub(inner=_InnerStub(glyph_order=[".notdef"])))
    assert _gid_to_glyph_name(out_of_range, 5) is None


def test_draw_glyph_by_name_swallows_draw_failures() -> None:
    ttf = cast(
        TrueTypeFont,
        _TTFStub(inner=_InnerStub(glyph_set=_GlyphSet(A=_GlyphStub(fail=True)))),
    )

    assert _draw_glyph_by_name(ttf, "A") == []


def test_get_path_by_name_returns_empty_for_non_integer_pseudo_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDTrueTypeFont()
    ttf = cast(TrueTypeFont, _TTFStub(inner=_InnerStub()))
    monkeypatch.setattr(font, "get_true_type_font", lambda: ttf)

    assert font.get_path_by_name("not-a-gid") == []


def test_glyph_bbox_height_handles_missing_glyf_name_and_bad_glyf() -> None:
    missing_name = cast(TrueTypeFont, _TTFStub(inner=_InnerStub(glyph_order=[".notdef"])))
    assert _glyph_bbox_height(missing_name, 1) == 0.0

    bad_glyf = cast(
        TrueTypeFont,
        _TTFStub(inner=_InnerStub(glyf={})),
    )
    assert _glyph_bbox_height(bad_glyf, 1) == 0.0

    good_glyf = cast(
        TrueTypeFont,
        _TTFStub(inner=_InnerStub(glyf={"A": _BBoxGlyph()})),
    )
    assert _glyph_bbox_height(good_glyf, 1) == 10.0


def test_glyph_bbox_height_uses_bounds_pen_without_glyf_table() -> None:
    ttf = cast(
        TrueTypeFont,
        _TTFStub(inner=_InnerStub(glyph_set=_GlyphSet(A=_GlyphStub()))),
    )

    assert _glyph_bbox_height(ttf, 1) == 10.0


def test_glyph_bbox_height_bounds_pen_empty_and_failure_paths() -> None:
    missing_glyph = cast(TrueTypeFont, _TTFStub(inner=_InnerStub()))
    assert _glyph_bbox_height(missing_glyph, 1) == 0.0

    empty_bounds = cast(
        TrueTypeFont,
        _TTFStub(
            inner=_InnerStub(glyph_set=_GlyphSet(A=_GlyphStub(draw_bounds=False)))
        ),
    )
    assert _glyph_bbox_height(empty_bounds, 1) == 0.0

    failing_draw = cast(
        TrueTypeFont,
        _TTFStub(inner=_InnerStub(glyph_set=_GlyphSet(A=_GlyphStub(fail=True)))),
    )
    assert _glyph_bbox_height(failing_draw, 1) == 0.0


def test_embed_subset_bytes_requires_descriptor_and_creates_font_file2() -> None:
    with pytest.raises(ValueError, match="no /FontDescriptor"):
        _embed_subset_bytes(PDTrueTypeFont(), b"abc", "ABCDEF")

    font = PDTrueTypeFont()
    descriptor = PDFontDescriptor()
    descriptor.set_font_name("Example")
    font.set_font_descriptor(descriptor)
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Example")

    _embed_subset_bytes(font, b"subset", "ABCDEF")

    embedded = descriptor.get_font_file2()
    assert embedded is not None
    assert embedded.to_byte_array() == b"subset"
    assert font.get_name() == "ABCDEF+Example"
    assert descriptor.get_font_name() == "ABCDEF+Example"
