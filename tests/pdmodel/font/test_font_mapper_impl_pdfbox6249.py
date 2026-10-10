"""PDFBOX-6249 forward-port (unreleased PDFBox 3.0.9): CID font selection.

Covers the ``FontMapperImpl`` side of the fix with fake :class:`FontInfo`
objects so the results are deterministic on any host:

* Adobe-Identity-0 CID-keyed fonts (Noto CJK, Source Han) match a legacy
  ROS through their OS/2 code page bits.
* A descriptor without weight information prefers a regular weight.
* Wrongly set code page bits on Noto Sans CJK fonts are masked.
* DroidSansFallback is skipped unless explicitly requested.
"""

from typing import Any

import pytest

from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.fontbox.font_info import FontInfo
from pypdfbox.fontbox.font_provider import FontProvider
from pypdfbox.pdmodel.font.cid_system_info import CIDSystemInfo
from pypdfbox.pdmodel.font.font_cache import FontCache
from pypdfbox.pdmodel.font.font_mapper_impl import FontMapperImpl
from pypdfbox.pdmodel.font.font_match import FontMatch
from pypdfbox.pdmodel.font.pd_cid_system_info import PDCIDSystemInfo
from pypdfbox.pdmodel.font.pd_font_descriptor import (
    PDFontDescriptor,
    PDPanoseClassification,
)

JIS_JAPAN = 1 << 17
CHINESE_SIMPLIFIED = 1 << 18
KOREAN_WANSUNG = 1 << 19
CHINESE_TRADITIONAL = 1 << 20
ALL_CJK = JIS_JAPAN | CHINESE_SIMPLIFIED | KOREAN_WANSUNG | CHINESE_TRADITIONAL

IDENTITY = CIDSystemInfo("Adobe", "Identity", 0)


class _Info(FontInfo):
    def __init__(
        self,
        name: str,
        *,
        weight: int = 0,
        ros: CIDSystemInfo | None = None,
        cp1: int = 0,
        panose: PDPanoseClassification | None = None,
        font_format: FontFormat = FontFormat.OTF,
    ) -> None:
        self._name = name
        self._weight = weight
        self._ros = ros
        self._cp1 = cp1
        self._panose = panose
        self._format = font_format
        self.font = object()

    def get_post_script_name(self) -> str:
        return self._name

    def get_format(self) -> FontFormat:
        return self._format

    def get_cid_system_info(self) -> CIDSystemInfo | None:
        return self._ros

    def get_font(self) -> Any:
        return self.font

    def get_family_class(self) -> int:
        return 0

    def get_weight_class(self) -> int:
        return self._weight

    def get_code_page_range1(self) -> int:
        return self._cp1

    def get_code_page_range2(self) -> int:
        return 0

    def get_mac_style(self) -> int:
        return 0

    def get_panose(self) -> PDPanoseClassification | None:
        return self._panose


class _Provider(FontProvider):
    def __init__(self, fonts: list[FontInfo]) -> None:
        self._fonts = fonts
        self._cache = FontCache()

    def to_debug_string(self) -> str:
        return ""

    def get_font_info(self) -> list[FontInfo]:
        return list(self._fonts)

    def get_cache(self) -> FontCache:
        return self._cache


def _mapper(*infos: FontInfo) -> FontMapperImpl:
    mapper = FontMapperImpl()
    mapper.set_provider(_Provider(list(infos)))
    return mapper


def _descriptor(
    *, weight: float = 0.0, name: str | None = None, family: str | None = None
) -> PDFontDescriptor:
    fd = PDFontDescriptor()
    if weight:
        fd.set_font_weight(weight)
    if name is not None:
        fd.set_font_name(name)
    if family is not None:
        fd.set_font_family(family)
    return fd


def _panose(family_kind: int, serif: int, weight: int) -> PDPanoseClassification:
    return PDPanoseClassification(bytes([family_kind, serif, weight] + [0] * 7))


# ---------- Identity-ordering substitutes ----------


def test_identity_font_substitutes_legacy_ros_and_prefers_regular() -> None:
    # The PDFBOX-6249 repro: a non-embedded Adobe-CNS1 font whose descriptor
    # has neither Panose nor /FontWeight. Only Adobe-Identity-0 CJK fonts are
    # installed; Bold must not win the tie.
    bold = _Info("NotoSansCJKtc-Bold", weight=700, ros=IDENTITY, cp1=ALL_CJK)
    regular = _Info("NotoSansCJKtc-Regular", weight=400, ros=IDENTITY, cp1=ALL_CJK)
    light = _Info("NotoSansCJKtc-Light", weight=300, ros=IDENTITY, cp1=ALL_CJK)
    mapper = _mapper(bold, light, regular)
    mapping = mapper.get_cid_font(
        "MingLiU", _descriptor(name="MingLiU"), PDCIDSystemInfo("Adobe", "CNS1", 0)
    )
    assert mapping is not None
    assert mapping.is_fallback()
    assert mapping.get_true_type_font() is regular.font


def test_identity_font_without_code_page_bit_is_rejected() -> None:
    simplified = _Info("SomeIdentitySC", weight=400, ros=IDENTITY, cp1=CHINESE_SIMPLIFIED)
    queue = _mapper(simplified).get_font_matches(
        _descriptor(), PDCIDSystemInfo("Adobe", "CNS1", 0)
    )
    assert queue == []


