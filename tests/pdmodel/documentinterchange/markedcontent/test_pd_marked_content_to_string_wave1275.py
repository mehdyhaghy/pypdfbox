"""Wave 1275 round-out: ``PDMarkedContent.to_string()`` explicit method."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.markedcontent.pd_marked_content import (
    PDMarkedContent,
)


def test_to_string_with_no_tag_or_properties() -> None:
    mc = PDMarkedContent(None, None)
    # Mirrors upstream ``PDMarkedContent.toString()``
    # (PDMarkedContent.java line 194): ``tag=<tag>, properties=<props>,
    # contents=<list>``.
    assert mc.to_string() == "tag=None, properties=None, contents=[]"


def test_to_string_with_tag_and_properties() -> None:
    properties = COSDictionary()
    properties.set_int(COSName.get_pdf_name("MCID"), 5)
    mc = PDMarkedContent(COSName.get_pdf_name("Span"), properties)
    rendered = mc.to_string()
    assert rendered.startswith("tag=Span, properties=")
    assert rendered.endswith(", contents=[]")


def test_to_string_matches_str() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("P"), None)
    assert mc.to_string() == str(mc)
