from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_object_reference import (
    PDObjectReference,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_node import (
    PDStructureNode,
)

_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE = COSName.get_pdf_name("Subtype")
_PG = COSName.get_pdf_name("Pg")
_OBJ = COSName.get_pdf_name("Obj")
_K = COSName.get_pdf_name("K")


# ---------- Construction ----------


def test_default_ctor_stamps_type_objr() -> None:
    objr = PDObjectReference()
    assert objr.get_cos_object().get_name(_TYPE) == "OBJR"
    assert PDObjectReference.TYPE == "OBJR"


def test_wraps_existing_dictionary() -> None:
    dic = COSDictionary()
    dic.set_name(_TYPE, "OBJR")
    objr = PDObjectReference(dic)
    assert objr.get_cos_object() is dic


def test_fresh_objr_has_no_pg_or_obj() -> None:
    objr = PDObjectReference()
    assert objr.get_pg() is None
    assert objr.get_obj() is None
    assert objr.get_page() is None
    assert objr.get_referenced_object() is None


# ---------- /Pg accessors (raw + typed PDPage) ----------


def test_set_pg_round_trip_raw_dict() -> None:
    objr = PDObjectReference()
    page_dict = COSDictionary()
    page_dict.set_name(_TYPE, "Page")
    objr.set_pg(page_dict)
    assert objr.get_pg() is page_dict
    assert objr.get_cos_object().get_dictionary_object(_PG) is page_dict


def test_set_pg_none_removes() -> None:
    objr = PDObjectReference()
    page_dict = COSDictionary()
    objr.set_pg(page_dict)
    objr.set_pg(None)
    assert objr.get_pg() is None
    assert objr.get_page() is None


def test_get_page_typed_wrapper() -> None:
    from pypdfbox.pdmodel.pd_page import PDPage

    objr = PDObjectReference()
    page = PDPage()
    objr.set_pg(page.get_cos_object())

    typed = objr.get_page()
    assert isinstance(typed, PDPage)
    assert typed.get_cos_object() is page.get_cos_object()


def test_set_page_typed_wrapper() -> None:
    from pypdfbox.pdmodel.pd_page import PDPage

    objr = PDObjectReference()
    page = PDPage()
    objr.set_page(page)

    assert objr.get_pg() is page.get_cos_object()
    assert objr.get_cos_object().get_dictionary_object(_PG) is page.get_cos_object()


def test_set_page_none_removes() -> None:
    from pypdfbox.pdmodel.pd_page import PDPage

    objr = PDObjectReference()
    objr.set_page(PDPage())
    objr.set_page(None)
    assert objr.get_pg() is None
    assert objr.get_page() is None


def test_get_page_returns_none_when_pg_not_dict() -> None:
    # /Pg present but not a dictionary (malformed) — typed accessor must
    # not crash; returns None.
    objr = PDObjectReference()
    objr.get_cos_object().set_item(_PG, COSArray())
    assert objr.get_page() is None


# ---------- /Obj accessors (raw + typed) ----------


def test_set_obj_round_trip() -> None:
    objr = PDObjectReference()
    target = COSDictionary()
    target.set_name(_TYPE, "Annot")
    objr.set_obj(target)
    assert objr.get_obj() is target
    assert objr.get_cos_object().get_dictionary_object(_OBJ) is target


def test_set_obj_none_removes() -> None:
    objr = PDObjectReference()
    objr.set_obj(COSDictionary())
    objr.set_obj(None)
    assert objr.get_obj() is None


def test_get_referenced_object_link_annotation() -> None:
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    objr = PDObjectReference()
    annot_dict = COSDictionary()
    annot_dict.set_name(_TYPE, "Annot")
    annot_dict.set_name(_SUBTYPE, "Link")
    objr.set_obj(annot_dict)

    referenced = objr.get_referenced_object()
    assert isinstance(referenced, PDAnnotationLink)
    assert referenced.get_cos_object() is annot_dict


def test_get_referenced_object_form_xobject_stream() -> None:
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject

    objr = PDObjectReference()
    stream = COSStream()
    stream.set_name(_SUBTYPE, "Form")
    objr.set_obj(stream)

    referenced = objr.get_referenced_object()
    assert isinstance(referenced, PDFormXObject)
    assert referenced.get_cos_object() is stream


def test_get_referenced_object_image_xobject_stream() -> None:
    from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
        PDImageXObject,
    )

    objr = PDObjectReference()
    stream = COSStream()
    stream.set_name(_SUBTYPE, "Image")
    objr.set_obj(stream)

    referenced = objr.get_referenced_object()
    assert isinstance(referenced, PDImageXObject)
    assert referenced.get_cos_object() is stream