def test_other_legacy_ros_never_matches_even_with_code_page_bits() -> None:
    japan = _Info("KozMinPr6N", ros=CIDSystemInfo("Adobe", "Japan1", 6), cp1=ALL_CJK)
    assert not FontMapperImpl.is_char_set_match(
        PDCIDSystemInfo("Adobe", "GB1", 0), japan
    )


# ---------- weight scoring ----------


@pytest.mark.parametrize(
    ("weight_class", "expected"),
    [(400, 1.0), (300, 0.5), (500, 0.5), (700, -0.5), (0, 0.0)],
    ids=["regular", "light", "medium", "bold", "unknown"],
)
def test_weightless_descriptor_prefers_regular_weight(
    weight_class: int, expected: float
) -> None:
    info = _Info("Foo", weight=weight_class)
    match = FontMatch(info)
    FontMapperImpl._score_weight(match, _descriptor(), info)
    assert match.score == pytest.approx(expected)


def test_descriptor_weight_still_wins_over_regular_preference() -> None:
    info = _Info("Foo", weight=700)
    match = FontMatch(info)
    FontMapperImpl._score_weight(match, _descriptor(weight=700), info)
    assert match.score == pytest.approx(1.0)


def test_panose_branch_skips_regular_weight_preference() -> None:
    # Both sides carry Panose: the Panose branch scores and the
    # weightless-descriptor regular preference does not apply.
    fd = _descriptor()
    fd.set_panose(bytes([0, 0]) + bytes([2, 11, 5] + [0] * 7))
    info = _Info("SansRegular", weight=400, panose=_panose(2, 11, 5))
    queue = _mapper(info).get_font_matches(fd, None)
    assert len(queue) == 1
    # serif exact (+2) and weight exact (+2)
    assert queue[0].score == pytest.approx(4.0)


def test_panose_branch_family_kind_mismatch_scores_zero() -> None:
    fd = _descriptor()
    fd.set_panose(bytes([0, 0]) + bytes([3, 11, 5] + [0] * 7))
    info = _Info("SansRegular", weight=400, panose=_panose(2, 11, 5))
    queue = _mapper(info).get_font_matches(fd, None)
    assert queue[0].score == pytest.approx(0.0)


def test_panose_branch_skips_unrequested_barcode_font() -> None:
    fd = _descriptor(name="Helvetica")
    fd.set_panose(bytes([0, 0]) + bytes([0, 0, 0] + [0] * 7))
    barcode = _Info("Code128", weight=400, panose=_panose(0, 0, 0))
    assert _mapper(barcode).get_font_matches(fd, None) == []


# ---------- wrongly set Noto Sans CJK code page bits ----------


@pytest.mark.parametrize(
    ("name", "ordering", "expected"),
    [
        ("NotoSansTC-Regular", "Japan1", False),
        ("NotoSansHK-Regular", "Japan1", False),
        ("NotoSansCJKsc-Regular", "Japan1", False),
        ("NotoSansCJKtc-Regular", "Japan1", False),
        ("NotoSansCJKhk-Regular", "Japan1", False),
        ("NotoSansCJKkr-Regular", "Japan1", False),
        ("NotoSansKR-Regular", "Japan1", False),
        ("NotoSansJP-Regular", "GB1", False),
        ("NotoSansJP-Regular", "CNS1", False),
        ("NotoSansCJKjp-Regular", "CNS1", False),
        ("NotoSansKR-Regular", "GB1", False),
        ("NotoSansCJKkr-Regular", "CNS1", False),
        ("NotoSansJP-Regular", "Japan1", True),
        ("NotoSansCJKjp-Regular", "Japan1", True),
        ("NotoSansKR-Regular", "Korea1", True),
        ("NotoSansTC-Regular", "CNS1", True),
        ("NotoSansCJKsc-Regular", "GB1", True),
        ("NotoSansCJKhk-Regular", "CNS1", True),
        # other Noto Sans families keep their bits
        ("NotoSansSC-Regular", "Japan1", True),
        ("NotoSans-Regular", "Japan1", True),
    ],
)
def test_noto_sans_wrongly_set_bits_are_masked(
    name: str, ordering: str, expected: bool
) -> None:
    info = _Info(name, ros=IDENTITY, cp1=ALL_CJK)
    assert (
        FontMapperImpl.is_char_set_match(PDCIDSystemInfo("Adobe", ordering, 0), info)
        is expected
    )


# ---------- DroidSansFallback ----------


def test_droid_sans_fallback_skipped_unless_requested() -> None:
    droid = _Info("DroidSansFallback", weight=400, ros=None, cp1=ALL_CJK)
    other = _Info("OtherCJK", weight=700, ros=None, cp1=ALL_CJK)
    mapper = _mapper(droid, other)
    cns1 = PDCIDSystemInfo("Adobe", "CNS1", 0)
    fonts = {m.info.get_font() for m in mapper.get_font_matches(_descriptor(), cns1)}
    assert fonts == {other.font}

    by_family = mapper.get_font_matches(_descriptor(family="DroidSansFallback"), cns1)
    assert droid.font in {m.info.get_font() for m in by_family}
    by_name = mapper.get_font_matches(_descriptor(name="DroidSansFallback"), cns1)
    assert droid.font in {m.info.get_font() for m in by_name}
