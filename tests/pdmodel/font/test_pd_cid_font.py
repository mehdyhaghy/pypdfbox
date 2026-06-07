from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.font.pd_cid_font import PDCIDFont
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_cid_system_info import PDCIDSystemInfo

# ---------- subtype scaffolding ----------


def test_cid_font_type0_construction_sets_type_and_subtype() -> None:
    font = PDCIDFontType0()
    cos = font.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "Font"  # type: ignore[attr-defined]
    assert cos.get_name(COSName.SUBTYPE) == "CIDFontType0"  # type: ignore[attr-defined]
    assert font.get_subtype() == "CIDFontType0"


def test_cid_font_type2_construction_sets_type_and_subtype() -> None:
    font = PDCIDFontType2()
    cos = font.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "Font"  # type: ignore[attr-defined]
    assert cos.get_name(COSName.SUBTYPE) == "CIDFontType2"  # type: ignore[attr-defined]
    assert font.get_subtype() == "CIDFontType2"


def test_cid_font_wraps_existing_dict_without_overwriting_subtype() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "CIDFontType2")  # type: ignore[attr-defined]
    raw.set_name(COSName.get_pdf_name("BaseFont"), "Arial")
    font = PDCIDFontType0(raw)
    # Existing subtype is preserved when wrapping a pre-built dict.
    assert font.get_cos_object().get_name(COSName.SUBTYPE) == "CIDFontType2"  # type: ignore[attr-defined]


def test_cid_font_base_class_get_subtype_is_abstract() -> None:
    base = PDCIDFont(COSDictionary())
    try:
        base.get_subtype()
    except NotImplementedError:
        return
    raise AssertionError("PDCIDFont.get_subtype() must raise NotImplementedError")


# ---------- PDCIDSystemInfo round-trip ----------


def test_cid_system_info_round_trip_adobe_japan1_6() -> None:
    info = PDCIDSystemInfo()
    info.set_registry("Adobe")
    info.set_ordering("Japan1")
    info.set_supplement(6)

    info2 = PDCIDSystemInfo(info.get_cos_object())
    assert info2.get_registry() == "Adobe"
    assert info2.get_ordering() == "Japan1"
    assert info2.get_supplement() == 6
    assert str(info2) == "Adobe-Japan1-6"


def test_cid_system_info_default_supplement_is_minus_one() -> None:
    # Upstream getSupplement() returns -1 for an absent /Supplement
    # (COSDictionary.getInt one-arg default) — verified via the live oracle.
    info = PDCIDSystemInfo()
    assert info.get_supplement() == -1
    assert info.get_registry() is None
    assert info.get_ordering() is None


def test_cid_system_info_set_none_removes_entries() -> None:
    info = PDCIDSystemInfo()
    info.set_registry("Adobe")
    info.set_ordering("Japan1")
    info.set_registry(None)
    info.set_ordering(None)
    assert info.get_registry() is None
    assert info.get_ordering() is None


# ---------- PDCIDFont accessors round-trip ----------


def test_cid_font_dw_default_is_1000_when_absent() -> None:
    font = PDCIDFontType0()
    assert font.get_dw() == 1000


def test_cid_font_dw_round_trip() -> None:
    font = PDCIDFontType2()
    font.set_dw(500)
    assert font.get_dw() == 500
    # Re-wrap to verify dictionary was actually mutated.
    again = PDCIDFontType2(font.get_cos_object())
    assert again.get_dw() == 500


def test_cid_font_w_round_trip() -> None:
    font = PDCIDFontType0()
    w = COSArray([COSInteger.get(0), COSInteger.get(100), COSInteger.get(1000)])
    font.set_w(w)
    out = font.get_w()
    assert out is w
    assert out.size() == 3


def test_cid_font_w_absent_returns_none() -> None:
    assert PDCIDFontType0().get_w() is None
    assert PDCIDFontType0().get_w2() is None
    assert PDCIDFontType0().get_dw2() is None


def test_cid_font_w2_dw2_round_trip() -> None:
    font = PDCIDFontType2()
    dw2 = COSArray([COSInteger.get(880), COSInteger.get(-1000)])
    font.set_dw2(dw2)
    w2 = COSArray([COSInteger.get(120), COSInteger.get(120)])
    font.set_w2(w2)
    assert font.get_dw2() is dw2
    assert font.get_w2() is w2


def test_cid_font_set_w_none_removes_entry() -> None:
    font = PDCIDFontType0()
    font.set_w(COSArray([COSInteger.get(1)]))
    assert font.get_w() is not None
    font.set_w(None)
    assert font.get_w() is None


# ---------- /CIDSystemInfo wiring ----------


def test_cid_font_set_get_cid_system_info_round_trip() -> None:
    font = PDCIDFontType2()
    info = PDCIDSystemInfo()
    info.set_registry("Adobe")
    info.set_ordering("Japan1")
    info.set_supplement(6)
    font.set_cid_system_info(info)

    out = font.get_cid_system_info()
    assert isinstance(out, PDCIDSystemInfo)
    assert out.get_cos_object() is info.get_cos_object()
    assert out.get_registry() == "Adobe"
    assert out.get_ordering() == "Japan1"
    assert out.get_supplement() == 6


