from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.type1.type1_font import Type1Font


class _FakeT1:
    def __init__(self, font: dict[str, Any] | None = None) -> None:
        self.font = font if font is not None else {"CharStrings": {".notdef": b""}}

    def __getitem__(self, key: str) -> Any:
        return self.font[key]


class _FakeProgram:
    font = {"CharStrings": {".notdef": b""}}

    def __getitem__(self, key: str) -> Any:
        return self.font[key]


class _BrokenCharString:
    def draw(self, pen: object) -> None:
        del pen
        msg = "cannot draw"
        raise ValueError(msg)


def _font_with(font_dict: dict[str, Any]) -> Type1Font:
    font = Type1Font()
    font._t1 = _FakeT1(font_dict)  # noqa: SLF001
    return font


def test_wave474_from_bytes_normalizes_hex_and_binary_eexec_chunks(
    monkeypatch: Any,
) -> None:
    import fontTools.t1Lib

    chunks = [
        (False, b"%!PS-AdobeFont-1.0\n"),
        (True, b"41424344"),
        (True, b"\x01\x02"),
    ]

    monkeypatch.setattr(fontTools.t1Lib, "T1Font", _FakeProgram)
    monkeypatch.setattr(fontTools.t1Lib, "assertType1", lambda raw: None)
    monkeypatch.setattr(fontTools.t1Lib, "findEncryptedChunks", lambda raw: chunks)
    monkeypatch.setattr(fontTools.t1Lib, "isHex", lambda chunk: chunk == b"4142")
    monkeypatch.setattr(fontTools.t1Lib, "deHexString", lambda chunk: b"ABCD")

    font = Type1Font.from_bytes(memoryview(b"raw-type1"))

    assert font.get_ascii_segment() == b"%!PS-AdobeFont-1.0\n"
    assert font.get_binary_segment() == b"ABCD\x01\x02"
    assert font._t1.data == b"%!PS-AdobeFont-1.0\nABCD\x01\x02"  # noqa: SLF001
    assert font._t1.encoding == "ascii"  # noqa: SLF001
    assert font.has_glyph(".notdef") is True


def test_wave474_font_matrix_and_numeric_font_info_bad_values_default() -> None:
    font = _font_with(
        {
            "FontName": "Wave474",
            "FontMatrix": ["bad"],
            "FontInfo": {
                "ItalicAngle": object(),
                "UnderlinePosition": object(),
                "UnderlineThickness": object(),
                "isFixedPitch": 1,
            },
        }
    )
    short_matrix = _font_with({"FontName": "Wave474", "FontMatrix": [0.001]})

    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    assert short_matrix.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    assert font.get_italic_angle() == 0.0
    assert font.get_underline_position() == 0.0
    assert font.get_underline_thickness() == 0.0
    assert font.get_is_fixed_pitch() is True


def test_wave474_missing_glyph_and_broken_charstring_return_empty_results() -> None:
    font = _font_with(
        {
            "FontName": "Wave474",
            "CharStrings": {
                ".notdef": b"",
                "broken": _BrokenCharString(),
            },
        }
    )

    assert font.get_width("missing") == 0.0
    assert font.get_path("missing") == []
    assert font.get_width("broken") == 0.0
    assert font.get_path("broken") == []
