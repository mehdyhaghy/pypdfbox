"""Port of upstream ``CIDCharSetMatchTest`` (PDFBox 3.0 branch, PDFBOX-6249).

CIDSystemInfo-based candidate filtering for CID font substitution.
"""

from typing import Any

from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.fontbox.font_info import FontInfo
from pypdfbox.pdmodel.font.cid_system_info import CIDSystemInfo
from pypdfbox.pdmodel.font.font_mapper_impl import FontMapperImpl
from pypdfbox.pdmodel.font.pd_cid_system_info import PDCIDSystemInfo

CHINESE_TRADITIONAL = 1 << 20
CHINESE_SIMPLIFIED = 1 << 18


class _Info(FontInfo):
    def __init__(self, ros: CIDSystemInfo | None, code_page_range1: int) -> None:
        self._ros = ros
        self._cp1 = code_page_range1

    def get_post_script_name(self) -> str:
        return "TestFont"

    def get_format(self) -> FontFormat:
        return FontFormat.OTF

    def get_cid_system_info(self) -> CIDSystemInfo | None:
        return self._ros

    def get_font(self) -> Any:
        return None

    def get_family_class(self) -> int:
        return 0

    def get_weight_class(self) -> int:
        return 0

    def get_code_page_range1(self) -> int:
        return self._cp1

    def get_code_page_range2(self) -> int:
        return 0

    def get_mac_style(self) -> int:
        return 0

    def get_panose(self) -> Any:
        return None


def _info(ros: CIDSystemInfo | None, code_page_range1: int) -> FontInfo:
    return _Info(ros, code_page_range1)


def test_char_set_match() -> None:
    mapper = FontMapperImpl()
    cns1 = PDCIDSystemInfo("Adobe", "CNS1", 0)

    # exact ROS match
    assert mapper.is_char_set_match(cns1, _info(CIDSystemInfo("Adobe", "CNS1", 0), 0))

    # a different legacy ROS never matches
    assert not mapper.is_char_set_match(
        cns1, _info(CIDSystemInfo("Adobe", "Japan1", 0), CHINESE_TRADITIONAL)
    )

    # Adobe-Identity-0 (Noto CJK, Source Han) matches via its OS/2 code page bits
    assert mapper.is_char_set_match(
        cns1, _info(CIDSystemInfo("Adobe", "Identity", 0), CHINESE_TRADITIONAL)
    )
    assert not mapper.is_char_set_match(
        cns1, _info(CIDSystemInfo("Adobe", "Identity", 0), CHINESE_SIMPLIFIED)
    )

    # ROS-less TrueType fonts keep matching via code page bits
    assert mapper.is_char_set_match(cns1, _info(None, CHINESE_TRADITIONAL))
    assert not mapper.is_char_set_match(cns1, _info(None, 0))


# Upstream PDCIDFontType0SubstituteTest.testLatinViaCns1NonEmbedded is
# ported in tests/pdmodel/font/upstream/test_pd_cid_font_type0_substitute.py
# (with a fake FontMapper, so it does not need a host-installed CJK font).
# Its mapper half (regular weight preferred over Bold on a weightless
# descriptor) is covered deterministically in
# tests/pdmodel/font/test_font_mapper_impl_pdfbox6249.py.
