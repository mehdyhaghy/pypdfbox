"""Widths conversion memo (wave 1604 perf round).

Upstream ``PDFont.getWidths`` converts the ``/Widths`` array once and keeps
the resulting list. The port memoises the conversion keyed on the resolved
``COSArray``'s identity: repeated calls return the same list without
re-walking the array, and replacing the array (``set_widths`` or a raw
``set_item``) re-converts.
"""

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

_WIDTHS = COSName.get_pdf_name("Widths")


def test_get_widths_returns_memoised_list_on_repeat_calls() -> None:
    font = PDType1Font()
    font.set_widths([250.0, 333.0])

    first = font.get_widths()
    assert first == [250.0, 333.0]
    assert font.get_widths() is first


def test_set_widths_invalidates_memo() -> None:
    font = PDType1Font()
    font.set_widths([250.0])
    assert font.get_widths() == [250.0]

    font.set_widths([600.0, 610.5])
    assert font.get_widths() == [600.0, 610.5]

    font.set_widths(None)
    assert font.get_widths() == []


def test_raw_set_item_replacement_invalidates_memo() -> None:
    font = PDType1Font()
    font.set_widths([500.0])
    assert font.get_widths() == [500.0]

    replacement = COSArray([COSInteger.get(120), COSFloat(340.5)])
    font.get_cos_object().set_item(_WIDTHS, replacement)
    assert font.get_widths() == [120.0, 340.5]


def test_non_numeric_entries_still_map_to_none_through_memo() -> None:
    font = PDType1Font()
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("bogus"), COSFloat(500.5)])
    font.get_cos_object().set_item(_WIDTHS, arr)

    assert font.get_widths() == [0.0, None, 500.5]
    assert font.get_widths() == [0.0, None, 500.5]
