from __future__ import annotations

from pypdfbox.fontbox.font_format import FontFormat
from tests.fontbox.test_font_info import _StubFontInfo
from tests.fontbox.test_font_provider import _ListProvider, _StubInfo


def test_wave858_provider_stub_info_exposes_all_contract_methods() -> None:
    info = _StubInfo("ProviderFont")

    assert info.get_post_script_name() == "ProviderFont"
    assert info.get_format() is FontFormat.TTF
    assert info.get_cid_system_info() is None
    assert info.get_family_class() == -1
    assert info.get_weight_class() == -1
    assert info.get_code_page_range1() == 0
    assert info.get_code_page_range2() == 0
    assert info.get_mac_style() == -1
    assert info.get_panose() is None


def test_wave858_list_provider_debug_and_font_info_round_trip() -> None:
    infos = [_StubInfo("A"), _StubInfo("B")]
    provider = _ListProvider(infos, "debug text")

    assert provider.to_debug_string() == "debug text"
    assert provider.get_font_info() is infos


def test_wave858_font_info_stub_font_contract_and_panose_fields() -> None:
    panose = object()
    info = _StubFontInfo(
        post_script_name="StubPS",
        font_format=FontFormat.OTF,
        cid_system_info="ros",
        family_class=2,
        weight_class=7,
        code_page_range1=0x10,
        code_page_range2=0x20,
        mac_style=3,
        panose=panose,
    )

    assert info.get_post_script_name() == "StubPS"
    assert info.get_format() is FontFormat.OTF
    assert info.get_cid_system_info() == "ros"
    assert info.get_family_class() == 2
    assert info.get_weight_class() == 7
    assert info.get_code_page_range1() == 0x10
    assert info.get_code_page_range2() == 0x20
    assert info.get_mac_style() == 3
    assert info.get_panose() is panose

    font = info.get_font()
    assert font.get_name() == "StubFont"
    assert font.get_font_bbox() == (0, 0, 0, 0)
    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    assert font.get_path("A") == []
    assert font.get_width("A") == 0.0
    assert font.has_glyph("A") is False
