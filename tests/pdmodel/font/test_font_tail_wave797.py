from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.fontbox.cmap import CMapParser
from pypdfbox.fontbox.encoding.glyph_list import GlyphList
from pypdfbox.pdmodel.font.encoding.dictionary_encoding import DictionaryEncoding
from pypdfbox.pdmodel.font.encoding.encoding import Encoding
from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import WinAnsiEncoding
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font import PDFont
from pypdfbox.pdmodel.font.pd_simple_font import PDSimpleFont
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont

_BASE_FONT = COSName.get_pdf_name("BaseFont")
_CID_TO_GID_MAP = COSName.get_pdf_name("CIDToGIDMap")
_DIFFERENCES = COSName.get_pdf_name("Differences")
_ENCODING = COSName.get_pdf_name("Encoding")
_FIRST_CHAR = COSName.get_pdf_name("FirstChar")
_TO_UNICODE = COSName.get_pdf_name("ToUnicode")
_WIDTHS = COSName.get_pdf_name("Widths")


class _BarePDFont(PDFont):
    SUB_TYPE = None


class _NamedEncoding(Encoding):
    def get_encoding_name(self) -> str:
        return "WaveTailEncoding"


class _UnknownEncoding(Encoding):
    pass


class _NamelessEncoding(Encoding):
    def __init__(self) -> None:
        super().__init__()
        self.add(70, "F")


class _EmptyCharsetCFF(CFFFont):
    units_per_em = 1000

    def get_charset(self) -> list[str]:
        return []

    def has_glyph(self, name: str) -> bool:
        return name == "A"


def test_encoding_base_helpers_handle_nameless_and_non_member_inputs() -> None:
    enc = Encoding()
    enc.add(65, "A")

    assert enc.get_cos_object() is None
    assert enc.contains(object()) is False
    assert (object() in enc) is False
    assert enc.get_codes_for_name(None) == []

    codes = enc.get_codes()
    codes[66] = "B"
    assert enc.get_codes() == {65: "A"}

    assert _NamedEncoding().get_cos_object() == COSName.get_pdf_name(
        "WaveTailEncoding"
    )


def test_dictionary_encoding_clears_base_encoding_for_nameless_encoding() -> None:
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))

    enc.set_base_encoding(_NamelessEncoding())

    assert enc.get_base_encoding_name() is None
    assert enc.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("BaseEncoding")
    ) is None
    assert enc.get_name(70) == "F"


def test_pdfont_space_width_clamps_negative_first_char_to_zero() -> None:
    font = _BarePDFont()
    cos = font.get_cos_object()
    cos.set_int(_FIRST_CHAR, -4)
    cos.set_item(_WIDTHS, COSArray([COSInteger.get(333)] * 33))

    assert font.get_space_width() == 333.0


def test_pdfont_to_unicode_absent_and_malformed_stream_are_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _BarePDFont().get_to_unicode_cmap() is None

    def raise_value_error(self: CMapParser, data: bytes) -> object:
        assert data == b"not a cmap"
        raise ValueError("bad cmap")

    monkeypatch.setattr(CMapParser, "parse", raise_value_error)

    stream = COSStream()
    stream.set_raw_data(b"not a cmap")
    font = _BarePDFont()
    font.get_cos_object().set_item(_TO_UNICODE, stream)

    assert font.has_to_unicode() is True
    assert font.get_to_unicode_cmap() is None
    assert font.get_to_unicode_cmap() is None


def test_simple_font_zapf_encoding_uses_zapf_glyph_list() -> None:
    raw = COSDictionary()
    raw.set_item(_ENCODING, COSName.get_pdf_name("ZapfDingbatsEncoding"))
    font = PDSimpleFont(raw)

    assert font.get_glyph_list() is GlyphList.ZAPF_DINGBATS
    assert font.decode(b"\x21") == "\u2701"


def test_simple_font_symbolic_detection_returns_none_for_unknown_encoding() -> None:
    font = PDSimpleFont(COSDictionary())
    font._encoding_typed = _UnknownEncoding()  # type: ignore[attr-defined]
    font._encoding_resolved = True  # type: ignore[attr-defined]

    assert font.is_font_symbolic() is None


def test_simple_font_dictionary_differences_common_names_are_nonsymbolic() -> None:
    encoding = COSDictionary()
    encoding.set_item(
        _DIFFERENCES,
        COSArray([COSInteger.get(65), COSName.get_pdf_name("A")]),
    )
    font = PDSimpleFont(COSDictionary())
    font._encoding_typed = DictionaryEncoding(
        font_encoding=encoding,
        is_non_symbolic=False,
        built_in=WinAnsiEncoding.INSTANCE,
    )
    font._encoding_resolved = True  # type: ignore[attr-defined]

    assert font.is_font_symbolic() is False


def test_cid_identity_map_defaults_to_identity_when_absent() -> None:
    font = PDCIDFontType2()

    assert font.get_cid_to_gid_map() is None
    assert font.is_identity_cid_to_gid_map() is True

    stream = COSStream()
    font.get_cos_object().set_item(_CID_TO_GID_MAP, stream)
    assert font.has_cid_to_gid_map_stream() is True


def test_type1c_empty_charset_maps_encoded_glyph_to_notdef_gid() -> None:
    raw = COSDictionary()
    raw.set_name(_BASE_FONT, "CustomCFF")
    raw.set_item(_ENCODING, COSName.get_pdf_name("WinAnsiEncoding"))
    font = PDType1CFont(raw)
    font.set_font_program(_EmptyCharsetCFF())

    assert font.code_to_gid(65) == 0
