from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSFloat
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor


class _MissingGlyphTable:
    def __contains__(self, key: str) -> bool:
        return key in {"glyf", "head"}

    def getGlyphOrder(self) -> list[str]:  # noqa: N802 - fontTools API
        return [".notdef", "A"]

    def __getitem__(self, key: str) -> Any:
        if key == "head":
            return SimpleNamespace()
        raise KeyError(key)


class _BrokenHeadTable:
    def __contains__(self, key: str) -> bool:
        return key == "head"

    def __getitem__(self, key: str) -> Any:
        if key == "head":
            return SimpleNamespace(xMin=-10.0, yMin=-20.0)
        raise KeyError(key)


class _StubTTF:
    def __init__(self, inner: object, units_per_em: int = 1000) -> None:
        self._tt = inner
        self._units_per_em = units_per_em

    def get_units_per_em(self) -> int:
        return self._units_per_em

    def get_advance_width(self, gid: int) -> int:
        return 500 if gid > 0 else 0

    @property
    def advance_widths(self) -> list[int]:
        return [0, 500]


def _font_with_ttf(ttf: object) -> PDCIDFontType2:
    font = PDCIDFontType2()
    font.get_true_type_font = lambda: ttf  # type: ignore[method-assign]
    return font


def _w2_height(cid: int, height: float) -> COSArray:
    return COSArray(
        [
            COSFloat(cid),
            COSArray([COSFloat(height), COSFloat(0.0), COSFloat(880.0)]),
        ]
    )


def test_get_height_falls_back_to_w2_when_cid_mapping_fails() -> None:
    font = _font_with_ttf(_StubTTF(_MissingGlyphTable()))
    font.set_w2(_w2_height(4, 777.0))

    def raise_mapping(_cid: int) -> int:
        raise RuntimeError("bad cid map")

    font.cid_to_gid = raise_mapping  # type: ignore[method-assign]

    assert font.get_height(4) == pytest.approx(777.0)


def test_get_height_returns_zero_when_glyf_lookup_raises_key_error() -> None:
    font = _font_with_ttf(_StubTTF(_MissingGlyphTable()))

    assert font.get_height(1) == 0.0


def test_get_font_matrix_uses_default_when_units_per_em_raises() -> None:
    class BrokenUnitsTTF(_StubTTF):
        def get_units_per_em(self) -> int:
            raise RuntimeError("bad head")

    font = _font_with_ttf(BrokenUnitsTTF(_MissingGlyphTable()))

    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


def test_get_bounding_box_falls_back_when_embedded_head_is_incomplete() -> None:
    font = _font_with_ttf(_StubTTF(_BrokenHeadTable()))
    descriptor = PDFontDescriptor()
    descriptor.set_font_b_box(
        COSArray([COSFloat(-50), COSFloat(-25), COSFloat(1050), COSFloat(950)])
    )
    font.set_font_descriptor(descriptor)

    bbox = font.get_bounding_box()

    assert bbox is not None
    assert bbox.lower_left_x == pytest.approx(-50.0)
    assert bbox.lower_left_y == pytest.approx(-25.0)
    assert bbox.upper_right_x == pytest.approx(1050.0)
    assert bbox.upper_right_y == pytest.approx(950.0)


def test_has_glyph_falls_back_to_width_tables_when_gid_mapping_fails() -> None:
    font = _font_with_ttf(_StubTTF(_MissingGlyphTable()))
    font.set_dw(0)
    widths = COSArray(
        [
            COSFloat(9),
            COSArray([COSFloat(444.0)]),
        ]
    )
    font.set_w(widths)

    def raise_mapping(_cid: int) -> int:
        raise RuntimeError("bad cid map")

    font.cid_to_gid = raise_mapping  # type: ignore[method-assign]

    assert font.has_glyph(9) is True
    assert font.has_glyph(10) is False
