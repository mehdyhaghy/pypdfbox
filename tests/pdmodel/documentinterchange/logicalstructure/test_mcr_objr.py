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
