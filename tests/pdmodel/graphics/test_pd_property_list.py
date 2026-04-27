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


def test_create_returns_bare_property_list_for_unknown_type() -> None:
    """Upstream behaviour: an unknown /Type yields a bare PDPropertyList
    wrapping the supplied dictionary (the upstream "todo: more types"
    fallback). It must NOT be an OCG or OCMD."""
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.get_pdf_name("Catalog"))  # type: ignore[attr-defined]
    result = PDPropertyList.create(raw)
    assert result is not None
    assert isinstance(result, PDPropertyList)
    assert not isinstance(result, PDOptionalContentGroup)
    assert not isinstance(result, PDOptionalContentMembershipDictionary)
    assert result.get_cos_object() is raw


def test_create_returns_bare_property_list_for_missing_type() -> None:
    """A dictionary with no /Type entry still produces a bare
    PDPropertyList — it is *not* None."""
    raw = COSDictionary()
    result = PDPropertyList.create(raw)
    assert result is not None
    assert isinstance(result, PDPropertyList)
    assert not isinstance(result, PDOptionalContentGroup)
    assert not isinstance(result, PDOptionalContentMembershipDictionary)
    assert result.get_cos_object() is raw


def test_create_rejects_non_dictionary() -> None:
    """Pythonic safety net: refuse non-COSDictionary input rather than
    silently mis-typing the result."""
    import pytest

    with pytest.raises(TypeError):
        PDPropertyList.create("not a dict")  # type: ignore[arg-type]


def test_base_get_cos_object_round_trip() -> None:
    d = COSDictionary()
    pl = PDPropertyList(d)
    assert pl.get_cos_object() is d


def test_base_default_constructs_empty_dict() -> None:
    pl = PDPropertyList()
    assert isinstance(pl.get_cos_object(), COSDictionary)


def test_upstream_named_alias_re_exports_same_class() -> None:
    """Upstream places PDPropertyList under
    documentinterchange.markedcontent. The pypdfbox alias must be the
    *same* class object as the canonical implementation so isinstance()
    checks succeed across both import paths."""
    from pypdfbox.pdmodel.documentinterchange.markedcontent import (
        PDPropertyList as MarkedContentPDPropertyList,
    )
    from pypdfbox.pdmodel.documentinterchange.markedcontent.pd_property_list import (
        PDPropertyList as DirectAlias,
    )

    assert MarkedContentPDPropertyList is PDPropertyList
    assert DirectAlias is PDPropertyList
