"""PDFBOX-6292 (space width of a substitute-encoded Identity-H font),
PDFBOX-6293 (foreign Identity CID substitute for CIDFontType2) and the
PDFBOX-6287 follow-ups (per-codepoint string-width cache, default
``read_code``)."""

from pathlib import Path
from typing import Any

import pytest

from pypdfbox import PDDocument
from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.fontbox.font_mappers import FontMappers
from pypdfbox.pdmodel.font import PDType0Font
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

from .upstream.test_identity_cjk_substitute import (
    ZHONG,
    ZHONG_GID,
    _build_substitute,
    _FixtureMapper,
    type0,
)

_CID_FONT_TYPE0 = COSName.get_pdf_name("CIDFontType0")
_CID_FONT_TYPE2 = COSName.get_pdf_name("CIDFontType2")
_CID_SYSTEM_INFO = COSName.get_pdf_name("CIDSystemInfo")
_TO_UNICODE = COSName.get_pdf_name("ToUnicode")

_TTF = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture
def identity_substitute() -> Any:
    otf = _build_substitute()
    FontMappers.set(_FixtureMapper(otf))
    try:
        yield otf
    finally:
        FontMappers.reset()


def _ttf_bytes() -> bytes:
    if not _TTF.exists():
        pytest.skip(f"missing fixture {_TTF}")
    return _TTF.read_bytes()


# ---------- PDFBOX-6292: is_encoded_via_substitute ----------


def test_encoded_via_substitute_for_non_embedded_identity_h() -> None:
    font = PDType0Font(type0("SimSun", _CID_FONT_TYPE2, "Identity-H"))
    assert font.is_encoded_via_substitute()


def test_not_encoded_via_substitute_with_to_unicode() -> None:
    d = type0("SimSun", _CID_FONT_TYPE2, "Identity-H")
    d.set_name(_TO_UNICODE, "Identity-H")
    assert not PDType0Font(d).is_encoded_via_substitute()


def test_not_encoded_via_substitute_for_predefined_cmap() -> None:
    font = PDType0Font(type0("SimSun", _CID_FONT_TYPE2, "UniGB-UCS2-H"))
    assert not font.is_encoded_via_substitute()


def test_not_encoded_via_substitute_for_cid_font_type0() -> None:
    font = PDType0Font(type0("AdobeSongStd-Light", _CID_FONT_TYPE0, "Identity-H"))
    assert not font.is_encoded_via_substitute()


def test_not_encoded_via_substitute_when_embedded() -> None:
    with PDDocument() as doc:
        font = PDType0Font.load(doc, _ttf_bytes())
        assert font.is_embedded()
        assert not font.is_encoded_via_substitute()


def test_simple_font_not_encoded_via_substitute() -> None:
    assert not PDType1Font(Standard14Fonts.FontName.HELVETICA).is_encoded_via_substitute()


def test_space_width_skips_string_width_when_encoded_via_substitute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font(type0("SimSun", _CID_FONT_TYPE2, "Identity-H"))

    def _fail(text: str) -> float:
        raise AssertionError("get_string_width must not be consulted")

    monkeypatch.setattr(font, "get_string_width", _fail)
    assert font.get_space_width() == font.get_width(32)


def test_space_width_uses_string_width_otherwise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font(type0("SimSun", _CID_FONT_TYPE2, "UniGB-UCS2-H"))
    calls: list[str] = []

    def _spy(text: str) -> float:
        calls.append(text)
        return 321.0

    monkeypatch.setattr(font, "get_string_width", _spy)
    assert font.get_space_width() == 321.0
    assert calls == [" "]


# ---------- PDFBOX-6293: foreign Identity CID substitute ----------


def test_foreign_identity_substitute_detected(identity_substitute: Any) -> None:
    font = PDType0Font(type0("SimSun", _CID_FONT_TYPE2, "UniGB-UCS2-H"))
    cid_font = font.get_descendant_font()
    assert isinstance(cid_font, PDCIDFontType2)
    assert cid_font._is_foreign_cid_substitute()
    assert cid_font.code_to_gid(ZHONG) == ZHONG_GID
    assert cid_font.has_glyph(ZHONG)


