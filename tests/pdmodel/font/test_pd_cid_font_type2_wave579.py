from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor


def _font_with_font_file2(data: bytes) -> PDCIDFontType2:
    font = PDCIDFontType2()
    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(data)
    descriptor.set_font_file2(stream)
    font.set_font_descriptor(descriptor)
    return font


def test_wave579_get_true_type_font_caches_parse_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bytes] = []

    def fail_parse(data: bytes) -> Any:
        calls.append(data)
        raise OSError("not a ttf")

    monkeypatch.setattr(
        "pypdfbox.pdmodel.font.pd_cid_font_type2.TrueTypeFont.from_bytes",
        fail_parse,
    )
    font = _font_with_font_file2(b"broken-font")

    assert font.get_true_type_font() is None
    assert font.get_true_type_font() is None
    assert calls == [b"broken-font"]
    assert font.is_damaged() is True


def test_wave579_set_true_type_font_none_sets_negative_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(_data: bytes) -> Any:
        raise AssertionError("cached None should not parse embedded bytes")

    monkeypatch.setattr(
        "pypdfbox.pdmodel.font.pd_cid_font_type2.TrueTypeFont.from_bytes",
        fail_if_called,
    )
    font = _font_with_font_file2(b"would-parse-if-cache-was-clear")

    font.set_true_type_font(None)

    assert font.get_true_type_font() is None
    assert font.is_embedded() is True
    assert font.is_damaged() is True


def test_wave579_get_average_font_width_falls_back_for_non_positive_upem() -> None:
    class ZeroUnitsTTF:
        def get_units_per_em(self) -> int:
            return 0

        @property
        def advance_widths(self) -> list[int]:
            return [300, 600]

    font = PDCIDFontType2()
    font.get_true_type_font = lambda: ZeroUnitsTTF()  # type: ignore[method-assign]
    font.set_dw(812)

    assert font.get_average_font_width() == pytest.approx(812.0)

