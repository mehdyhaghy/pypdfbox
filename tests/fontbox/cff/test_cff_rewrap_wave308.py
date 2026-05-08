from __future__ import annotations

from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font


class _Top:
    rawDict = {"FamilyName": "ParsedFamily"}  # noqa: N815, RUF012


def _base_font() -> CFFFont:
    base = CFFFont()
    base._top = _Top()  # noqa: SLF001
    base._data = b"\x01\x00\x04\x04cff"  # noqa: SLF001
    base._font_matrix = [0.002, 0.0, 0.0, 0.002, 0.0, 0.0]  # noqa: SLF001
    base._widths = {"A": 600.0}  # noqa: SLF001
    base.set_name("SyntheticName")
    base.add_value_to_top_dict("FamilyName", "OverlayFamily")
    base.add_value_to_top_dict("Weight", "Medium")
    return base


def _assert_rewrapped_base_state(wrapped: CFFFont, base: CFFFont) -> None:
    assert wrapped.get_data() == b"\x01\x00\x04\x04cff"
    assert wrapped.get_name() == "SyntheticName"
    assert wrapped.get_property("FamilyName") == "OverlayFamily"
    assert wrapped.get_property("Weight") == "Medium"
    assert wrapped.get_font_matrix() == [0.002, 0.0, 0.0, 0.002, 0.0, 0.0]

    base.add_value_to_top_dict("Weight", "Changed")
    base._font_matrix = [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]  # noqa: SLF001

    assert wrapped.get_property("Weight") == "Medium"
    assert wrapped.get_font_matrix() == [0.002, 0.0, 0.0, 0.002, 0.0, 0.0]


def test_type1_from_cff_font_preserves_base_state() -> None:
    base = _base_font()

    wrapped = CFFType1Font.from_cff_font(base)

    _assert_rewrapped_base_state(wrapped, base)


def test_cid_from_cff_font_preserves_base_state() -> None:
    base = _base_font()

    wrapped = CFFCIDFont.from_cff_font(base)

    _assert_rewrapped_base_state(wrapped, base)
    assert wrapped.is_cid_font() is True
