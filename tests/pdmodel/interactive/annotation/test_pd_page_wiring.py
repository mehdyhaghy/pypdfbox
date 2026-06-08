"""End-to-end check for ``PDPage.get_annotations`` / ``set_annotations``."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel import PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationCircle,
    PDAnnotationLink,
    PDAnnotationSquare,
    PDAnnotationText,
    PDAnnotationUnknown,
    PDAnnotationWidget,
)


def test_page_no_annots_returns_empty_list() -> None:
    page = PDPage()
    assert page.get_annotations() == []


def test_page_get_annotations_dispatches_per_subtype() -> None:
    page = PDPage()
    annots = COSArray()
    for subtype in ("Link", "Text", "Square", "Circle", "Widget", "Unknownish"):
        d = COSDictionary()
        d.set_name(COSName.SUBTYPE, subtype)  # type: ignore[attr-defined]
        annots.add(d)
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)

    result = page.get_annotations()
    assert len(result) == 6
    assert isinstance(result[0], PDAnnotationLink)
    assert isinstance(result[1], PDAnnotationText)
    assert isinstance(result[2], PDAnnotationSquare)
    assert isinstance(result[3], PDAnnotationCircle)
    assert isinstance(result[4], PDAnnotationWidget)
    assert isinstance(result[5], PDAnnotationUnknown)


def test_page_get_annotations_raises_on_non_dict_entry() -> None:
    """A non-``null``, non-dict /Annots member is NOT silently skipped:
    upstream ``getAnnotations`` passes it to ``createAnnotation``, which
    throws ``IOException``. pypdfbox propagates the equivalent ``TypeError``
    (wave 1515 aligned the page loop to upstream — only ``null`` is skipped)."""
    page = PDPage()
    annots = COSArray()
    # A stray name in /Annots is illegal; upstream raises rather than skip.
    annots.add(COSName.get_pdf_name("garbage"))
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Text")  # type: ignore[attr-defined]
    annots.add(d)
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)

    with pytest.raises(TypeError):
        page.get_annotations()


def test_page_set_annotations_round_trip() -> None:
    page = PDPage()
    link = PDAnnotationLink()
    link.set_rectangle(PDRectangle(10.0, 10.0, 100.0, 100.0))
    text = PDAnnotationText()
    text.set_contents("hi")

    page.set_annotations([link, text])

    rt = page.get_annotations()
    assert len(rt) == 2
    # Same backing dicts → equality holds via PDAnnotation.__eq__.
    assert isinstance(rt[0], PDAnnotationLink)
    assert isinstance(rt[1], PDAnnotationText)
    assert rt[0] == link
    assert rt[1] == text
    assert rt[1].get_contents() == "hi"


def test_page_set_annotations_none_removes_entry() -> None:
    page = PDPage()
    page.set_annotations([PDAnnotationText()])
    assert len(page.get_annotations()) == 1
    page.set_annotations(None)
    assert page.get_annotations() == []
    assert page.get_cos_object().get_item(COSName.get_pdf_name("Annots")) is None


def test_page_set_annotations_rejects_non_pdannotation() -> None:
    page = PDPage()
    with pytest.raises(TypeError):
        page.set_annotations(["not-an-annotation"])  # type: ignore[list-item]


def test_page_get_annotations_when_annots_not_array() -> None:
    page = PDPage()
    # Bogus type — exercise the defensive fallback.
    page.get_cos_object().set_item(
        COSName.get_pdf_name("Annots"),
        COSName.get_pdf_name("oops"),
    )
    assert page.get_annotations() == []
