"""Upstream-named accessor parity tests for ``PDPageDestination``.

Mirrors the contract in
``org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination``.
"""
from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageFitDestination,
    PDPageFitHeightDestination,
    PDPageFitRectangleDestination,
    PDPageFitWidthDestination,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.pd_page import PDPage

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_PAGE: COSName = COSName.PAGE  # type: ignore[attr-defined]


def test_get_cos_array_returns_underlying_cos_array() -> None:
    """``get_cos_array()`` returns the same ``COSArray`` as ``get_cos_object()``."""
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("XYZ")])
    dest = PDPageXYZDestination(arr)

    assert isinstance(dest.get_cos_array(), COSArray)
    assert dest.get_cos_array() is arr
    assert dest.get_cos_array() is dest.get_cos_object()


def test_get_cos_array_default_constructed_destination() -> None:
    """Default-constructed destinations expose a non-None ``COSArray``
    that is at least 2 entries long (page slot + type-name slot)."""
    dest = PDPageFitDestination()
    arr = dest.get_cos_array()

    assert isinstance(arr, COSArray)
    assert arr.size() >= 2
    assert arr.get_name(1) == "Fit"


def test_get_type_returns_xyz() -> None:
    dest = PDPageXYZDestination()
    assert dest.get_type() == "XYZ"


def test_get_type_returns_fit() -> None:
    dest = PDPageFitDestination()
    assert dest.get_type() == "Fit"


def test_get_type_returns_fit_v_for_fit_height() -> None:
    """Per upstream naming: ``PDPageFitHeightDestination`` writes ``/FitV``
    (vertical line, page height fits the window)."""
    dest = PDPageFitHeightDestination()
    assert dest.get_type() == "FitV"


def test_get_type_returns_fit_h_for_fit_width() -> None:
    """Per upstream naming: ``PDPageFitWidthDestination`` writes ``/FitH``
    (horizontal line, page width fits the window)."""
    dest = PDPageFitWidthDestination()
    assert dest.get_type() == "FitH"


def test_get_type_returns_fit_r() -> None:
    dest = PDPageFitRectangleDestination()
    assert dest.get_type() == "FitR"


def test_get_type_returns_fit_b_when_bounding_box_flag_set() -> None:
    """The /FitB variant is set via the ``set_fit_bounding_box(True)`` helper
    and ``get_type()`` reflects the change."""
    dest = PDPageFitDestination()
    dest.set_fit_bounding_box(True)
    assert dest.get_type() == "FitB"


def test_get_page_returns_none_when_d0_is_integer() -> None:
    """Per upstream: ``get_page()`` returns ``null`` (None) when ``/D[0]``
    is a page index integer rather than a page dictionary."""
    dest = PDPageXYZDestination()
    dest.set_page_number(3)

    assert dest.get_page() is None
    # The page slot is an integer at this point.
    assert isinstance(dest.get_cos_array().get_object(0), COSInteger)


def test_raw_cos_number_page_slot_accepts_float_like_upstream() -> None:
    """PDFBox checks ``COSNumber`` for ``/D[0]`` and calls ``intValue()``.

    Malformed PDFs can carry a float where an integer page index is expected;
    mirror upstream by accepting it and truncating toward zero.
    """
    arr = COSArray([COSFloat(2.75), COSName.get_pdf_name("XYZ")])
    dest = PDPageXYZDestination(arr)

    assert dest.has_page_number() is True
    assert dest.get_page() is None
    assert dest.get_page_number() == 2
    assert dest.find_page_number() == 2
    assert dest.retrieve_page_number() == 2


def test_get_page_returns_none_for_explicit_negative_index() -> None:
    dest = PDPageFitDestination()
    dest.set_page_number(-1)
    assert dest.get_page() is None
    assert dest.get_page_number() == -1


def test_set_page_accepts_pd_page() -> None:
    """``set_page(PDPage)`` should unwrap to the page's underlying COSDictionary."""
    page = PDPage()
    dest = PDPageFitDestination()
    dest.set_page(page)

    assert dest.get_page() is page.get_cos_object()
    assert dest.get_cos_array().get_object(0) is page.get_cos_object()


def test_set_page_accepts_cos_dictionary() -> None:
    page_dict = COSDictionary()
    page_dict.set_item(_TYPE, _PAGE)

    dest = PDPageXYZDestination()
    dest.set_page(page_dict)

    assert dest.get_page() is page_dict


def test_set_page_none_writes_cos_null() -> None:
    dest = PDPageFitDestination()
    dest.set_page_number(2)
    dest.set_page(None)

    assert dest.get_cos_array().get(0) is COSNull.NULL
    assert dest.get_page() is None
    assert dest.get_page_number() == -1
