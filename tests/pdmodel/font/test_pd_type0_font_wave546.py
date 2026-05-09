from __future__ import annotations

import io
from types import SimpleNamespace

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font


def test_wave546_predefined_cmap_parse_failure_is_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.fontbox.cmap import CMapParser

    calls: list[str] = []

    def parse_predefined(name: str) -> object:
        calls.append(name)
        raise OSError("missing cmap")

    font = PDType0Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("Encoding"), "Missing-H")
    monkeypatch.setattr(CMapParser, "parse_predefined", parse_predefined)

    assert font.get_cmap() is None
    assert font.get_cmap() is None
    assert calls == ["Missing-H"]


def test_wave546_to_unicode_predefined_parse_failure_is_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.fontbox.cmap import CMapParser

    calls: list[str] = []

    def parse_predefined(name: str) -> object:
        calls.append(name)
        raise OSError("missing unicode cmap")

    font = PDType0Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("ToUnicode"), "Missing-UCS2")
    monkeypatch.setattr(CMapParser, "parse_predefined", parse_predefined)

    assert font.get_to_unicode_cmap() is None
    assert font.get_to_unicode_cmap() is None
    assert calls == ["Missing-UCS2"]


def test_wave546_ucs2_fallback_skips_identity_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    monkeypatch.setattr(
        font,
        "get_cid_system_info",
        lambda: SimpleNamespace(
            get_registry=lambda: "Adobe",
            get_ordering=lambda: "Identity",
        ),
    )

    assert font.get_cmap_ucs2() is None


def test_wave546_code_to_cid_falls_back_to_descendant_for_unmapped_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    cmap = SimpleNamespace(
        has_cid_mappings=lambda: True,
        to_cid=lambda _code: 0,
    )
    descendant = SimpleNamespace(code_to_cid=lambda code: code + 1000)
    monkeypatch.setattr(font, "get_cmap", lambda: cmap)
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)

    assert font.code_to_cid(41) == 1041
    assert font.code_to_cid(0) == 0


def test_wave546_read_stream_with_non_seekable_source_ignores_rewind_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NonSeekable(io.BytesIO):
        def seek(self, *_args: object) -> int:
            raise OSError("not seekable")

    font = PDType0Font()
    stream = NonSeekable(b"abcdef")
    monkeypatch.setattr(font, "read_code", lambda _data, _offset: (0xCAFE, 2))

    assert font.read(stream) == 0xCAFE


def test_wave546_get_descendant_font_wraps_only_first_dictionary() -> None:
    descendant_dict = COSDictionary()
    descendant_dict.set_name(COSName.SUBTYPE, PDCIDFontType2.SUB_TYPE)  # type: ignore[attr-defined]
    fonts = COSArray()
    fonts.add(descendant_dict)
    fonts.add(COSStream())
    font = PDType0Font()
    font.get_cos_object().set_item(COSName.get_pdf_name("DescendantFonts"), fonts)

    assert isinstance(font.get_descendant_font(), PDCIDFontType2)

    malformed = PDType0Font()
    bad_fonts = COSArray()
    bad_fonts.add(COSStream())
    malformed.get_cos_object().set_item(
        COSName.get_pdf_name("DescendantFonts"), bad_fonts
    )
    assert malformed.get_descendant_font() is None

