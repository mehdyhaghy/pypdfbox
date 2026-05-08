from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.type1.type1_font import Type1Font


class _FakeT1:
    def __init__(self, font: dict[str, Any]) -> None:
        self.font = font


def _font_with_encoding(encoding: Any) -> Type1Font:
    font = Type1Font()
    font._t1 = _FakeT1({"FontName": "Wave325", "Encoding": encoding})
    return font


def test_wave325_get_encoding_resolves_iso_latin1_name() -> None:
    font = _font_with_encoding("ISOLatin1Encoding")

    encoding = font.get_encoding()

    assert encoding[65] == "A"
    assert encoding[233] == "eacute"
    assert 128 not in encoding


def test_wave325_iso_latin1_encoding_returns_copy() -> None:
    font = _font_with_encoding("ISOLatin1Encoding")

    encoding = font.get_encoding()
    encoding[65] = "mutated"

    assert font.get_encoding()[65] == "A"
