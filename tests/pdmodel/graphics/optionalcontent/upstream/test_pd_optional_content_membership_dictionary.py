"""Ported from upstream Apache PDFBox 3.0.x:
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/optionalcontent/PDOptionalContentMembershipDictionaryTest.java``.

Translation rules per the project's "Test Porting Conventions".
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    MembershipDictionaryVisibilityPolicy,
    PDOptionalContentGroup,
    PDOptionalContentMembershipDictionary,
)


# Java: testCreateNewOCMD
def test_create_new_ocmd() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    assert ocmd.get_cos_object().get_dictionary_object(
        COSName.TYPE  # type: ignore[attr-defined]
    ) == COSName.get_pdf_name("OCMD")
    # Default visibility policy is "AnyOn" per PDF 1.7.
    assert ocmd.get_visibility_policy() == "AnyOn"


# Java: testRejectWrongType
def test_reject_wrong_type() -> None:
    raw = COSDictionary()
    raw.set_item(
        COSName.TYPE,  # type: ignore[attr-defined]
        COSName.get_pdf_name("Catalog"),
    )
    with pytest.raises(ValueError):
        PDOptionalContentMembershipDictionary(raw)


# Java: testSetVisibilityPolicy
def test_set_visibility_policy() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_visibility_policy("AllOff")
    assert ocmd.get_visibility_policy() == "AllOff"
    with pytest.raises(ValueError):
        ocmd.set_visibility_policy("Bogus")


# Java: testSetVisibilityPolicyEnum — typed enum.
def test_set_visibility_policy_enum() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_visibility_policy(
        MembershipDictionaryVisibilityPolicy.ALL_ON
    )
    assert ocmd.get_visibility_policy() == "AllOn"
    assert (
        ocmd.get_visibility_policy_enum()
        is MembershipDictionaryVisibilityPolicy.ALL_ON
    )


# Java: testOCGsArrayRoundTrip
def test_ocgs_array_round_trip() -> None:
    g1 = PDOptionalContentGroup("g1")
    g2 = PDOptionalContentGroup("g2")
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_ocgs([g1, g2])
    names = [g.get_name() for g in ocmd.get_ocgs()]
    assert names == ["g1", "g2"]


# Java: testVisibilityExpressionRoundTrip
def test_visibility_expression_round_trip() -> None:
    g = PDOptionalContentGroup("g")
    ocmd = PDOptionalContentMembershipDictionary()
    ve = COSArray()
    ve.add(COSName.get_pdf_name("And"))
    ve.add(g.get_cos_object())
    ocmd.set_visibility_expression(ve)
    assert ocmd.get_visibility_expression() is ve
    ocmd.set_visibility_expression(None)
    assert ocmd.get_visibility_expression() is None
