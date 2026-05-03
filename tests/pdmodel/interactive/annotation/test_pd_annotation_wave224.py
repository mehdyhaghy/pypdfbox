"""Wave 224 — pdmodel/interactive/annotation small parity gaps.

Covers:
- ``PDAnnotationPopup.get_parent`` ``/Parent`` -> ``/P`` fallback +
  typed ``get_parent_markup``.
- ``PDAnnotationPopup.is_open`` predicate alias.
- ``PDAnnotationFileAttachment.is_push_pin/paperclip/graph/tag`` icon
  predicates.
- ``PDAnnotationText.is_open/is_note/is_comment`` predicates and
  ``STATE_*`` / ``STATE_MODEL_*`` constants.
- ``PDAnnotationInk.path_count``.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_file_attachment import (
    PDAnnotationFileAttachment,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_ink import (
    PDAnnotationInk,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
    PDAnnotationMarkup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_popup import (
    PDAnnotationPopup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text import (
    PDAnnotationText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_unknown import (
    PDAnnotationUnknown,
)

# ---------- PDAnnotationPopup ----------


def test_popup_is_open_predicate_default_false() -> None:
    assert PDAnnotationPopup().is_open() is False


def test_popup_is_open_round_trip() -> None:
    ann = PDAnnotationPopup()
    ann.set_open(True)
    assert ann.is_open() is True
    ann.set_open(False)
    assert ann.is_open() is False


def test_popup_get_parent_falls_back_to_p_when_parent_absent() -> None:
    ann = PDAnnotationPopup()
    parent_dict = COSDictionary()
    parent_dict.set_name(COSName.SUBTYPE, "Text")  # type: ignore[attr-defined]
    ann.get_cos_object().set_item(COSName.get_pdf_name("P"), parent_dict)

    assert ann.get_parent() is parent_dict


def test_popup_get_parent_prefers_parent_over_p() -> None:
    ann = PDAnnotationPopup()
    parent_dict = COSDictionary()
    parent_dict.set_name(COSName.SUBTYPE, "Text")  # type: ignore[attr-defined]
    p_dict = COSDictionary()
    p_dict.set_name(COSName.SUBTYPE, "FreeText")  # type: ignore[attr-defined]

    ann.set_parent(parent_dict)
    ann.get_cos_object().set_item(COSName.get_pdf_name("P"), p_dict)

    assert ann.get_parent() is parent_dict


def test_popup_get_parent_markup_returns_typed_markup() -> None:
    ann = PDAnnotationPopup()
    parent_dict = COSDictionary()
    parent_dict.set_name(COSName.SUBTYPE, "Text")  # type: ignore[attr-defined]
    ann.set_parent(parent_dict)

    parent = ann.get_parent_markup()
    assert isinstance(parent, PDAnnotationMarkup)
    assert parent.get_subtype() == "Text"


def test_popup_get_parent_markup_returns_none_when_absent() -> None:
    assert PDAnnotationPopup().get_parent_markup() is None


def test_popup_get_parent_markup_returns_none_for_non_markup_subtype() -> None:
    """Upstream returns null when the resolved parent is not
    ``PDAnnotationMarkup`` (e.g. a Link annotation, a Widget)."""
    ann = PDAnnotationPopup()
    parent_dict = COSDictionary()
    parent_dict.set_name(COSName.SUBTYPE, "Link")  # type: ignore[attr-defined]
    ann.set_parent(parent_dict)

    assert ann.get_parent_markup() is None


def test_popup_get_parent_markup_uses_p_fallback() -> None:
    ann = PDAnnotationPopup()
    parent_dict = COSDictionary()
    parent_dict.set_name(COSName.SUBTYPE, "FreeText")  # type: ignore[attr-defined]
    ann.get_cos_object().set_item(COSName.get_pdf_name("P"), parent_dict)

    parent = ann.get_parent_markup()
    assert isinstance(parent, PDAnnotationMarkup)
    assert parent.get_subtype() == "FreeText"


def test_popup_get_parent_markup_returns_none_for_unknown_subtype() -> None:
    """Unknown subtypes resolve to PDAnnotationUnknown (not markup)."""
    ann = PDAnnotationPopup()
    parent_dict = COSDictionary()
    parent_dict.set_name(COSName.SUBTYPE, "MysteryAnnotation")  # type: ignore[attr-defined]
    ann.set_parent(parent_dict)

    parent = ann.get_parent_markup()
    assert parent is None
    # Sanity: confirm the dispatch indeed lands in Unknown for this subtype.
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation

    assert isinstance(PDAnnotation.create(parent_dict), PDAnnotationUnknown)


# ---------- PDAnnotationFileAttachment ----------


def test_file_attachment_is_push_pin_default_true() -> None:
    """``/Name`` defaults to ``PushPin`` per spec — predicate must reflect that."""
    assert PDAnnotationFileAttachment().is_push_pin() is True


def test_file_attachment_icon_predicates_each_constant() -> None:
    ann = PDAnnotationFileAttachment()

    ann.set_attachment_name(PDAnnotationFileAttachment.ATTACHMENT_NAME_PAPERCLIP)
    assert ann.is_paperclip() is True
    assert ann.is_push_pin() is False
    assert ann.is_graph() is False
    assert ann.is_tag() is False

    ann.set_attachment_name(PDAnnotationFileAttachment.ATTACHMENT_NAME_GRAPH)
    assert ann.is_graph() is True
    assert ann.is_paperclip() is False

    ann.set_attachment_name(PDAnnotationFileAttachment.ATTACHMENT_NAME_TAG)
    assert ann.is_tag() is True
    assert ann.is_graph() is False


def test_file_attachment_icon_predicate_after_clear_returns_to_push_pin() -> None:
    ann = PDAnnotationFileAttachment()
    ann.set_attachment_name(PDAnnotationFileAttachment.ATTACHMENT_NAME_TAG)
    ann.set_attachment_name(None)
    assert ann.is_push_pin() is True
    assert ann.is_tag() is False


def test_file_attachment_icon_predicate_unknown_name_all_false() -> None:
    ann = PDAnnotationFileAttachment()
    ann.set_attachment_name("CustomIcon")
    assert ann.is_push_pin() is False
    assert ann.is_paperclip() is False
    assert ann.is_graph() is False
    assert ann.is_tag() is False


# ---------- PDAnnotationText ----------


def test_text_is_open_predicate() -> None:
    ann = PDAnnotationText()
    assert ann.is_open() is False
    ann.set_open(True)
    assert ann.is_open() is True


def test_text_is_note_default_true() -> None:
    """``/Name`` defaults to ``Note`` per spec."""
    assert PDAnnotationText().is_note() is True


def test_text_icon_predicates() -> None:
    ann = PDAnnotationText()
    ann.set_name(PDAnnotationText.NAME_COMMENT)
    assert ann.is_comment() is True
    assert ann.is_note() is False

    ann.set_name(PDAnnotationText.NAME_NOTE)
    assert ann.is_note() is True
    assert ann.is_comment() is False


def test_text_state_model_constants() -> None:
    assert PDAnnotationText.STATE_MODEL_MARKED == "Marked"
    assert PDAnnotationText.STATE_MODEL_REVIEW == "Review"


def test_text_state_value_constants() -> None:
    assert PDAnnotationText.STATE_MARKED == "Marked"
    assert PDAnnotationText.STATE_UNMARKED == "Unmarked"
    assert PDAnnotationText.STATE_ACCEPTED == "Accepted"
    assert PDAnnotationText.STATE_REJECTED == "Rejected"
    assert PDAnnotationText.STATE_CANCELLED == "Cancelled"
    assert PDAnnotationText.STATE_COMPLETED == "Completed"
    assert PDAnnotationText.STATE_NONE == "None"


def test_text_state_constants_round_trip_with_setters() -> None:
    """Sanity check that the state constants flow through the setters."""
    ann = PDAnnotationText()
    ann.set_state_model(PDAnnotationText.STATE_MODEL_REVIEW)
    ann.set_state(PDAnnotationText.STATE_ACCEPTED)
    assert ann.get_state_model() == "Review"
    assert ann.get_state() == "Accepted"

    ann.set_state_model(PDAnnotationText.STATE_MODEL_MARKED)
    ann.set_state(PDAnnotationText.STATE_UNMARKED)
    assert ann.get_state_model() == "Marked"
    assert ann.get_state() == "Unmarked"


# ---------- PDAnnotationInk ----------


def test_ink_path_count_default_zero() -> None:
    assert PDAnnotationInk().path_count() == 0


def test_ink_path_count_matches_set_paths() -> None:
    ann = PDAnnotationInk()
    ann.set_ink_paths(
        [
            [10.0, 20.0, 30.0, 40.0],
            [50.0, 60.0, 70.0, 80.0],
            [90.0, 100.0],
        ]
    )
    assert ann.path_count() == 3


def test_ink_path_count_cleared_returns_zero() -> None:
    ann = PDAnnotationInk()
    ann.set_ink_paths([[1.0, 2.0]])
    ann.set_ink_paths(None)
    assert ann.path_count() == 0


def test_ink_path_count_ignores_non_array_value() -> None:
    """If a stray ``/InkList`` value is not a COSArray (corrupt PDF),
    ``path_count`` returns 0 rather than raising."""
    ann = PDAnnotationInk()
    ann.get_cos_object().set_item(COSName.get_pdf_name("InkList"), COSFloat(0.0))
    assert ann.path_count() == 0


def test_ink_path_count_counts_nested_arrays_even_if_inner_invalid() -> None:
    """``path_count`` counts entries in the outer array — regardless of
    whether each inner entry is itself a valid COSArray (matches
    ``get_ink_paths`` which substitutes ``[]`` for non-array entries)."""
    ann = PDAnnotationInk()
    outer = COSArray()
    outer.add(COSArray([COSFloat(1.0), COSFloat(2.0)]))
    outer.add(COSFloat(42.0))  # bogus
    ann.get_cos_object().set_item(COSName.get_pdf_name("InkList"), outer)
    assert ann.path_count() == 2
