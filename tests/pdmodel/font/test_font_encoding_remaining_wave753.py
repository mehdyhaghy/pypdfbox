from __future__ import annotations

from typing import cast

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSStream
from pypdfbox.fontbox.cmap import CMapParser
from pypdfbox.fontbox.font_box_font import FontBoxFont
from pypdfbox.fontbox.font_mapper import FontMapper
from pypdfbox.fontbox.font_mapping import FontMapping
from pypdfbox.pdmodel.font import PDFont
from pypdfbox.pdmodel.font.encoding.encoding import Encoding
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory


class _BarePDFont(PDFont):
    SUB_TYPE = None


class _NamedEncoding(Encoding):
    def get_encoding_name(self) -> str:
        return "WaveEncoding"


class _RecordingMapper(FontMapper):
    def __init__(self) -> None:
        self.calls: list[tuple[str, object | None]] = []
        self.mapping = FontMapping(cast(FontBoxFont, object()), False)

    def get_true_type_font(
        self,
        base_font: str,
        font_descriptor: object | None,
    ) -> None:
        return None

    def get_open_type_font(
        self,
        base_font: str,
        font_descriptor: object | None,
    ) -> None:
        return None

    def get_font_box_font(
        self,
        base_font: str,
        font_descriptor: object | None,
    ) -> FontMapping[FontBoxFont]:
        self.calls.append((base_font, font_descriptor))
        return self.mapping


def test_encoding_base_cos_object_and_remaining_membership_edges() -> None:
    enc = Encoding()
    enc.add(65, "A")

    assert enc.get_encoding_name() is None
    assert enc.get_cos_object() is None
    assert enc.contains(object()) is False
    assert (True in enc) is False
    assert (object() in enc) is False
    assert enc.get_codes_for_name(None) == []

    codes = enc.get_codes()
    codes[66] = "B"
    assert enc.get_codes() == {65: "A"}


def test_encoding_named_cos_object_returns_pdf_name() -> None:
    cos_object = _NamedEncoding().get_cos_object()

    assert cos_object == COSName.get_pdf_name("WaveEncoding")


def test_pdfont_space_width_clamps_negative_first_char_to_zero() -> None:
    font = _BarePDFont()
    cos = font.get_cos_object()
    cos.set_int(COSName.get_pdf_name("FirstChar"), -10)
    cos.set_item(COSName.get_pdf_name("Widths"), COSArray([COSInteger.get(333)] * 33))

    assert font.get_space_width() == 333.0


def test_pdfont_to_unicode_stream_parse_errors_cache_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_value_error(self: CMapParser, data: bytes) -> object:
        assert data == b"not a cmap"
        raise ValueError("bad cmap")

    monkeypatch.setattr(CMapParser, "parse", raise_value_error)

    stream = COSStream()
    stream.set_raw_data(b"not a cmap")
    font = _BarePDFont()
    font.get_cos_object().set_item(COSName.get_pdf_name("ToUnicode"), stream)

    assert font.get_to_unicode_cmap() is None
    assert font.get_to_unicode_cmap() is None


def test_pdfont_factory_mapper_hooks_delegate_to_active_mapper() -> None:
    mapper = _RecordingMapper()
    try:
        PDFontFactory.set_font_mapper(mapper)

        assert PDFontFactory.get_font_mapper() is mapper
        assert PDFontFactory.find_font_box_font("Helvetica") is mapper.mapping
        assert mapper.calls == [("Helvetica", None)]
    finally:
        PDFontFactory.set_font_mapper(None)
