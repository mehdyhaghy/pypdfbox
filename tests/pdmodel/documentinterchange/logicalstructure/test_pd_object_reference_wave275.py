from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_object_reference import (
    PDObjectReference,
)

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_PG: COSName = COSName.get_pdf_name("Pg")
_OBJ: COSName = COSName.get_pdf_name("Obj")


def test_wave275_typed_page_round_trip_and_clear() -> None:
    from pypdfbox.pdmodel.pd_page import PDPage

    objr = PDObjectReference()
    page = PDPage()

    objr.set_page(page)

    assert objr.has_pg() is True
    assert objr.get_pg() is page.get_cos_object()
    typed = objr.get_page()
    assert isinstance(typed, PDPage)
    assert typed.get_cos_object() is page.get_cos_object()
    assert objr.get_cos_object().get_dictionary_object(_PG) is page.get_cos_object()

    objr.set_page(None)

    assert objr.has_pg() is False
    assert objr.get_pg() is None
    assert objr.get_page() is None
    assert objr.get_cos_object().get_dictionary_object(_PG) is None


def test_wave275_raw_pg_and_obj_aliases_preserve_cos_values() -> None:
    objr = PDObjectReference()
    page_dict = COSDictionary()
    page_dict.set_name(_TYPE, "Page")
    raw_obj = COSArray()

    objr.set_pg(page_dict)
    objr.set_obj(raw_obj)

    assert objr.get_pg() is page_dict
    assert objr.get_obj() is raw_obj
    assert objr.get_cos_object().get_dictionary_object(_PG) is page_dict
    assert objr.get_cos_object().get_dictionary_object(_OBJ) is raw_obj
    assert objr.get_referenced_object() is None

    objr.set_pg(None)
    objr.set_obj(None)

    assert objr.get_pg() is None
    assert objr.get_obj() is None


def test_wave275_set_referenced_object_accepts_only_annotation_or_xobject() -> None:
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )
    from pypdfbox.pdmodel.pd_page import PDPage

    objr = PDObjectReference()
    annotation = PDAnnotationLink()
    objr.set_referenced_object(annotation)
    assert objr.get_obj() is annotation.get_cos_object()

    form = PDFormXObject(COSStream())
    objr.set_referenced_object(form)
    assert objr.get_obj() is form.get_cos_object()
    assert objr.get_referenced_object().__class__ is PDFormXObject

    with pytest.raises(TypeError, match="PDAnnotation or PDXObject"):
        objr.set_referenced_object(PDPage())

    with pytest.raises(TypeError, match="Use set_obj for raw COSBase"):
        objr.set_referenced_object(COSDictionary())

    assert objr.get_obj() is form.get_cos_object()


def test_wave275_subtype_constants_and_predicates() -> None:
    assert PDObjectReference.SUBTYPE_ANNOT == "Annot"
    assert PDObjectReference.SUBTYPE_XOBJECT_FORM == "Form"
    assert PDObjectReference.SUBTYPE_XOBJECT_IMAGE == "Image"

    form_ref = PDObjectReference()
    form = COSStream()
    form.set_name(_SUBTYPE, PDObjectReference.SUBTYPE_XOBJECT_FORM)
    form_ref.set_obj(form)
    assert form_ref.is_referenced_form_xobject() is True
    assert form_ref.is_referenced_image_xobject() is False
    assert form_ref.is_referenced_annotation() is False

    image_ref = PDObjectReference()
    image = COSStream()
    image.set_name(_SUBTYPE, PDObjectReference.SUBTYPE_XOBJECT_IMAGE)
    image_ref.set_obj(image)
    assert image_ref.is_referenced_image_xobject() is True
    assert image_ref.is_referenced_form_xobject() is False
    assert image_ref.is_referenced_annotation() is False

    annot_ref = PDObjectReference()
    annot = COSDictionary()
    annot.set_name(_TYPE, PDObjectReference.SUBTYPE_ANNOT)
    annot_ref.set_obj(annot)
    assert annot_ref.is_referenced_annotation() is True
    assert annot_ref.is_referenced_form_xobject() is False
    assert annot_ref.is_referenced_image_xobject() is False


def test_wave275_malformed_shapes_are_raw_visible_but_typed_safe() -> None:
    objr = PDObjectReference()

    malformed_page = COSArray()
    objr.get_cos_object().set_item(_PG, malformed_page)
    assert objr.has_pg() is False
    assert objr.get_pg() is None
    assert objr.get_page() is None

    malformed_obj = COSArray()
    objr.get_cos_object().set_item(_OBJ, malformed_obj)
    assert objr.has_obj() is True
    assert objr.get_obj() is malformed_obj
    assert objr.get_referenced_object() is None
    assert objr.is_referenced_form_xobject() is False
    assert objr.is_referenced_image_xobject() is False
    assert objr.is_referenced_annotation() is False

    unknown_stream = COSStream()
    unknown_stream.set_name(_SUBTYPE, "PS")
    objr.set_obj(unknown_stream)
    assert objr.get_referenced_object() is None
    assert objr.is_referenced_form_xobject() is False
    assert objr.is_referenced_image_xobject() is False
    assert objr.is_referenced_annotation() is False

    bare_dict = COSDictionary()
    objr.set_obj(bare_dict)
    assert objr.get_obj() is bare_dict
    assert objr.is_referenced_annotation() is False
    assert objr.get_referenced_object() is None