def test_same_collection_identity_substitute_uses_cid(
    identity_substitute: Any,
) -> None:
    # the PDF's ROS equals the substitute's (Adobe-Identity): CIDs are GIDs
    d = type0("SimSun", _CID_FONT_TYPE2, "UniGB-UCS2-H")
    descendant = d.get_dictionary_object(COSName.get_pdf_name("DescendantFonts"))
    ros = descendant.get_object(0).get_dictionary_object(_CID_SYSTEM_INFO)
    ros.set_item(COSName.get_pdf_name("Ordering"), COSString("Identity"))
    font = PDType0Font(d)
    cid_font = font.get_descendant_font()
    assert not cid_font._is_foreign_cid_substitute()
    assert cid_font.code_to_gid(ZHONG) == cid_font.code_to_cid(ZHONG) == 4559


def test_non_identity_cid_substitute_is_not_foreign(identity_substitute: Any) -> None:
    identity_substitute.get_cff().set_ordering("Japan1")
    font = PDType0Font(type0("SimSun", _CID_FONT_TYPE2, "UniGB-UCS2-H"))
    cid_font = font.get_descendant_font()
    assert not cid_font._is_foreign_cid_substitute()
    assert cid_font.code_to_gid(ZHONG) == 4559


def test_true_type_substitute_is_not_foreign() -> None:
    # default mapper: the bundled last-resort TrueType font
    font = PDType0Font(type0("SimSun", _CID_FONT_TYPE2, "UniGB-UCS2-H"))
    cid_font = font.get_descendant_font()
    assert not cid_font._is_foreign_cid_substitute()


def test_embedded_font_is_never_foreign() -> None:
    with PDDocument() as doc:
        font = PDType0Font.load(doc, _ttf_bytes())
        assert not font.get_descendant_font()._is_foreign_cid_substitute()


def test_foreign_check_without_cid_system_info(identity_substitute: Any) -> None:
    font = PDType0Font(type0("SimSun", _CID_FONT_TYPE2, "UniGB-UCS2-H"))
    cid_font = font.get_descendant_font()
    cid_font.get_cos_object().remove_item(_CID_SYSTEM_INFO)
    assert cid_font._is_foreign_cid_font(identity_substitute)
    assert not cid_font._is_foreign_cid_font(None)


# ---------- PDFBOX-6287: per-codepoint width cache ----------


def test_simple_font_string_width_is_cached() -> None:
    font = PDType1Font(Standard14Fonts.FontName.HELVETICA)
    width = font.get_string_width("AAB")
    assert width == 2 * font.get_width(65) + font.get_width(66)
    assert font._codepoint_to_width_map == {
        65: font.get_width(65),
        66: font.get_width(66),
    }
    font._codepoint_to_width_map[65] = 1.0
    assert font.get_string_width("A") == 1.0


def test_type0_string_width_is_cached_and_matches_widths() -> None:
    with PDDocument() as doc:
        font = PDType0Font.load(doc, _ttf_bytes())
        expected = sum(
            font.get_width(int.from_bytes(font.encode(ch), "big")) for ch in "Hello"
        )
        assert font.get_string_width("Hello") == pytest.approx(expected)
        assert set(font._codepoint_to_width_map) == {ord(c) for c in "Helo"}


def test_type0_width_cache_cleared_by_descendant_set_w() -> None:
    with PDDocument() as doc:
        font = PDType0Font.load(doc, _ttf_bytes())
        cid_font = font.get_descendant_font()
        code = int.from_bytes(font.encode("A"), "big")
        assert font.get_string_width("A") > 0
        assert ord("A") in font._codepoint_to_width_map
        w = COSArray()
        w.add(COSInteger.get(cid_font.code_to_cid(code)))
        inner = COSArray()
        inner.add(COSInteger.get(123))
        w.add(inner)
        cid_font.set_w(w)
        assert font._codepoint_to_width_map == {}
        assert font.get_string_width("A") == 123.0


def test_type0_lenient_notdef_width_is_not_cached() -> None:
    with PDDocument() as doc:
        font = PDType0Font.load(doc, _ttf_bytes())
        font.get_string_width("一")
        assert 0x4E00 not in font._codepoint_to_encoding_map
        assert 0x4E00 not in font._codepoint_to_width_map


def test_bare_cid_font_clear_without_parent() -> None:
    cid_font = PDCIDFontType2(COSDictionary())
    cid_font.set_dw(500)
    assert cid_font._cid_code_to_width == {}
