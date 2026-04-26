from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_membership_dictionary import (
    PDOptionalContentMembershipDictionary,
)
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList


def test_create_returns_none_for_none() -> None:
    assert PDPropertyList.create(None) is None


def test_create_dispatches_ocg_to_optional_content_group() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.get_pdf_name("OCG"))  # type: ignore[attr-defined]
    raw.set_string(COSName.get_pdf_name("Name"), "L1")

    result = PDPropertyList.create(raw)
    assert isinstance(result, PDOptionalContentGroup)
    assert result.get_cos_object() is raw


def test_create_dispatches_ocmd_to_membership_dictionary() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.get_pdf_name("OCMD"))  # type: ignore[attr-defined]

    result = PDPropertyList.create(raw)
    assert isinstance(result, PDOptionalContentMembershipDictionary)
    assert result.get_cos_object() is raw


def test_create_returns_none_for_unknown_type() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.get_pdf_name("Catalog"))  # type: ignore[attr-defined]
    assert PDPropertyList.create(raw) is None


def test_base_get_cos_object_round_trip() -> None:
    d = COSDictionary()
    pl = PDPropertyList(d)
    assert pl.get_cos_object() is d


def test_base_default_constructs_empty_dict() -> None:
    pl = PDPropertyList()
    assert isinstance(pl.get_cos_object(), COSDictionary)
