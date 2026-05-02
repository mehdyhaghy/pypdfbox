from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_marked_content_reference import (
    PDMarkedContentReference,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_object_reference import (
    PDObjectReference,
)

_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_PG = COSName.get_pdf_name("Pg")
_STM = COSName.get_pdf_name("Stm")
_STM_OWN = COSName.get_pdf_name("StmOwn")
_MCID = COSName.get_pdf_name("MCID")
_OBJ = COSName.get_pdf_name("Obj")


# ---------- PDMarkedContentReference ----------


def test_mcr_fresh_has_type_mcr() -> None:
    mcr = PDMarkedContentReference()
    assert mcr.get_cos_object().get_name(_TYPE) == "MCR"
    assert mcr.get_pg() is None
    assert mcr.get_stm() is None
    assert mcr.get_stm_own() is None


def test_mcr_wraps_existing_dictionary() -> None:
    dic = COSDictionary()
    dic.set_name(_TYPE, "MCR")
    mcr = PDMarkedContentReference(dic)
    assert mcr.get_cos_object() is dic


def test_mcr_set_mcid_round_trip() -> None:
    mcr = PDMarkedContentReference()
    mcr.set_mcid(7)
    assert mcr.get_mcid() == 7
    assert mcr.get_cos_object().get_int(_MCID) == 7


def test_mcr_set_mcid_negative_raises() -> None:
    mcr = PDMarkedContentReference()
    with pytest.raises(ValueError):
        mcr.set_mcid(-1)


def test_mcr_set_pg_round_trip() -> None:
    mcr = PDMarkedContentReference()
    page = COSDictionary()
    page.set_name(_TYPE, "Page")
    mcr.set_pg(page)
    assert mcr.get_pg() is page
    assert mcr.get_cos_object().get_dictionary_object(_PG) is page


def test_mcr_set_pg_none_removes() -> None:
    mcr = PDMarkedContentReference()
    page = COSDictionary()
    mcr.set_pg(page)
    mcr.set_pg(None)
    assert mcr.get_pg() is None


def test_mcr_set_stm_round_trip() -> None:
    mcr = PDMarkedContentReference()
    stream = COSStream()
    mcr.set_stm(stream)
    assert mcr.get_stm() is stream
    assert mcr.get_cos_object().get_dictionary_object(_STM) is stream


def test_mcr_set_stm_own_round_trip() -> None:
    mcr = PDMarkedContentReference()
    owner = COSDictionary()
    mcr.set_stm_own(owner)
    assert mcr.get_stm_own() is owner
    assert mcr.get_cos_object().get_dictionary_object(_STM_OWN) is owner


# ---------- PDObjectReference ----------


def test_objr_fresh_has_type_objr() -> None:
    objr = PDObjectReference()
    assert objr.get_cos_object().get_name(_TYPE) == "OBJR"
    assert objr.get_pg() is None
    assert objr.get_obj() is None


def test_objr_wraps_existing_dictionary() -> None:
    dic = COSDictionary()
    dic.set_name(_TYPE, "OBJR")
    objr = PDObjectReference(dic)
    assert objr.get_cos_object() is dic


def test_objr_set_pg_round_trip() -> None:
    objr = PDObjectReference()
    page = COSDictionary()
    page.set_name(_TYPE, "Page")
    objr.set_pg(page)
    assert objr.get_pg() is page
    assert objr.get_cos_object().get_dictionary_object(_PG) is page


def test_objr_set_obj_round_trip() -> None:
    objr = PDObjectReference()
    target = COSDictionary()
    target.set_name(_TYPE, "Annot")
    objr.set_obj(target)
    assert objr.get_obj() is target
    assert objr.get_cos_object().get_dictionary_object(_OBJ) is target


def test_objr_set_obj_none_removes() -> None:
    objr = PDObjectReference()
    target = COSDictionary()
    objr.set_obj(target)
    objr.set_obj(None)
    assert objr.get_obj() is None


# ---------- PDObjectReference.get_referenced_object ----------


def test_objr_get_referenced_object_none_when_obj_absent() -> None:
    objr = PDObjectReference()
    assert objr.get_referenced_object() is None


def test_objr_get_referenced_object_link_annotation() -> None:
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    objr = PDObjectReference()
    annot_dict = COSDictionary()
    annot_dict.set_name(_TYPE, "Annot")
    annot_dict.set_name(COSName.get_pdf_name("Subtype"), "Link")
    objr.set_obj(annot_dict)

    referenced = objr.get_referenced_object()
    assert isinstance(referenced, PDAnnotationLink)
    assert referenced.get_cos_object() is annot_dict


def test_objr_get_referenced_object_form_xobject_stream() -> None:
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject

    objr = PDObjectReference()
    stream = COSStream()
    stream.set_name(COSName.get_pdf_name("Subtype"), "Form")
    objr.set_obj(stream)

    referenced = objr.get_referenced_object()
    assert isinstance(referenced, PDFormXObject)
    assert referenced.get_cos_object() is stream


def test_objr_set_referenced_object_round_trip() -> None:
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    annotation = PDAnnotationLink()
    objr = PDObjectReference()
    objr.set_referenced_object(annotation)

    assert objr.get_cos_object().get_dictionary_object(_OBJ) is annotation.get_cos_object()
    referenced = objr.get_referenced_object()
    assert isinstance(referenced, PDAnnotationLink)
    assert referenced.get_cos_object() is annotation.get_cos_object()


def test_objr_set_referenced_object_none_clears_obj() -> None:
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    annotation = PDAnnotationLink()
    objr = PDObjectReference()
    objr.set_referenced_object(annotation)
    objr.set_referenced_object(None)
    assert objr.get_obj() is None
    assert objr.get_referenced_object() is None


# ---------- PDMarkedContentReference typed /Pg accessors ----------


def test_mcr_get_page_returns_none_when_pg_absent() -> None:
    mcr = PDMarkedContentReference()
    assert mcr.get_page() is None


def test_mcr_set_page_then_get_page_returns_pdpage() -> None:
    from pypdfbox.pdmodel.pd_page import PDPage

    mcr = PDMarkedContentReference()
    page = PDPage()
    mcr.set_page(page)
    got = mcr.get_page()
    assert isinstance(got, PDPage)
    # Same underlying COSDictionary — no copy.
    assert got.get_cos_object() is page.get_cos_object()


def test_mcr_set_page_none_removes_pg() -> None:
    from pypdfbox.pdmodel.pd_page import PDPage

    mcr = PDMarkedContentReference()
    mcr.set_page(PDPage())
    assert mcr.get_pg() is not None
    mcr.set_page(None)
    assert mcr.get_pg() is None
    assert mcr.get_page() is None


def test_mcr_get_page_skips_non_dictionary_pg() -> None:
    # Hand-construct a /Pg that is not a dict — get_page should return None.
    raw = COSDictionary()
    raw.set_name(_TYPE, "MCR")
    raw.set_int(_PG, 42)  # nonsense /Pg shape
    mcr = PDMarkedContentReference(raw)
    assert mcr.get_page() is None


def test_mcr_str_renders_mcid_format() -> None:
    """Mirrors upstream ``PDMarkedContentReference.toString()``."""
    mcr = PDMarkedContentReference()
    mcr.set_mcid(42)
    assert str(mcr) == "mcid=42"


def test_mcr_str_matches_repr() -> None:
    mcr = PDMarkedContentReference()
    mcr.set_mcid(7)
    assert str(mcr) == repr(mcr) == "mcid=7"


def test_mcr_str_when_mcid_absent_uses_default_minus_one() -> None:
    # No /MCID set — get_mcid() returns -1 (mirrors upstream getInt default).
    mcr = PDMarkedContentReference()
    assert str(mcr) == "mcid=-1"
