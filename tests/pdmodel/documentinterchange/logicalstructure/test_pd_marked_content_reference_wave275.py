from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream, COSString
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_marked_content_reference import (
    PDMarkedContentReference,
)
from pypdfbox.pdmodel.pd_page import PDPage

_PG = COSName.get_pdf_name("Pg")
_STM = COSName.get_pdf_name("Stm")
_STM_OWN = COSName.get_pdf_name("StmOwn")
_MCID = COSName.get_pdf_name("MCID")


def test_typed_page_accessors_round_trip_without_copying_page_dict() -> None:
    mcr = PDMarkedContentReference()
    page = PDPage()

    mcr.set_page(page)
    got = mcr.get_page()

    assert isinstance(got, PDPage)
    assert got.get_cos_object() is page.get_cos_object()
    assert mcr.get_pg() is page.get_cos_object()
    assert mcr.has_pg()


def test_typed_page_setter_accepts_raw_dictionary_alias() -> None:
    mcr = PDMarkedContentReference()
    page_dict = COSDictionary()

    mcr.set_page(page_dict)
    got = mcr.get_page()

    assert isinstance(got, PDPage)
    assert got.get_cos_object() is page_dict
    assert mcr.get_pg() is page_dict


def test_raw_pg_aliases_round_trip_and_clear() -> None:
    mcr = PDMarkedContentReference()
    page_dict = COSDictionary()

    mcr.set_pg(page_dict)
    got = mcr.get_page()

    assert mcr.get_pg() is page_dict
    assert got is not None
    assert got.get_cos_object() is page_dict
    assert mcr.has_pg()

    mcr.set_pg(None)
    assert mcr.get_pg() is None
    assert mcr.get_page() is None
    assert not mcr.has_pg()
    assert mcr.get_cos_object().get_dictionary_object(_PG) is None


def test_page_clear_removes_pg_entry() -> None:
    mcr = PDMarkedContentReference()
    mcr.set_page(PDPage())

    mcr.set_page(None)

    assert mcr.get_page() is None
    assert mcr.get_pg() is None
    assert not mcr.has_pg()
    assert mcr.get_cos_object().get_dictionary_object(_PG) is None


def test_stream_aliases_round_trip_presence_and_clear() -> None:
    mcr = PDMarkedContentReference()
    stream = COSStream()

    mcr.set_stm(stream)
    assert mcr.get_stm() is stream
    assert mcr.has_stm()

    mcr.set_stm(None)
    assert mcr.get_stm() is None
    assert not mcr.has_stm()
    assert mcr.get_cos_object().get_dictionary_object(_STM) is None


def test_stream_owner_aliases_round_trip_presence_and_clear() -> None:
    mcr = PDMarkedContentReference()
    owner = COSDictionary()

    mcr.set_stm_own(owner)
    assert mcr.get_stm_own() is owner
    assert mcr.has_stm_own()

    mcr.set_stm_own(None)
    assert mcr.get_stm_own() is None
    assert not mcr.has_stm_own()
    assert mcr.get_cos_object().get_dictionary_object(_STM_OWN) is None


def test_mcid_round_trip_presence_and_negative_rejection() -> None:
    mcr = PDMarkedContentReference()
    assert mcr.get_mcid() == PDMarkedContentReference.MCID_NOT_SET
    assert not mcr.has_mcid()

    mcr.set_mcid(0)
    assert mcr.get_mcid() == 0
    assert mcr.has_mcid()

    with pytest.raises(ValueError):
        mcr.set_mcid(-1)


def test_malformed_shapes_return_none_or_default_without_hiding_presence() -> None:
    dictionary = COSDictionary()
    dictionary.set_item(_PG, COSArray())
    dictionary.set_item(_STM, COSDictionary())
    dictionary.set_item(_STM_OWN, COSString("owner"))
    dictionary.set_item(_MCID, COSString("7"))

    mcr = PDMarkedContentReference(dictionary)

    assert mcr.get_pg() is None
    assert mcr.get_page() is None
    assert not mcr.has_pg()
    assert mcr.get_stm() is None
    assert not mcr.has_stm()
    assert mcr.get_stm_own() is None
    assert not mcr.has_stm_own()
    assert mcr.get_mcid() == PDMarkedContentReference.MCID_NOT_SET
    assert mcr.has_mcid()
