from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotation,
    PDAnnotationWatermark,
)

_FIXED_PRINT = COSName.get_pdf_name("FixedPrint")


class _COSDictionaryBacked:
    def __init__(self, cos: COSDictionary) -> None:
        self._cos = cos

    def get_cos_object(self) -> COSDictionary:
        return self._cos


class _NonDictionaryBacked:
    def get_cos_object(self) -> COSArray:
        return COSArray()


def test_subtype_constant_and_default_constructor() -> None:
    ann = PDAnnotationWatermark()

    assert PDAnnotationWatermark.SUB_TYPE == "Watermark"
    assert ann.get_subtype() == "Watermark"
    assert ann.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]


def test_constructor_preserves_existing_cos_dictionary() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Watermark")  # type: ignore[attr-defined]
    fixed_print = COSDictionary()
    raw.set_item(_FIXED_PRINT, fixed_print)

    ann = PDAnnotationWatermark(raw)

    assert ann.get_cos_object() is raw
    assert ann.get_subtype() == "Watermark"
    assert ann.get_fixed_print() is fixed_print


def test_factory_dispatches_watermark_and_preserves_fixed_print() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Watermark")  # type: ignore[attr-defined]
    fixed_print = COSDictionary()
    fixed_print.set_int("H", 0)
    raw.set_item(_FIXED_PRINT, fixed_print)

    ann = PDAnnotation.create(raw)

    assert isinstance(ann, PDAnnotationWatermark)
    assert ann.get_cos_object() is raw
    assert ann.get_fixed_print() is fixed_print


def test_fixed_print_default_is_none() -> None:
    ann = PDAnnotationWatermark()

    assert ann.get_fixed_print() is None
    assert ann.get_cos_object().get_dictionary_object(_FIXED_PRINT) is None


def test_fixed_print_raw_dictionary_round_trip() -> None:
    ann = PDAnnotationWatermark()
    fixed_print = COSDictionary()
    fixed_print.set_float("Matrix", 1.0)

    ann.set_fixed_print(fixed_print)

    assert ann.get_fixed_print() is fixed_print
    assert ann.get_cos_object().get_dictionary_object(_FIXED_PRINT) is fixed_print


def test_fixed_print_accepts_cos_dictionary_backed_wrapper() -> None:
    ann = PDAnnotationWatermark()
    fixed_print = COSDictionary()

    ann.set_fixed_print(_COSDictionaryBacked(fixed_print))  # type: ignore[arg-type]

    assert ann.get_fixed_print() is fixed_print


def test_fixed_print_clear_removes_entry() -> None:
    ann = PDAnnotationWatermark()
    ann.set_fixed_print(COSDictionary())

    ann.set_fixed_print(None)

    assert ann.get_fixed_print() is None
    assert ann.get_cos_object().get_dictionary_object(_FIXED_PRINT) is None


def test_fixed_print_replacement_does_not_mutate_old_dictionary() -> None:
    ann = PDAnnotationWatermark()
    old = COSDictionary()
    new = COSDictionary()
    old.set_int("H", 1)

    ann.set_fixed_print(old)
    ann.set_fixed_print(new)

    assert ann.get_fixed_print() is new
    assert old.get_int("H") == 1


def test_fixed_print_malformed_shape_reads_as_none_but_preserves_cos() -> None:
    ann = PDAnnotationWatermark()
    malformed = COSArray([COSInteger.get(1)])
    ann.get_cos_object().set_item(_FIXED_PRINT, malformed)

    assert ann.get_fixed_print() is None
    assert ann.get_cos_object().get_dictionary_object(_FIXED_PRINT) is malformed


@pytest.mark.parametrize("value", [COSArray(), COSName.get_pdf_name("Bad")])
def test_set_fixed_print_rejects_non_dictionary_values(value: object) -> None:
    ann = PDAnnotationWatermark()

    with pytest.raises(TypeError, match="set_fixed_print expects"):
        ann.set_fixed_print(value)  # type: ignore[arg-type]


def test_set_fixed_print_rejects_non_dictionary_backed_wrapper() -> None:
    ann = PDAnnotationWatermark()

    with pytest.raises(TypeError, match="COSDictionary-backed wrapper"):
        ann.set_fixed_print(_NonDictionaryBacked())  # type: ignore[arg-type]