def test_cid_font_get_cid_system_info_none_when_absent() -> None:
    assert PDCIDFontType0().get_cid_system_info() is None


def test_cid_font_set_cid_system_info_none_removes_entry() -> None:
    font = PDCIDFontType0()
    info = PDCIDSystemInfo()
    info.set_registry("Adobe")
    font.set_cid_system_info(info)
    assert font.get_cid_system_info() is not None
    font.set_cid_system_info(None)
    assert font.get_cid_system_info() is None


# ---------- /CIDToGIDMap (stream OR /Identity name) ----------


def test_cid_to_gid_map_identity_name_round_trip() -> None:
    font = PDCIDFontType2()
    font.set_cid_to_gid_map("Identity")
    assert font.get_cid_to_gid_map() == "Identity"


def test_cid_to_gid_map_stream_round_trip() -> None:
    font = PDCIDFontType2()
    stream = COSStream()
    font.set_cid_to_gid_map(stream)
    out = font.get_cid_to_gid_map()
    assert out is stream


def test_cid_to_gid_map_none_when_absent() -> None:
    assert PDCIDFontType0().get_cid_to_gid_map() is None


def test_cid_to_gid_map_set_none_removes_entry() -> None:
    font = PDCIDFontType2()
    font.set_cid_to_gid_map("Identity")
    assert font.get_cid_to_gid_map() == "Identity"
    font.set_cid_to_gid_map(None)
    assert font.get_cid_to_gid_map() is None


def test_cid_font_type2_identity_cid_to_gid_map_uses_cid_as_gid() -> None:
    font = PDCIDFontType2()
    font.set_cid_to_gid_map("Identity")
    assert font.has_cid_to_gid_map() is False
    assert font.cid_to_gid(0) == 0
    assert font.cid_to_gid(42) == 42
    assert font.code_to_gid(42) == 42
    assert font._code_to_gid(42) == 42


def test_cid_font_type2_absent_cid_to_gid_map_defaults_to_identity() -> None:
    font = PDCIDFontType2()
    assert font.has_cid_to_gid_map() is False
    assert font.cid_to_gid(7) == 7


def test_cid_font_type2_stream_cid_to_gid_map_reads_big_endian_words() -> None:
    font = PDCIDFontType2()
    stream = COSStream()
    stream.set_data(
        b"\x00\x00"  # CID 0 -> GID 0
        b"\x00\x2a"  # CID 1 -> GID 42
        b"\x01\x00"  # CID 2 -> GID 256
    )
    font.set_cid_to_gid_map(stream)

    assert font.has_cid_to_gid_map() is True
    assert font.cid_to_gid(0) == 0
    assert font.cid_to_gid(1) == 42
    assert font.cid_to_gid(2) == 256
    assert font.cid_to_gid(3) == 0


def test_cid_font_type2_stream_cid_to_gid_map_ignores_trailing_odd_byte() -> None:
    font = PDCIDFontType2()
    stream = COSStream()
    stream.set_data(b"\x12\x34\xff")
    font.set_cid_to_gid_map(stream)

    assert font.cid_to_gid(0) == 0x1234
    assert font.cid_to_gid(1) == 0


def test_cid_font_type2_cid_to_gid_cache_can_be_cleared() -> None:
    font = PDCIDFontType2()
    stream = COSStream()
    stream.set_data(b"\x00\x01")
    font.set_cid_to_gid_map(stream)
    assert font.cid_to_gid(0) == 1

    stream.set_data(b"\x00\x02")
    assert font.cid_to_gid(0) == 1
    font.clear_cid_to_gid_map_cache()
    assert font.cid_to_gid(0) == 2


# ---------- parent Type0 wiring ----------


def test_cid_font_parent_passthrough() -> None:
    from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

    parent = PDType0Font()
    cid = PDCIDFontType2(parent_type0_font=parent)
    assert cid.get_parent() is parent


def test_cid_font_no_parent_default() -> None:
    assert PDCIDFontType0().get_parent() is None


def test_type0_descendant_type2_preserves_cid_to_gid_lookup() -> None:
    from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

    parent_dict = COSDictionary()
    descendant = COSDictionary()
    descendant.set_name(COSName.SUBTYPE, "CIDFontType2")  # type: ignore[attr-defined]
    stream = COSStream()
    stream.set_data(b"\x00\x00\x00\x0d")
    descendant.set_item(COSName.get_pdf_name("CIDToGIDMap"), stream)
    parent_dict.set_item(COSName.get_pdf_name("DescendantFonts"), COSArray([descendant]))

    parent = PDType0Font(parent_dict)
    cid = parent.get_descendant_font()
    assert isinstance(cid, PDCIDFontType2)
    assert cid.get_parent() is parent
    assert cid.cid_to_gid(1) == 13


# ---------- inheritance sanity ----------


def test_cid_font_inheritance_chain() -> None:
    from pypdfbox.pdmodel.font.pd_font import PDFont

    assert issubclass(PDCIDFont, PDFont)
    assert issubclass(PDCIDFontType0, PDCIDFont)
    assert issubclass(PDCIDFontType2, PDCIDFont)