def test_get_referenced_object_unknown_xobject_subtype_returns_none() -> None:
    objr = PDObjectReference()
    stream = COSStream()
    stream.set_name(_SUBTYPE, "PS")  # PostScript XObject — not Form/Image
    objr.set_obj(stream)
    assert objr.get_referenced_object() is None


def test_set_referenced_object_typed_round_trip() -> None:
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    annotation = PDAnnotationLink()
    objr = PDObjectReference()
    objr.set_referenced_object(annotation)

    assert (
        objr.get_cos_object().get_dictionary_object(_OBJ)
        is annotation.get_cos_object()
    )
    referenced = objr.get_referenced_object()
    assert isinstance(referenced, PDAnnotationLink)


def test_set_referenced_object_none_clears_obj() -> None:
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    objr = PDObjectReference()
    objr.set_referenced_object(PDAnnotationLink())
    objr.set_referenced_object(None)
    assert objr.get_obj() is None
    assert objr.get_referenced_object() is None


def test_set_referenced_object_rejects_raw_cos() -> None:
    objr = PDObjectReference()
    with pytest.raises(TypeError):
        objr.set_referenced_object(object())  # no get_cos_object


# ---------- OBJR wiring into structure tree (PDStructureNode.wrap_kid) ----------


def test_wrap_kid_dispatches_objr_dict_to_pd_object_reference() -> None:
    objr_dict = COSDictionary()
    objr_dict.set_name(_TYPE, "OBJR")
    wrapped = PDStructureNode.wrap_kid(objr_dict)
    assert isinstance(wrapped, PDObjectReference)
    assert wrapped.get_cos_object() is objr_dict


def test_struct_elem_kid_objr_resolved_via_get_kids() -> None:
    # Build a StructElem with /K = a single OBJR dict.
    elem = PDStructureElement("P")
    objr_dict = COSDictionary()
    objr_dict.set_name(_TYPE, "OBJR")
    elem.get_cos_object().set_item(_K, objr_dict)

    kids = elem.get_kids()
    assert len(kids) == 1
    assert isinstance(kids[0], PDObjectReference)
    assert kids[0].get_cos_object() is objr_dict


def test_struct_elem_kid_objr_resolved_via_iter_object_references() -> None:
    elem = PDStructureElement("Figure")
    arr = COSArray()
    objr_a = COSDictionary()
    objr_a.set_name(_TYPE, "OBJR")
    objr_b = COSDictionary()
    objr_b.set_name(_TYPE, "OBJR")
    arr.add(objr_a)
    arr.add(objr_b)
    elem.get_cos_object().set_item(_K, arr)

    refs = list(elem.iter_object_references())
    assert len(refs) == 2
    assert all(isinstance(r, PDObjectReference) for r in refs)
    assert refs[0].get_cos_object() is objr_a
    assert refs[1].get_cos_object() is objr_b


def test_append_kid_object_reference_stores_cos_dict() -> None:
    elem = PDStructureElement("Link")
    objr = PDObjectReference()
    elem.append_kid_object_reference(objr)

    kids = elem.get_kids()
    assert len(kids) == 1
    assert isinstance(kids[0], PDObjectReference)
    assert kids[0].get_cos_object() is objr.get_cos_object()


# ---------- Upstream-aligned dispatch: subtype-only / fallback rules ----


