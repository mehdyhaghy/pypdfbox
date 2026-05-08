from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_wave322_simple_font_metric_setters_round_trip_on_type1() -> None:
    font = PDType1Font()

    font.set_first_char(65)
    font.set_last_char(66)
    font.set_widths([500, 625.5])

    assert font.get_first_char() == 65
    assert font.get_last_char() == 66
    assert font.get_widths() == [500.0, 625.5]
    widths = font.get_cos_object().get_dictionary_object(_name("Widths"))
    assert isinstance(widths, COSArray)
    assert all(isinstance(widths.get(i), COSFloat) for i in range(widths.size()))


def test_wave322_simple_font_metric_setters_clear_entries_on_type1c() -> None:
    font = PDType1CFont()
    font.set_first_char(30)
    font.set_last_char(31)
    font.set_widths([250.0, 300.0])

    font.set_first_char(None)
    font.set_last_char(None)
    font.set_widths(None)

    raw = font.get_cos_object()
    assert font.get_first_char() == -1
    assert font.get_last_char() == -1
    assert font.get_widths() == []
    assert raw.get_dictionary_object(_name("FirstChar")) is None
    assert raw.get_dictionary_object(_name("LastChar")) is None
    assert raw.get_dictionary_object(_name("Widths")) is None
