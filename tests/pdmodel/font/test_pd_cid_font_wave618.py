from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSString
from pypdfbox.pdmodel.font.pd_cid_font import PDCIDFont
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2


def _num(value: int | float):
    if isinstance(value, int):
        return COSInteger.get(value)
    return COSFloat(str(value))


def test_base_font_and_dw_presence_round_trip() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("BaseFont"), "AdobeSongStd-Light")
    font = PDCIDFont(raw)

    assert font.get_base_font() == "AdobeSongStd-Light"
    assert font.has_dw() is False
    assert font.get_dw() == 1000

    font.set_dw(500)
    assert font.has_dw() is True
    assert font.get_default_width() == 500.0

    font.set_dw(None)
    assert font.has_dw() is False
    assert font.get_default_width() == 1000.0


def test_malformed_w_array_is_lenient_and_cache_can_be_cleared() -> None:
    font = PDCIDFontType2()
    font.set_dw(777)
    font.set_w(
        COSArray(
            [
                COSString("bad"),
                COSInteger.get(2),
                COSArray([COSInteger.get(210), COSString("skip"), COSFloat("230.5")]),
                COSInteger.get(10),
                COSInteger.get(12),
                COSInteger.get(400),
                COSInteger.get(99),
            ]
        )
    )

    assert font.get_widths() == {
        2: 210.0,
        4: pytest.approx(230.5),
        10: 400.0,
        11: 400.0,
        12: 400.0,
    }
    assert font.get_glyph_width(3) == 777.0

    font.get_w().set(5, COSInteger.get(300))  # type: ignore[union-attr]
    assert font.get_glyph_width(10) == 400.0
    font.clear_widths_cache()
    assert font.get_glyph_width(10) == 300.0


def test_average_width_ignores_zero_and_negative_entries_then_falls_back_to_dw() -> None:
    font = PDCIDFontType2()
    font.set_dw(640)
    font.set_w(
        COSArray(
            [
                COSInteger.get(1),
                COSArray([COSInteger.get(0), COSInteger.get(-20), COSInteger.get(500)]),
            ]
        )
    )
    assert font.get_average_font_width() == 500.0

    font.set_w(COSArray([COSInteger.get(1), COSArray([COSInteger.get(0)])]))
    assert font.get_average_font_width() == 640.0


def test_w2_array_supports_array_form_range_form_and_malformed_entries() -> None:
    font = PDCIDFontType2()
    font.set_w2(
        COSArray(
            [
                COSString("bad"),
                COSInteger.get(5),
                COSArray(
                    [
                        _num(-900),
                        _num(250),
                        _num(880),
                        COSString("x"),
                        _num(1),
                        _num(2),
                        _num(-901),
                        _num(251),
                        _num(881),
                    ]
                ),
                COSInteger.get(20),
                COSInteger.get(22),
                _num(-1000),
                _num(300),
                _num(900),
                COSInteger.get(30),
                COSInteger.get(31),
                COSString("missing-triple"),
            ]
        )
    )

    assert font.get_widths2() == {
        5: (-900.0, 250.0, 880.0),
        7: (-901.0, 251.0, 881.0),
        20: (-1000.0, 300.0, 900.0),
        21: (-1000.0, 300.0, 900.0),
        22: (-1000.0, 300.0, 900.0),
    }
    assert font.get_position_vector(7) == (251.0, 881.0)
    assert font.get_height(20) == -1000.0


def test_large_w2_range_is_kept_compact_but_lookup_still_works() -> None:
    font = PDCIDFontType2()
    font.set_w2(
        COSArray(
            [
                COSInteger.get(1),
                COSInteger.get(5000),
                COSInteger.get(-900),
                COSInteger.get(250),
                COSInteger.get(880),
            ]
        )
    )

    assert font.get_widths2() == {}
    assert font.get_position_vector(4096) == (250.0, 880.0)
    assert font.get_vertical_displacement_vector_y(5000) == -900.0


def test_dw2_defaults_and_partial_malformed_values() -> None:
    font = PDCIDFontType2()

    assert font.get_default_position_vector() == (880.0, -1000.0)
    assert font.get_default_position_vector_for_cid(3) == (500.0, 880.0)
    assert font.get_vertical_displacement_vector_y(3) == -1000.0

    font.set_dw2(COSArray([COSString("bad"), COSInteger.get(-1200)]))
    assert font.get_default_position_vector() == (880.0, -1200.0)
    assert font.get_dw2_position_vector_y() == 880.0
    assert font.get_dw2_displacement_vector_y() == -1200.0


def test_has_glyph_and_explicit_width_distinguish_dw_fallback() -> None:
    font = PDCIDFontType2()
    font.set_dw(0)
    font.set_w(COSArray([COSInteger.get(4), COSArray([COSInteger.get(0), COSInteger.get(222)])]))

    assert font.has_explicit_width(4) is True
    assert font.has_glyph(4) is False
    assert font.has_explicit_width(5) is True
    assert font.has_glyph(5) is True
    assert font.has_explicit_width(6) is False
    assert font.has_glyph(6) is False


def test_cid_to_gid_map_identity_absent_stream_and_invalid_setter() -> None:
    font = PDCIDFontType2()
    assert font.get_cid_to_gid_map() is None
    assert font.read_cid_to_gid_map() is None
    assert font.is_identity_cid_to_gid_map() is True
    assert font.has_cid_to_gid_map_stream() is False

    font.set_cid_to_gid_map("Custom")
    assert font.get_cid_to_gid_map() == "Custom"
    assert font.is_identity_cid_to_gid_map() is False

    with pytest.raises(TypeError, match="COSStream, str, or None"):
        font.set_cid_to_gid_map(123)  # type: ignore[arg-type]
