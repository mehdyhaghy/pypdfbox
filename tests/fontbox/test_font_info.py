"""Tests for :class:`FontInfo`.

Covers the abstract surface (subclass instantiation), the two concrete
helpers (``get_weight_class_as_panose``, ``get_code_page_range``) and
the ``__str__`` format.

Upstream Java has no checked-in unit tests for ``FontInfo`` — its
helpers are exercised via ``FontMapperImpl``. We pin them here directly
because they're stable contracts the mapper depends on.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.fontbox.font_box_font import FontBoxFont
from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.fontbox.font_info import FontInfo


class _StubFont:
    """Minimal :class:`FontBoxFont`-shaped stub for FontInfo tests."""

    def get_name(self) -> str:
        return "StubFont"

    def get_font_bbox(self) -> tuple[int, int, int, int]:
        return (0, 0, 0, 0)

    def get_font_matrix(self) -> list[float]:
        return [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]

    def get_path(self, name: str) -> list[Any]:
        del name
        return []

    def get_width(self, name: str) -> float:
        del name
        return 0.0

    def has_glyph(self, name: str) -> bool:
        del name
        return False


class _StubFontInfo(FontInfo):
    """All-args concrete FontInfo for direct test usage."""

    def __init__(
        self,
        post_script_name: str = "Helvetica",
        font_format: FontFormat = FontFormat.TTF,
        cid_system_info: Any | None = None,
        family_class: int = -1,
        weight_class: int = -1,
        code_page_range1: int = 0,
        code_page_range2: int = 0,
        mac_style: int = -1,
        panose: Any | None = None,
    ) -> None:
        self._psn = post_script_name
        self._format = font_format
        self._ros = cid_system_info
        self._family = family_class
        self._weight = weight_class
        self._cpr1 = code_page_range1
        self._cpr2 = code_page_range2
        self._mac = mac_style
        self._panose = panose

    def get_post_script_name(self) -> str:
        return self._psn

    def get_format(self) -> FontFormat:
        return self._format

    def get_cid_system_info(self) -> Any | None:
        return self._ros

    def get_font(self) -> FontBoxFont:
        return _StubFont()  # type: ignore[return-value]

    def get_family_class(self) -> int:
        return self._family

    def get_weight_class(self) -> int:
        return self._weight

    def get_code_page_range1(self) -> int:
        return self._cpr1

    def get_code_page_range2(self) -> int:
        return self._cpr2

    def get_mac_style(self) -> int:
        return self._mac

    def get_panose(self) -> Any | None:
        return self._panose


# ---------------------------------------------------------------------------
# Abstract surface
# ---------------------------------------------------------------------------


def test_font_info_is_abstract() -> None:
    with pytest.raises(TypeError):
        FontInfo()  # type: ignore[abstract]


def test_concrete_subclass_can_be_instantiated() -> None:
    info = _StubFontInfo()
    assert info.get_post_script_name() == "Helvetica"
    assert info.get_format() is FontFormat.TTF


# ---------------------------------------------------------------------------
# get_weight_class_as_panose — the OS/2 → Panose ladder
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "weight,expected",
    [
        (-1, 0),
        (0, 0),
        (100, 2),
        (200, 3),
        (300, 4),
        (400, 5),
        (500, 6),
        (600, 7),
        (700, 8),
        (800, 9),
        (900, 10),
    ],
)
def test_weight_class_as_panose_known_values(weight: int, expected: int) -> None:
    info = _StubFontInfo(weight_class=weight)
    assert info.get_weight_class_as_panose() == expected


@pytest.mark.parametrize("weight", [50, 150, 1000, 9999, -2])
def test_weight_class_as_panose_unknown_returns_zero(weight: int) -> None:
    """Anything outside the OS/2 ladder maps to Panose ``Any`` (0)."""
    info = _StubFontInfo(weight_class=weight)
    assert info.get_weight_class_as_panose() == 0


# ---------------------------------------------------------------------------
# get_code_page_range — packs range1/range2 into a single 64-bit int
# ---------------------------------------------------------------------------


def test_code_page_range_packs_low_then_high() -> None:
    info = _StubFontInfo(code_page_range1=0xAAAA, code_page_range2=0xBBBB)
    # range1 in the low 32 bits, range2 in the high 32 bits.
    assert info.get_code_page_range() == (0xBBBB << 32) | 0xAAAA


def test_code_page_range_unsigned_masking_protects_against_negatives() -> None:
    # Java treats range1/range2 as signed ``int`` and masks with
    # ``0x00000000ffffffffL`` to get the unsigned 32-bit value. We
    # mirror the mask so a negative-int implementation stays
    # well-defined.
    info = _StubFontInfo(code_page_range1=-1, code_page_range2=0)
    assert info.get_code_page_range() == 0xFFFFFFFF


def test_code_page_range_zero_when_both_zero() -> None:
    assert _StubFontInfo().get_code_page_range() == 0


# ---------------------------------------------------------------------------
# __str__ — matches upstream FontInfo.toString() shape
# ---------------------------------------------------------------------------


def test_str_format_matches_upstream_shape() -> None:
    info = _StubFontInfo(
        post_script_name="MyFont",
        font_format=FontFormat.OTF,
        family_class=0x12,
        mac_style=0x3,
        cid_system_info=None,
    )
    text = str(info)
    assert text == "MyFont (OTF, mac: 0x3, os/2: 0x12, cid: None)"


def test_str_uses_format_member_name() -> None:
    info = _StubFontInfo(font_format=FontFormat.PFB)
    assert "PFB" in str(info)


def test_str_includes_post_script_name() -> None:
    info = _StubFontInfo(post_script_name="UniqueName-Variant")
    assert "UniqueName-Variant" in str(info)
