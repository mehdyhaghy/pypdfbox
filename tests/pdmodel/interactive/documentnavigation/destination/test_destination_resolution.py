from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageFitDestination,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_PAGE: COSName = COSName.PAGE  # type: ignore[attr-defined]


def test_find_page_number_returns_integer_index() -> None:
    """When ``/D[0]`` is a COSInteger, ``find_page_number()`` returns it."""
    dest = PDPageXYZDestination()
    dest.set_page_number(5)

    assert dest.find_page_number() == 5
    assert dest.get_page_number() == 5


def test_find_page_number_returns_minus_one_for_unresolved_page_dict() -> None:
    """When ``/D[0]`` is a page COSDictionary, lite resolution returns -1
    (deferred: full document-context lookup not implemented)."""
    page_dict = COSDictionary()
    page_dict.set_item(_TYPE, _PAGE)

    arr = COSArray([page_dict, COSName.get_pdf_name("XYZ")])
    dest = PDPageXYZDestination(arr)

    assert dest.find_page_number() == -1


def test_get_page_returns_page_dict_when_d0_is_dictionary() -> None:
    """``get_page()`` returns the underlying page dict when ``/D[0]`` is
    a COSDictionary; ``None`` when it is anything else (e.g. a COSInteger)."""
    page_dict = COSDictionary()
    page_dict.set_item(_TYPE, _PAGE)

    arr = COSArray([page_dict, COSName.get_pdf_name("XYZ")])
    dest = PDPageXYZDestination(arr)

    assert dest.get_page() is page_dict


def test_get_page_returns_none_when_d0_is_integer() -> None:
    dest = PDPageXYZDestination()
    dest.set_page_number(7)

    assert dest.get_page() is None


def test_find_page_number_resolves_page_dict_against_document() -> None:
    """When ``/D[0]`` is a Page COSDictionary and a document is supplied,
    ``find_page_number(document)`` returns the 0-based index of that page
    within the document's page tree."""
    doc = PDDocument()
    pages = [PDPage(), PDPage(), PDPage()]
    for page in pages:
        doc.add_page(page)

    target_dict = pages[1].get_cos_object()
    arr = COSArray([target_dict, COSName.get_pdf_name("Fit")])
    dest = PDPageFitDestination(arr)

    assert dest.find_page_number(doc) == 1
    assert dest.retrieve_page_number(doc) == 1
    # Without a document context we still return -1 (page-dict path).
    assert dest.find_page_number() == -1