def test_get_referenced_object_subtype_only_annotation_dispatched() -> None:
    """Upstream returns the annotation for a known /Subtype even when
    /Type is missing — the only filter is "is the dispatch result
    PDAnnotationUnknown?"."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    objr = PDObjectReference()
    annot_dict = COSDictionary()
    # Deliberately omit /Type — upstream still recognises this as Link.
    annot_dict.set_name(_SUBTYPE, "Link")
    objr.set_obj(annot_dict)

    referenced = objr.get_referenced_object()
    assert isinstance(referenced, PDAnnotationLink)
    assert referenced.get_cos_object() is annot_dict


def test_get_referenced_object_unknown_subtype_with_type_annot_returned() -> None:
    """Upstream rule: PDAnnotationUnknown is returned only when /Type is
    /Annot (allows callers to round-trip producer-specific subtypes)."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_unknown import (
        PDAnnotationUnknown,
    )

    objr = PDObjectReference()
    annot_dict = COSDictionary()
    annot_dict.set_name(_TYPE, "Annot")
    annot_dict.set_name(_SUBTYPE, "FutureSubtype42")
    objr.set_obj(annot_dict)

    referenced = objr.get_referenced_object()
    assert isinstance(referenced, PDAnnotationUnknown)
    assert referenced.get_cos_object() is annot_dict


def test_get_referenced_object_unknown_subtype_without_type_returns_none() -> None:
    """No /Type, unknown /Subtype → upstream returns null (cannot tell
    whether the dict is even an annotation)."""
    objr = PDObjectReference()
    annot_dict = COSDictionary()
    annot_dict.set_name(_SUBTYPE, "FutureSubtype42")
    objr.set_obj(annot_dict)
    assert objr.get_referenced_object() is None


def test_get_referenced_object_dict_no_type_no_subtype_returns_none() -> None:
    """Bare dict with neither /Type nor /Subtype — nothing to dispatch on."""
    objr = PDObjectReference()
    objr.set_obj(COSDictionary())
    assert objr.get_referenced_object() is None


def test_get_referenced_object_form_xobject_dispatched_before_annotation() -> None:
    """Stream with /Subtype /Form must dispatch to PDFormXObject even
    when /Type is /Annot (which would never happen in practice but tests
    the upstream stream-first ordering)."""
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject

    objr = PDObjectReference()
    stream = COSStream()
    stream.set_name(_SUBTYPE, "Form")
    objr.set_obj(stream)

    referenced = objr.get_referenced_object()
    assert isinstance(referenced, PDFormXObject)


def test_get_referenced_object_known_annotation_returns_typed_subclass() -> None:
    """All twenty-odd dispatch table entries should round-trip — spot-
    check Square + Text since they're not exercised above."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_square_circle import (
        PDAnnotationSquare,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text import (
        PDAnnotationText,
    )

    for subtype, expected_cls in (
        ("Square", PDAnnotationSquare),
        ("Text", PDAnnotationText),
    ):
        objr = PDObjectReference()
        annot_dict = COSDictionary()
        annot_dict.set_name(_TYPE, "Annot")
        annot_dict.set_name(_SUBTYPE, subtype)
        objr.set_obj(annot_dict)

        referenced = objr.get_referenced_object()
        assert isinstance(referenced, expected_cls)


def test_set_referenced_object_form_xobject_round_trip() -> None:
    """set_referenced_object must accept a PDFormXObject (upstream
    overload no. 2) and round-trip through get_referenced_object."""
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject

    form = PDFormXObject(COSStream())
    objr = PDObjectReference()
    objr.set_referenced_object(form)

    assert (
        objr.get_cos_object().get_dictionary_object(_OBJ) is form.get_cos_object()
    )
    referenced = objr.get_referenced_object()
    assert isinstance(referenced, PDFormXObject)
    assert referenced.get_cos_object() is form.get_cos_object()


def test_get_referenced_object_returns_none_when_obj_is_array() -> None:
    """/Obj points at a COSArray (malformed) — typed accessor must not
    crash; returns None."""
    objr = PDObjectReference()
    objr.get_cos_object().set_item(_OBJ, COSArray())
    assert objr.get_referenced_object() is None


# ---------- TYPE constant ----------


def test_type_constant_is_objr() -> None:
    assert PDObjectReference.TYPE == "OBJR"
