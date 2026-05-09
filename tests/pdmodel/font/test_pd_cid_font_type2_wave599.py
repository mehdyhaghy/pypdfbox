from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2


class _BrokenAdvanceTTF:
    def get_advance_width(self, _gid: int) -> int:
        raise RuntimeError("hmtx unavailable")

    def get_units_per_em(self) -> int:
        return 1000


class _PathGlyph:
    def draw(self, pen: Any) -> None:
        pen.moveTo((10, 20))
        pen.lineTo((30, 40))
        pen.closePath()


class _PathTable:
    def getGlyphName(self, gid: int) -> str:  # noqa: N802 - fontTools API
        if gid != 1:
            raise KeyError(gid)
        return "A"

    def getGlyphSet(self) -> dict[str, _PathGlyph]:  # noqa: N802 - fontTools API
        return {"A": _PathGlyph()}


class _PathTTF:
    _tt = _PathTable()

    def get_units_per_em(self) -> int:
        return 2000


def _stream(data: bytes) -> COSStream:
    stream = COSStream()
    stream.set_data(data)
    return stream


def test_wave599_cid_to_gid_stream_ignores_dangling_byte_and_setter_clears_cache() -> None:
    font = PDCIDFontType2()
    font.set_cid_to_gid_map(_stream(b"\x00\x05\x00"))

    assert font.has_cid_to_gid_map() is True
    assert font.get_cid_to_gid_map_bytes() == b"\x00\x05\x00"
    assert font.cid_to_gid(0) == 5
    assert font.cid_to_gid(1) == 0

    font.set_cid_to_gid_map("Identity")

    assert font.has_cid_to_gid_map() is False
    assert font.is_identity_cid_to_gid_map() is True
    assert font.cid_to_gid(42) == 42


def test_wave599_width_from_font_returns_zero_when_advance_lookup_fails() -> None:
    font = PDCIDFontType2()
    font.get_true_type_font = lambda: _BrokenAdvanceTTF()  # type: ignore[method-assign]

    assert font.get_width_from_font(7) == 0.0


def test_wave599_normalized_path_scales_coordinates_and_preserves_closepath() -> None:
    font = PDCIDFontType2()
    font.get_true_type_font = lambda: _PathTTF()  # type: ignore[method-assign]

    assert font.get_normalized_path(1) == [
        ("moveto", pytest.approx(5.0), pytest.approx(10.0)),
        ("lineto", pytest.approx(15.0), pytest.approx(20.0)),
        ("closepath",),
    ]
