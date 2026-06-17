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


def _fail_if_called(_data: bytes) -> Any:
    raise AssertionError("cached None should not parse embedded bytes")


class _ZeroUnitsTTF:
    def get_units_per_em(self) -> int:
        return 0

    @property
    def advance_widths(self) -> list[int]:
        return [300, 600]


def test_wave579_get_true_type_font_caches_parse_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bytes] = []

    class _FailParser:
        def parse_embedded(self, data: bytes) -> Any:
            calls.append(bytes(data))
            raise OSError("not a ttf")

    # ``get_true_type_font`` routes the embedded program through the
    # OTTO-sniffing ``get_parser(...).parse_embedded(...)`` (so an
    # OpenType /FontFile3 becomes an OpenTypeFont). Stub the parser to
    # prove the parse is attempted exactly once and the failure is
    # negatively cached.
    monkeypatch.setattr(
        PDCIDFontType2,
        "get_parser",
        staticmethod(lambda _data, is_embedded=True: _FailParser()),
    )
    font = _font_with_font_file2(b"broken-font")

    assert font.get_true_type_font() is None
    assert font.get_true_type_font() is None
    assert calls == [b"broken-font"]
    assert font.is_damaged() is True


def test_wave579_set_true_type_font_none_sets_negative_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pypdfbox.pdmodel.font.pd_cid_font_type2.TrueTypeFont.from_bytes",
        _fail_if_called,
    )
    font = _font_with_font_file2(b"would-parse-if-cache-was-clear")

    font.set_true_type_font(None)

    assert font.get_true_type_font() is None
    assert font.is_embedded() is True
    assert font.is_damaged() is True


def test_wave579_get_average_font_width_falls_back_for_non_positive_upem() -> None:
    font = PDCIDFontType2()
    font.get_true_type_font = lambda: _ZeroUnitsTTF()  # type: ignore[method-assign]
    font.set_dw(812)

    assert font.get_average_font_width() == pytest.approx(812.0)
