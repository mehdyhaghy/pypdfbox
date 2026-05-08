from __future__ import annotations

from typing import Any, cast

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_marked_content_reference import (
    PDMarkedContentReference,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_object_reference import (
    PDObjectReference,
)

_PG = COSName.get_pdf_name("Pg")


class _NotPageWrapper:
    def get_cos_object(self) -> COSArray:
        return COSArray()


def test_wave322_mcr_set_page_rejects_non_page_wrapper_without_overwriting_pg() -> None:
    mcr = PDMarkedContentReference()
    page_dict = COSDictionary()
    mcr.set_page(page_dict)

    with pytest.raises(TypeError, match="PDPage, COSDictionary, or None"):
        mcr.set_page(cast(Any, _NotPageWrapper()))

    assert mcr.get_pg() is page_dict
    assert mcr.get_cos_object().get_dictionary_object(_PG) is page_dict


def test_wave322_objr_set_page_rejects_non_page_wrapper_without_overwriting_pg() -> None:
    objr = PDObjectReference()
    page_dict = COSDictionary()
    objr.set_page(page_dict)

    with pytest.raises(TypeError, match="PDPage, COSDictionary, or None"):
        objr.set_page(cast(Any, _NotPageWrapper()))

    assert objr.get_pg() is page_dict
    assert objr.get_cos_object().get_dictionary_object(_PG) is page_dict
