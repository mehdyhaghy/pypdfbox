"""Upstream-parity tests for PDPropertyList.

Apache PDFBox 3.0 does not ship a dedicated ``PDPropertyListTest.java`` for
``org.apache.pdfbox.pdmodel.documentinterchange.markedcontent.PDPropertyList``
(verified against the 3.0 branch of ``apache/pdfbox`` on 2026-04-27).

Because there is no upstream JUnit test to translate, this file pins the
behavioural contract of the upstream ``create(COSDictionary)`` factory
exactly as it appears in upstream's source. If/when upstream adds a test,
those translations should be added here verbatim per CLAUDE.md test-porting
conventions and PROVENANCE.md updated.

Upstream contract (from
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/documentinterchange/
markedcontent/PDPropertyList.java``)::

    public static PDPropertyList create(COSDictionary dict)
    {
        COSBase item = dict.getItem(COSName.TYPE);
        if (COSName.OCG.equals(item))
            return new PDOptionalContentGroup(dict);
        else if (COSName.OCMD.equals(item))
            return new PDOptionalContentMembershipDictionary(dict);
        else
            return new PDPropertyList(dict);
    }
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_membership_dictionary import (
    PDOptionalContentMembershipDictionary,
)
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_create_with_ocg_type_returns_optional_content_group() -> None:
    """Mirrors ``COSName.OCG.equals(item)`` branch of upstream ``create``."""
    dict_ = COSDictionary()
    dict_.set_item(COSName.TYPE, _name("OCG"))  # type: ignore[attr-defined]

    result = PDPropertyList.create(dict_)

    assert result is not None
    assert isinstance(result, PDOptionalContentGroup)
    assert result.get_cos_object() is dict_


def test_create_with_ocmd_type_returns_membership_dictionary() -> None:
    """Mirrors ``COSName.OCMD.equals(item)`` branch of upstream ``create``."""
    dict_ = COSDictionary()
    dict_.set_item(COSName.TYPE, _name("OCMD"))  # type: ignore[attr-defined]

    result = PDPropertyList.create(dict_)

    assert result is not None
    assert isinstance(result, PDOptionalContentMembershipDictionary)
    assert result.get_cos_object() is dict_


def test_create_with_unknown_type_returns_bare_property_list() -> None:
    """Mirrors the ``else`` branch (``return new PDPropertyList(dict)``)."""
    dict_ = COSDictionary()
    dict_.set_item(COSName.TYPE, _name("SomethingElse"))  # type: ignore[attr-defined]

    result = PDPropertyList.create(dict_)

    assert result is not None
    assert type(result) is PDPropertyList
    assert result.get_cos_object() is dict_


def test_create_with_no_type_returns_bare_property_list() -> None:
    """``getItem(TYPE)`` returns null for a typeless dict; ``equals`` is
    false on both branches; the fallback ``new PDPropertyList(dict)``
    runs."""
    dict_ = COSDictionary()

    result = PDPropertyList.create(dict_)

    assert result is not None
    assert type(result) is PDPropertyList
    assert result.get_cos_object() is dict_


def test_get_cos_object_returns_backing_dictionary() -> None:
    """Mirrors ``getCOSObject()``: returns the same dictionary instance the
    instance was constructed with."""
    dict_ = COSDictionary()
    pl = PDPropertyList(dict_)

    assert pl.get_cos_object() is dict_


def test_default_constructor_creates_empty_dictionary() -> None:
    """Mirrors the protected no-arg constructor, which seeds an empty
    ``COSDictionary``."""
    pl = PDPropertyList()
    cos = pl.get_cos_object()

    assert isinstance(cos, COSDictionary)
    # No /Type or any other entries on a freshly constructed list.
    assert cos.get_item(COSName.TYPE) is None  # type: ignore[attr-defined]
