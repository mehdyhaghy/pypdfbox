from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSString
from pypdfbox.pdmodel.font.pd_cid_font import PDCIDFont
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor


def _ci(value: int) -> COSInteger:
    return COSInteger.get(value)


def test_set_dw2_none_removes_existing_default_vertical_metrics() -> None:
    font = PDCIDFontType2()
    font.set_dw2(COSArray([_ci(900), _ci(-800)]))

    font.set_dw2(None)

    assert font.get_dw2() is None
    assert font.get_default_position_vector() == (880.0, -1000.0)


def test_malformed_w_array_trailing_range_and_unknown_second_slots_are_ignored() -> None:
    font = PDCIDFontType2()
    font.set_dw(333)
    font.set_w(
        COSArray(
            [
                _ci(1),
                COSString("not-array-or-number"),
                _ci(5),
                _ci(7),
            ]
        )
    )

    assert font.get_widths() == {}
    assert font.get_width(5) == 333.0
    assert font.code_to_cid("5") == 5  # type: ignore[arg-type]


def test_w2_lookup_with_manual_empty_cache_and_no_ranges_returns_none() -> None:
    font = PDCIDFontType2()
    font._widths2 = {}  # noqa: SLF001
    font._w2_ranges = None  # noqa: SLF001

    assert font._get_w2_metrics(12) is None  # noqa: SLF001


def test_malformed_w2_array_trailing_and_unknown_entries_are_ignored() -> None:
    font = PDCIDFontType2()
    font.set_w2(
        COSArray(
            [
                _ci(9),
                _ci(10),
                COSString("bad-w1y"),
                _ci(250),
                _ci(880),
                _ci(20),
                COSString("not-array-or-number"),
                _ci(30),
            ]
        )
    )

    assert font.get_widths2() == {}
    assert font.get_height(9) == 0.0
    assert font.get_position_vector(20) == (500.0, 880.0)


def test_get_program_returns_none_when_descriptor_has_no_font_files() -> None:
    font = PDCIDFontType2()
    font.set_font_descriptor(PDFontDescriptor())

    assert font.is_embedded() is False
    assert font.get_program() is None


def test_base_cid_font_code_and_width_paths_use_identity_mapping() -> None:
    font = PDCIDFont()
    font.set_dw(640)
    font.set_w(COSArray([_ci(7), COSArray([_ci(500)])]))

    assert font.code_to_cid(7) == 7
    assert font.get_width(7) == 500.0
    assert font.get_width(8) == 640.0
