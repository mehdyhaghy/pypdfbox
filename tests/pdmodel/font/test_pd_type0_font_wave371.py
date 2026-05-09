"""Wave 371 coverage for cold PDType0Font branches.

These tests stay synthetic: tiny COS dictionaries, fake CMaps, and defensive
parser monkeypatches exercise Type0 fallback paths without external fonts.
"""

from __future__ import annotations

import io
from types import SimpleNamespace

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font, _read_font_bytes

_DESCENDANT_FONTS = COSName.get_pdf_name("DescendantFonts")
_ENCODING = COSName.get_pdf_name("Encoding")
_TO_UNICODE = COSName.get_pdf_name("ToUnicode")


def _font_with_encoding(name: str | None = None) -> PDType0Font:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Type0")  # type: ignore[attr-defined]
    raw.set_name(COSName.get_pdf_name("BaseFont"), "Wave371")
    if name is not None:
        raw.set_name(_ENCODING, name)
    return PDType0Font(raw)


class _UnicodeCMap:
    def __init__(self, mapping: dict[int, str], *, codes: bytes | None = None) -> None:
        self._mapping = mapping
        self._codes = codes

    def has_unicode_mappings(self) -> bool:
        return True

    def to_unicode(self, code: int) -> str | None:
        return self._mapping.get(code)

    def get_codes_from_unicode(self, _text: str) -> bytes | None:
        return self._codes

    def get_name(self) -> str:
        return "Custom-H"

    def code_length_at(self, _offset: int) -> int:
        return 3


def test_descendant_array_non_dictionary_entry_returns_none() -> None:
    raw = COSDictionary()
    arr = COSArray()
    arr.add(COSInteger.get(7))
    raw.set_item(_DESCENDANT_FONTS, arr)

    assert PDType0Font(raw).get_descendant_font() is None


def test_unknown_descendant_subtype_returns_none() -> None:
    raw = COSDictionary()
    arr = COSArray()
    desc = COSDictionary()
    desc.set_name(COSName.SUBTYPE, "CIDFontType99")  # type: ignore[attr-defined]
    arr.add(desc)
    raw.set_item(_DESCENDANT_FONTS, arr)

    assert PDType0Font(raw).get_descendant_font() is None


def test_get_font_descriptor_none_without_own_or_descendant_descriptor() -> None:
    assert PDType0Font().get_font_descriptor() is None


def test_get_cmap_swallows_predefined_parser_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    from pypdfbox.fontbox.cmap import CMapParser

    def raise_oserror(_name: str) -> None:
        raise OSError("missing predefined cmap")

    monkeypatch.setattr(CMapParser, "parse_predefined", raise_oserror)

    assert _font_with_encoding("Missing-CMap").get_cmap() is None


def test_get_cmap_swallows_embedded_stream_parse_valueerror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.fontbox.cmap import CMapParser

    def raise_valueerror(self: CMapParser, _data: bytes) -> None:
        raise ValueError("bad cmap")

    monkeypatch.setattr(CMapParser, "parse", raise_valueerror)
    font = _font_with_encoding(None)
    stream = COSStream()
    stream.set_data(b"not a cmap")
    font.get_cos_object().set_item(_ENCODING, stream)

    assert font.get_cmap() is None


def test_to_unicode_predefined_name_parser_failure_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.fontbox.cmap import CMapParser

    def raise_oserror(_name: str) -> None:
        raise OSError("missing predefined cmap")

    monkeypatch.setattr(CMapParser, "parse_predefined", raise_oserror)
    font = _font_with_encoding(None)
    font.get_cos_object().set_name(_TO_UNICODE, "Missing-ToUnicode")

    assert font.get_to_unicode_cmap() is None


def test_to_unicode_uses_encoding_cmap_unicode_mapping() -> None:
    font = _font_with_encoding(None)
    font._cmap_loaded = True  # noqa: SLF001
    font._cmap = _UnicodeCMap({0x41: "A"})  # noqa: SLF001

    assert font.to_unicode(0x41) == "A"


def test_to_unicode_uses_ucs2_fallback_after_cid_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = _font_with_encoding(None)
    monkeypatch.setattr(font, "get_cmap_ucs2", lambda: _UnicodeCMap({5: "five"}))
    monkeypatch.setattr(font, "code_to_cid", lambda code: code + 4)

    assert font.to_unicode(1) == "five"


def test_has_explicit_writing_mode_true_for_stream_dictionary_entry() -> None:
    font = _font_with_encoding(None)
    stream = COSStream()
    stream.set_item(COSName.get_pdf_name("WMode"), COSInteger.get(1))
    font.get_cos_object().set_item(_ENCODING, stream)

    assert font.has_explicit_writing_mode() is True


def test_read_stream_seeks_back_overread_when_cmap_consumes_one_byte() -> None:
    font = _font_with_encoding(None)
    stream = io.BytesIO(b"ABCD")

    assert font.read(stream) == ord("A")
    assert stream.read() == b"BCD"


def test_decode_one_forwards_offset_to_read_code() -> None:
    font = _font_with_encoding("Identity-H")

    assert font.decode_one(b"\x00\x00\x12\x34", 2) == (0x1234, 2)


def test_encode_int_uses_single_codepoint_path() -> None:
    font = _font_with_encoding("Identity-H")

    assert font.encode(0x1041) == b"\x10\x41"


def test_encode_codepoint_uses_cmap_reverse_mapping() -> None:
    cmap = _UnicodeCMap({}, codes=b"\x01\x02")

    assert PDType0Font._encode_codepoint(ord("A"), cmap) == b"\x01\x02"


def test_encode_codepoint_handles_reverse_lookup_exception() -> None:
    cmap = SimpleNamespace(
        get_codes_from_unicode=lambda _text: (_ for _ in ()).throw(RuntimeError),
        get_name=lambda: "Custom-H",
        code_length_at=lambda _offset: 3,
    )

    assert PDType0Font._encode_codepoint(ord("A"), cmap) == b"\x00\x00\x00"


def test_read_font_bytes_rejects_non_readable_source() -> None:
    with pytest.raises(TypeError, match="cannot read font bytes"):
        _read_font_bytes(object())  # type: ignore[arg-type]
