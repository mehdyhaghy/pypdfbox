from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_caret import (
    PDAnnotationCaret,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
    PDAnnotationMarkup,
)


def test_caret_subtype_constant() -> None:
    assert PDAnnotationCaret.SUB_TYPE == "Caret"


def test_caret_inherits_markup() -> None:
    assert issubclass(PDAnnotationCaret, PDAnnotationMarkup)


def test_caret_default_constructor_sets_type_and_subtype() -> None:
    ann = PDAnnotationCaret()
    cos = ann.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]
    assert ann.get_subtype() == "Caret"


def test_caret_constructor_with_dict_preserves_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Caret")  # type: ignore[attr-defined]
    ann = PDAnnotationCaret(d)
    assert ann.get_subtype() == "Caret"
    assert ann.get_cos_object() is d


def test_caret_inherits_markup_subject() -> None:
    ann = PDAnnotationCaret()
    ann.set_subject("Insert here")
    assert ann.get_subject() == "Insert here"


def test_caret_rectangle_difference_aliases_round_trip_and_clear() -> None:
    ann = PDAnnotationCaret()

    ann.set_rect_differences([1, 2.5, 3, 4])

    assert ann.get_rectangle_differences() == [1.0, 2.5, 3.0, 4.0]
    assert ann.get_rect_differences() == [1.0, 2.5, 3.0, 4.0]

    ann.set_rect_differences(None)
    assert ann.get_rectangle_differences() is None


def test_caret_rectangle_difference_alias_rejects_wrong_length() -> None:
    ann = PDAnnotationCaret()

    with pytest.raises(ValueError):
        ann.set_rect_differences([1, 2, 3])


def test_caret_factory_dispatch() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Caret")  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    assert isinstance(ann, PDAnnotationCaret)
    assert ann.get_subtype() == "Caret"


def test_caret_set_rect_differences_uniform() -> None:
    ann = PDAnnotationCaret()
    ann.set_rect_differences_uniform(2.5)
    assert ann.get_rect_differences() == [2.5, 2.5, 2.5, 2.5]


def test_caret_set_rect_differences_lrtb() -> None:
    ann = PDAnnotationCaret()
    ann.set_rect_differences_lrtb(1.0, 2.0, 3.0, 4.0)
    assert ann.get_rect_differences() == [1.0, 2.0, 3.0, 4.0]


def test_caret_set_rect_differences_uniform_overrides_existing() -> None:
    ann = PDAnnotationCaret()
    ann.set_rect_differences_lrtb(9.0, 9.0, 9.0, 9.0)
    ann.set_rect_differences_uniform(0.0)
    assert ann.get_rect_differences() == [0.0, 0.0, 0.0, 0.0]


# ---------- /Sy (caret symbol) ----------


def test_caret_sy_constants_match_spec() -> None:
    assert PDAnnotationCaret.SY_PARAGRAPH == "P"
    assert PDAnnotationCaret.SY_NONE == "None"


def test_caret_get_symbol_default_is_spec_none() -> None:
    ann = PDAnnotationCaret()
    assert ann.get_symbol() == PDAnnotationCaret.SY_NONE


def test_caret_set_symbol_round_trip() -> None:
    ann = PDAnnotationCaret()
    ann.set_symbol(PDAnnotationCaret.SY_PARAGRAPH)
    assert ann.get_symbol() == "P"
    ann.set_symbol(PDAnnotationCaret.SY_NONE)
    assert ann.get_symbol() == "None"


def test_caret_set_symbol_none_clears_entry() -> None:
    ann = PDAnnotationCaret()
    ann.set_symbol("P")
    ann.set_symbol(None)
    # Cleared entry returns to the spec default.
    assert ann.get_symbol() == PDAnnotationCaret.SY_NONE
    # And the underlying COSDictionary really does not have /Sy.
    assert ann.get_cos_object().get_name(COSName.get_pdf_name("Sy")) is None


# ---------- predicate helpers ----------


def test_caret_has_rectangle_differences_default_false() -> None:
    ann = PDAnnotationCaret()
    assert ann.has_rectangle_differences() is False


def test_caret_has_rectangle_differences_true_after_set() -> None:
    ann = PDAnnotationCaret()
    ann.set_rect_differences_uniform(1.0)
    assert ann.has_rectangle_differences() is True


def test_caret_has_rectangle_differences_true_for_explicit_zero() -> None:
    """An all-zero ``/RD`` is still an explicit value (not "absent")."""
    ann = PDAnnotationCaret()
    ann.set_rect_differences_uniform(0.0)
    assert ann.has_rectangle_differences() is True


def test_caret_has_rectangle_differences_after_clear() -> None:
    ann = PDAnnotationCaret()
    ann.set_rect_differences_uniform(2.0)
    ann.set_rectangle_differences(None)
    assert ann.has_rectangle_differences() is False


def test_caret_has_symbol_default_false() -> None:
    """``has_symbol`` reflects presence of /Sy, not the spec default."""
    ann = PDAnnotationCaret()
    assert ann.has_symbol() is False
    # …yet get_symbol() reports the spec default.
    assert ann.get_symbol() == PDAnnotationCaret.SY_NONE


def test_caret_has_symbol_true_after_explicit_none() -> None:
    """Even an explicit ``/Sy /None`` is "set" — distinct from absent."""
    ann = PDAnnotationCaret()
    ann.set_symbol(PDAnnotationCaret.SY_NONE)
    assert ann.has_symbol() is True


def test_caret_has_symbol_after_clear() -> None:
    ann = PDAnnotationCaret()
    ann.set_symbol("P")
    ann.set_symbol(None)
    assert ann.has_symbol() is False


def test_caret_is_paragraph_symbol_true() -> None:
    ann = PDAnnotationCaret()
    ann.set_symbol(PDAnnotationCaret.SY_PARAGRAPH)
    assert ann.is_paragraph_symbol() is True
    assert ann.is_no_symbol() is False


def test_caret_is_paragraph_symbol_false_for_default() -> None:
    ann = PDAnnotationCaret()
    assert ann.is_paragraph_symbol() is False


def test_caret_is_no_symbol_default() -> None:
    """Absent /Sy → spec default of ``"None"`` → predicate is True."""
    ann = PDAnnotationCaret()
    assert ann.is_no_symbol() is True


def test_caret_is_no_symbol_when_explicitly_none() -> None:
    ann = PDAnnotationCaret()
    ann.set_symbol(PDAnnotationCaret.SY_NONE)
    assert ann.is_no_symbol() is True


def test_caret_is_no_symbol_false_for_paragraph() -> None:
    ann = PDAnnotationCaret()
    ann.set_symbol(PDAnnotationCaret.SY_PARAGRAPH)
    assert ann.is_no_symbol() is False


def test_caret_symbol_predicates_are_disjoint_for_known_values() -> None:
    """Paragraph and "no symbol" are mutually exclusive predicates for the
    two PDF-spec defined values."""
    for sy in (PDAnnotationCaret.SY_PARAGRAPH, PDAnnotationCaret.SY_NONE):
        ann = PDAnnotationCaret()
        ann.set_symbol(sy)
        assert ann.is_paragraph_symbol() ^ ann.is_no_symbol()


def test_caret_unknown_symbol_round_trip_preserves_value() -> None:
    """Setter does not validate against the spec list — unknown values
    survive a round-trip but are neither paragraph nor "no symbol"."""
    ann = PDAnnotationCaret()
    ann.set_symbol("X")
    assert ann.get_symbol() == "X"
    assert ann.has_symbol() is True
    assert ann.is_paragraph_symbol() is False
    assert ann.is_no_symbol() is False
