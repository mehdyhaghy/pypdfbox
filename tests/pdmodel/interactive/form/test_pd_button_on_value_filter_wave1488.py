"""Wave 1488: PDButton / PDCheckBox on-value discovery filters /AP /N states to
COSStream-valued entries only.

Upstream ``PDButton.getOnValueForWidget`` and ``PDCheckBox.getOnValue`` iterate
``normalAppearance.getSubDictionary().keySet()``, and
``PDAppearanceEntry.getSubDictionary`` surfaces only keys whose VALUE is a
``COSStream``. A ``/N`` state holding a non-stream placeholder (a plain
``COSDictionary`` or a ``COSName``) therefore contributes no on-value. Before
wave 1488 the pypdfbox helpers iterated the raw ``/N`` keys, accepting any
non-``/Off`` key regardless of value type.
"""
from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_button import PDButton
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox

_AP = COSName.get_pdf_name("AP")
_N = COSName.get_pdf_name("N")
_OFF = COSName.get_pdf_name("Off")
_KIDS = COSName.get_pdf_name("Kids")


def _ap(n: COSDictionary) -> COSDictionary:
    ap = COSDictionary()
    ap.set_item(_N, n)
    return ap


def _widget(n: COSDictionary) -> PDAnnotationWidget:
    widget = PDAnnotationWidget()
    widget.get_cos_object().set_item(_AP, _ap(n))
    return widget


# ---------- get_on_value_for_widget (PDButton static helper) ----------


def test_get_on_value_for_widget_returns_stream_state() -> None:
    n = COSDictionary()
    n.set_item(COSName.get_pdf_name("Yes"), COSStream())
    n.set_item(_OFF, COSStream())
    assert PDButton.get_on_value_for_widget(_widget(n)) == "Yes"


def test_get_on_value_for_widget_skips_dict_placeholder() -> None:
    n = COSDictionary()
    n.set_item(COSName.get_pdf_name("Yes"), COSDictionary())
    n.set_item(_OFF, COSStream())
    assert PDButton.get_on_value_for_widget(_widget(n)) == ""


def test_get_on_value_for_widget_skips_name_placeholder() -> None:
    n = COSDictionary()
    n.set_item(COSName.get_pdf_name("Yes"), COSName.get_pdf_name("ref"))
    n.set_item(_OFF, COSStream())
    assert PDButton.get_on_value_for_widget(_widget(n)) == ""


def test_get_on_value_for_widget_skips_non_stream_then_returns_stream() -> None:
    n = COSDictionary()
    n.set_item(COSName.get_pdf_name("Aaa"), COSDictionary())  # non-stream, first
    n.set_item(COSName.get_pdf_name("Bbb"), COSStream())  # stream
    n.set_item(_OFF, COSStream())
    assert PDButton.get_on_value_for_widget(_widget(n)) == "Bbb"


def test_get_on_value_for_widget_all_placeholders_is_empty() -> None:
    n = COSDictionary()
    n.set_item(COSName.get_pdf_name("Yes"), COSDictionary())
    n.set_item(_OFF, COSDictionary())
    assert PDButton.get_on_value_for_widget(_widget(n)) == ""


# ---------- PDCheckBox.get_on_value ----------


def test_check_box_get_on_value_returns_stream_state() -> None:
    cb = PDCheckBox(PDAcroForm())
    n = COSDictionary()
    n.set_item(COSName.get_pdf_name("Yes"), COSStream())
    n.set_item(_OFF, COSStream())
    cb.get_cos_object().set_item(_AP, _ap(n))
    assert cb.get_on_value() == "Yes"


def test_check_box_get_on_value_skips_dict_placeholder() -> None:
    cb = PDCheckBox(PDAcroForm())
    n = COSDictionary()
    n.set_item(COSName.get_pdf_name("Yes"), COSDictionary())
    n.set_item(_OFF, COSStream())
    cb.get_cos_object().set_item(_AP, _ap(n))
    assert cb.get_on_value() == ""


def test_check_box_get_on_value_skips_name_placeholder() -> None:
    cb = PDCheckBox(PDAcroForm())
    n = COSDictionary()
    n.set_item(COSName.get_pdf_name("Yes"), COSName.get_pdf_name("ref"))
    n.set_item(_OFF, COSStream())
    cb.get_cos_object().set_item(_AP, _ap(n))
    assert cb.get_on_value() == ""


def test_check_box_get_on_value_mixed_returns_stream_state() -> None:
    cb = PDCheckBox(PDAcroForm())
    n = COSDictionary()
    n.set_item(COSName.get_pdf_name("Aaa"), COSDictionary())
    n.set_item(COSName.get_pdf_name("Bbb"), COSStream())
    n.set_item(_OFF, COSStream())
    cb.get_cos_object().set_item(_AP, _ap(n))
    assert cb.get_on_value() == "Bbb"


# ---------- get_on_values aggregation through the filter ----------


def test_get_on_values_skips_non_stream_widget_states() -> None:
    """A widget whose only non-/Off /N state is a non-stream placeholder
    contributes the empty on-value, exactly like an AP-less widget."""
    cb = PDCheckBox(PDAcroForm())
    n = COSDictionary()
    n.set_item(COSName.get_pdf_name("Yes"), COSDictionary())  # placeholder
    n.set_item(_OFF, COSStream())
    cb.get_cos_object().set_item(_AP, _ap(n))
    assert set(cb.get_on_values()) == {""}


def test_get_on_values_kids_mix_stream_and_placeholder() -> None:
    cb = PDCheckBox(PDAcroForm())
    kids = COSArray()

    stream_n = COSDictionary()
    stream_n.set_item(COSName.get_pdf_name("Accepted"), COSStream())
    stream_n.set_item(_OFF, COSStream())
    kids.add(_widget(stream_n).get_cos_object())

    placeholder_n = COSDictionary()
    placeholder_n.set_item(COSName.get_pdf_name("Rejected"), COSDictionary())
    placeholder_n.set_item(_OFF, COSStream())
    kids.add(_widget(placeholder_n).get_cos_object())

    cb.get_cos_object().set_item(_KIDS, kids)
    # The stream widget contributes "Accepted"; the placeholder widget
    # contributes "" (its on-state is filtered out).
    assert set(cb.get_on_values()) == {"Accepted", ""}


def test_check_value_rejects_placeholder_only_on_state() -> None:
    """check_value is strict: a name backed only by a non-stream placeholder
    is not a valid on-value (it never enters get_on_values)."""
    import pytest

    cb = PDCheckBox(PDAcroForm())
    n = COSDictionary()
    n.set_item(COSName.get_pdf_name("Yes"), COSDictionary())
    n.set_item(_OFF, COSStream())
    cb.get_cos_object().set_item(_AP, _ap(n))

    cb.check_value("")  # the computed on-value for a filtered widget
    cb.check_value("Off")
    with pytest.raises(ValueError, match="not a valid option"):
        cb.check_value("Yes")
