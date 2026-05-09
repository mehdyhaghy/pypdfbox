from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.interactive.annotation import PDAnnotation, PDAnnotationText


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_wave588_equality_uses_backing_dictionary_identity() -> None:
    raw = COSDictionary()
    first = PDAnnotation(raw)
    second = PDAnnotation(raw)
    other = PDAnnotation(COSDictionary())

    assert first == second
    assert first != other


def test_wave588_border_default_is_synthetic_and_short_arrays_are_padded_copy() -> None:
    annotation = PDAnnotationText()

    default_border = annotation.get_border()

    assert [default_border.get(i).int_value() for i in range(3)] == [0, 0, 1]
    assert annotation.get_cos_object().get_dictionary_object(_name("Border")) is None

    short_border = COSArray([COSInteger.get(4)])
    annotation.set_border(short_border)
    padded = annotation.get_border()

    assert padded is not short_border
    assert short_border.size() == 1
    assert [padded.get(i).int_value() for i in range(3)] == [4, 0, 0]

    annotation.set_border(None)

    assert annotation.get_cos_object().get_dictionary_object(_name("Border")) is None


def test_wave588_set_color_accepts_duck_typed_color_and_clears() -> None:
    annotation = PDAnnotationText()
    color_array = COSArray([COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)])

    class ColorLike:
        def to_cos_array(self) -> COSArray:
            return color_array

    annotation.set_color(ColorLike())

    assert annotation.get_color() is color_array
    assert annotation.has_color() is True

    annotation.set_color(None)

    assert annotation.get_color() is None
    assert annotation.has_color() is False


def test_wave588_appearance_state_string_page_alias_and_noop_with_doc_arg() -> None:
    annotation = PDAnnotationText()
    page = COSDictionary()

    annotation.set_appearance_state("Pressed")
    annotation.set_page(page)

    assert annotation.get_appearance_state() == "Pressed"
    assert annotation.get_page() is page
    assert annotation.construct_appearances(document=None) is None

    annotation.set_page(None)

    assert annotation.get_page() is None
