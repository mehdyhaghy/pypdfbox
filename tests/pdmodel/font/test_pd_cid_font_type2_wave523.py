from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2


class _NoGlyphTableInner:
    def __contains__(self, key: str) -> bool:
        return False


class _SparseGlyphInner:
    def __contains__(self, key: str) -> bool:
        return key == "glyf"

    def getGlyphOrder(self) -> list[str]:  # noqa: N802 - fontTools API
        return [".notdef"]

    def __getitem__(self, key: str) -> Any:
        raise KeyError(key)


class _StubTTF:
    def __init__(self, inner: object, units_per_em: int = 1000) -> None:
        self._tt = inner
        self._units_per_em = units_per_em

    def get_units_per_em(self) -> int:
        return self._units_per_em

    def get_advance_width(self, gid: int) -> int:
        return 500 if gid == 1 else 0

    @property
    def advance_widths(self) -> list[int]:
        return [0, 500]


def _stream(data: bytes) -> COSStream:
    stream = COSStream()
    stream.set_data(data)
    return stream


def _font_with_stub_ttf(stub: _StubTTF) -> PDCIDFontType2:
    font = PDCIDFontType2()
    font.get_true_type_font = lambda: stub  # type: ignore[method-assign]
    return font


def test_cid_to_gid_stream_ignores_trailing_odd_byte_and_bounds() -> None:
    font = PDCIDFontType2()
    font.set_cid_to_gid_map(_stream(b"\x00\x05\x01"))

    assert font.has_cid_to_gid_map() is True
    assert font.cid_to_gid(0) == 5
    assert font.cid_to_gid(1) == 0
    assert font.cid_to_gid(-1) == 0


def test_cid_to_gid_cache_is_cleared_when_map_replaced() -> None:
    font = PDCIDFontType2()
    font.set_cid_to_gid_map(_stream(b"\x00\x02"))
    assert font.cid_to_gid(0) == 2

    font.set_cid_to_gid_map(_stream(b"\x00\x09"))

    assert font.cid_to_gid(0) == 9
    assert font.get_cid_to_gid_map_bytes() == b"\x00\x09"


def test_identity_name_after_stream_restores_identity_mapping() -> None:
    font = PDCIDFontType2()
    font.set_cid_to_gid_map(_stream(b"\x00\x04"))
    assert font.cid_to_gid(0) == 4

    font.set_cid_to_gid_map("Identity")

    assert font.has_cid_to_gid_map() is False
    assert font.is_identity_cid_to_gid_map() is True
    assert font.cid_to_gid(17) == 17


def test_get_height_returns_zero_when_embedded_font_has_no_glyf_table() -> None:
    font = _font_with_stub_ttf(_StubTTF(_NoGlyphTableInner()))

    assert font.get_height(1) == 0.0


def test_get_height_returns_zero_when_gid_is_outside_glyph_order() -> None:
    font = _font_with_stub_ttf(_StubTTF(_SparseGlyphInner()))
    font.set_cid_to_gid_map(_stream(b"\x00\x02"))

    assert font.get_height(0) == 0.0


def test_get_width_from_font_swallows_metric_lookup_errors() -> None:
    class BrokenMetricsTTF(_StubTTF):
        def get_advance_width(self, gid: int) -> int:
            raise RuntimeError("broken hmtx")

    font = _font_with_stub_ttf(BrokenMetricsTTF(_NoGlyphTableInner()))

    assert font.get_width_from_font(1) == 0.0


def test_get_average_font_width_falls_back_when_advances_unreadable() -> None:
    class BrokenAverageTTF(_StubTTF):
        @property
        def advance_widths(self) -> list[int]:
            raise RuntimeError("broken hmtx")

    font = _font_with_stub_ttf(BrokenAverageTTF(_NoGlyphTableInner()))
    font.set_dw(733)

    assert font.get_average_font_width() == pytest.approx(733.0)
