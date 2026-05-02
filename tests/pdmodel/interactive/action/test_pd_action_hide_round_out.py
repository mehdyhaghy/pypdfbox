"""Wave 188 round-out tests for :class:`PDActionHide`.

Cover the typed ``/T`` accessors (string lists, annotation, annotations
list) and the ``/H`` predicate aliases that wave 188 layered on top of
the lite Hide-action surface."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSBoolean, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.action.pd_action_hide import PDActionHide
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_unknown import (
    PDAnnotationUnknown,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)


_H: COSName = COSName.get_pdf_name("H")
_S: COSName = COSName.get_pdf_name("S")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_T: COSName = COSName.T  # type: ignore[attr-defined]
_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]


# ---------- /T typed: field-name list ----------


def test_get_target_names_absent_returns_none() -> None:
    action = PDActionHide()
    assert action.get_target_names() is None


def test_get_target_names_single_string_returns_one_element_list() -> None:
    action = PDActionHide()
    action.set_target(COSString("Field.Sub"))
    assert action.get_target_names() == ["Field.Sub"]


def test_get_target_names_array_of_strings() -> None:
    action = PDActionHide()
    array = COSArray()
    array.add(COSString("F1"))
    array.add(COSString("F2"))
    array.add(COSString("F3"))
    action.set_target(array)
    assert action.get_target_names() == ["F1", "F2", "F3"]


def test_get_target_names_skips_dict_entries() -> None:
    """An array containing a mix of string and annotation dict entries
    must yield only the strings — the annotation entries belong to
    :meth:`get_annotations`."""
    action = PDActionHide()
    array = COSArray()
    array.add(COSString("F1"))
    annot = COSDictionary()
    annot.set_item(_TYPE, COSName.get_pdf_name("Annot"))
    annot.set_item(_SUBTYPE, COSName.get_pdf_name("Widget"))
    array.add(annot)
    array.add(COSString("F2"))
    action.set_target(array)
    assert action.get_target_names() == ["F1", "F2"]


def test_get_target_names_dict_entry_returns_empty_list() -> None:
    """``/T`` carrying a single annotation dict yields an empty
    name list (the dict view lives on :meth:`get_annotation`)."""
    action = PDActionHide()
    annot = COSDictionary()
    annot.set_item(_SUBTYPE, COSName.get_pdf_name("Widget"))
    action.set_target(annot)
    assert action.get_target_names() == []


def test_set_target_names_none_removes_entry() -> None:
    action = PDActionHide()
    action.set_target_names(["F1"])
    assert action.get_target() is not None

    action.set_target_names(None)
    assert action.get_target() is None


def test_set_target_names_single_collapses_to_string() -> None:
    """Single-element lists store as a bare COSString — the simple form
    upstream emits when only one annotation is targeted."""
    action = PDActionHide()
    action.set_target_names(["OnlyOne"])
    raw = action.get_target()
    assert isinstance(raw, COSString)
    assert raw.get_string() == "OnlyOne"


def test_set_target_names_multiple_emits_cosarray() -> None:
    action = PDActionHide()
    action.set_target_names(["A", "B", "C"])
    raw = action.get_target()
    assert isinstance(raw, COSArray)
    assert raw.size() == 3
    assert action.get_target_names() == ["A", "B", "C"]


def test_set_target_names_round_trip_preserves_unicode() -> None:
    """COSString round-trips Unicode field names."""
    action = PDActionHide()
    action.set_target_names(["Heading.über"])
    assert action.get_target_names() == ["Heading.über"]


# ---------- /T typed: single annotation ----------


def test_get_annotation_absent_returns_none() -> None:
    action = PDActionHide()
    assert action.get_annotation() is None


def test_get_annotation_string_returns_none() -> None:
    """``/T`` being a field-name string is *not* an annotation entry —
    :meth:`get_annotation` returns ``None`` and callers should fall
    through to :meth:`get_target_names`."""
    action = PDActionHide()
    action.set_target(COSString("Field"))
    assert action.get_annotation() is None


def test_get_annotation_dispatches_to_typed_subclass() -> None:
    action = PDActionHide()
    annot = COSDictionary()
    annot.set_item(_TYPE, COSName.get_pdf_name("Annot"))
    annot.set_item(_SUBTYPE, COSName.get_pdf_name("Widget"))
    action.set_target(annot)

    resolved = action.get_annotation()
    assert isinstance(resolved, PDAnnotationWidget)
    assert resolved.get_cos_object() is annot


def test_get_annotation_unknown_subtype_returns_unknown_wrapper() -> None:
    action = PDActionHide()
    annot = COSDictionary()
    annot.set_item(_SUBTYPE, COSName.get_pdf_name("CustomSubtype"))
    action.set_target(annot)

    resolved = action.get_annotation()
    assert isinstance(resolved, PDAnnotationUnknown)


def test_set_annotation_pd_annotation_stores_cos_dict() -> None:
    """``set_annotation`` accepts a ``PDAnnotation`` and stores its
    underlying ``COSDictionary`` (not the wrapper)."""
    action = PDActionHide()
    widget = PDAnnotationWidget()
    action.set_annotation(widget)

    assert action.get_target() is widget.get_cos_object()
    assert isinstance(action.get_annotation(), PDAnnotationWidget)


def test_set_annotation_raw_dict_stored_as_is() -> None:
    action = PDActionHide()
    annot = COSDictionary()
    action.set_annotation(annot)
    assert action.get_target() is annot


def test_set_annotation_none_removes_entry() -> None:
    action = PDActionHide()
    action.set_annotation(PDAnnotationLink())
    assert action.get_target() is not None

    action.set_annotation(None)
    assert action.get_target() is None


# ---------- /T typed: annotations list ----------


def test_get_annotations_absent_returns_none() -> None:
    action = PDActionHide()
    assert action.get_annotations() is None


def test_get_annotations_single_dict_returns_one_element_list() -> None:
    """Single-dict ``/T`` returns a one-element list — the spec treats
    an annotation dictionary and a one-element array of annotations
    interchangeably."""
    action = PDActionHide()
    annot = COSDictionary()
    annot.set_item(_SUBTYPE, COSName.get_pdf_name("Widget"))
    action.set_target(annot)

    annotations = action.get_annotations()
    assert annotations is not None
    assert len(annotations) == 1
    assert isinstance(annotations[0], PDAnnotationWidget)


def test_get_annotations_array_collects_dicts_only() -> None:
    """A mixed array yields only the dict entries; string entries are
    skipped (their typed view is :meth:`get_target_names`)."""
    action = PDActionHide()
    array = COSArray()
    widget = COSDictionary()
    widget.set_item(_SUBTYPE, COSName.get_pdf_name("Widget"))
    link = COSDictionary()
    link.set_item(_SUBTYPE, COSName.get_pdf_name("Link"))
    array.add(widget)
    array.add(COSString("FieldName"))
    array.add(link)
    action.set_target(array)

    annotations = action.get_annotations()
    assert annotations is not None
    assert len(annotations) == 2
    assert isinstance(annotations[0], PDAnnotationWidget)
    assert isinstance(annotations[1], PDAnnotationLink)


def test_get_annotations_strings_only_returns_empty_list() -> None:
    action = PDActionHide()
    array = COSArray()
    array.add(COSString("F1"))
    array.add(COSString("F2"))
    action.set_target(array)
    assert action.get_annotations() == []


def test_set_annotations_none_removes_entry() -> None:
    action = PDActionHide()
    action.set_annotations([PDAnnotationWidget()])
    assert action.get_target() is not None

    action.set_annotations(None)
    assert action.get_target() is None


def test_set_annotations_single_collapses_to_dict() -> None:
    """A single-element list stores as the bare annotation dictionary
    (simple form), not as a one-element array."""
    action = PDActionHide()
    widget = PDAnnotationWidget()
    action.set_annotations([widget])

    raw = action.get_target()
    assert isinstance(raw, COSDictionary)
    assert raw is widget.get_cos_object()


def test_set_annotations_multiple_emits_cosarray_of_dicts() -> None:
    action = PDActionHide()
    a1 = PDAnnotationWidget()
    a2 = PDAnnotationLink()
    action.set_annotations([a1, a2])

    raw = action.get_target()
    assert isinstance(raw, COSArray)
    assert raw.size() == 2
    assert raw.get_object(0) is a1.get_cos_object()
    assert raw.get_object(1) is a2.get_cos_object()


def test_set_annotations_accepts_raw_cos_dictionary() -> None:
    """``set_annotations`` accepts ``COSDictionary`` entries directly so
    callers can mix typed wrappers and raw dicts."""
    action = PDActionHide()
    widget = PDAnnotationWidget()
    raw_dict = COSDictionary()
    raw_dict.set_item(_SUBTYPE, COSName.get_pdf_name("Link"))
    action.set_annotations([widget, raw_dict])

    raw = action.get_target()
    assert isinstance(raw, COSArray)
    assert raw.size() == 2
    assert raw.get_object(0) is widget.get_cos_object()
    assert raw.get_object(1) is raw_dict


# ---------- /H predicate aliases ----------


def test_is_hide_default_true() -> None:
    """``/H`` defaults to ``True`` per Table 200."""
    action = PDActionHide()
    assert action.is_hide() is True


def test_should_hide_default_true() -> None:
    action = PDActionHide()
    assert action.should_hide() is True


def test_is_hide_round_trip_via_set_h() -> None:
    action = PDActionHide()
    action.set_h(False)
    assert action.is_hide() is False
    assert action.should_hide() is False
    action.set_h(True)
    assert action.is_hide() is True
    assert action.should_hide() is True


def test_set_hide_alias_round_trip() -> None:
    action = PDActionHide()
    action.set_hide(False)
    assert action.get_h() is False
    assert action.is_hide() is False
    action.set_hide(True)
    assert action.get_h() is True


def test_h_default_when_explicit_false_stored_via_cos() -> None:
    """An explicit ``/H false`` round-trips via the predicate aliases —
    the default-True only kicks in when the entry is *absent*, not when
    it's present-but-false."""
    action = PDActionHide()
    action.get_cos_object().set_item(_H, COSBoolean.FALSE)
    assert action.is_hide() is False
    assert action.should_hide() is False
    assert action.get_h() is False


# ---------- Sub-type and PDAction.create dispatch ----------


def test_sub_type_constant_round_trip() -> None:
    action = PDActionHide()
    assert PDActionHide.SUB_TYPE == "Hide"
    assert action.get_cos_object().get_name(_S) == "Hide"


def test_pd_action_create_dispatches_to_hide() -> None:
    """A pre-existing ``/S /Hide`` dictionary parses back through
    :meth:`PDAction.create` as a :class:`PDActionHide`."""
    from pypdfbox.pdmodel.interactive.action.pd_action import PDAction

    action = PDActionHide()
    action.set_target_names(["Field1", "Field2"])
    action.set_h(False)

    parsed = PDAction.create(action.get_cos_object())
    assert isinstance(parsed, PDActionHide)
    assert parsed.get_target_names() == ["Field1", "Field2"]
    assert parsed.is_hide() is False
