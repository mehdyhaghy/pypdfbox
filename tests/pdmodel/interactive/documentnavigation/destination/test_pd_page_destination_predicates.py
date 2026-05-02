"""Predicate-helper and no-argument retrieval tests for ``PDPageDestination``.

Covers ``has_page`` / ``has_page_number`` and the upstream-shaped
no-argument ``retrieve_page_number()`` that walks the page-dict's
``/Parent``/``/P`` chain to the page-tree root and returns the index.

Mirrors upstream
``org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination#retrievePageNumber()``.
"""
from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSNull
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageFitDestination,
    PDPageFitRectangleDestination,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_PAGE: COSName = COSName.PAGE  # type: ignore[attr-defined]
_PAGES: COSName = COSName.PAGES  # type: ignore[attr-defined]
_PARENT: COSName = COSName.PARENT  # type: ignore[attr-defined]
_KIDS: COSName = COSName.KIDS  # type: ignore[attr-defined]
_P: COSName = COSName.get_pdf_name("P")


# ---------- has_page / has_page_number predicates ----------


def test_has_page_false_on_default_constructed_destination() -> None:
    """A fresh destination has ``/D[0]`` set to ``COSNull``, so neither
    predicate reports a page."""
    dest = PDPageXYZDestination()
    assert dest.has_page() is False
    assert dest.has_page_number() is False


def test_has_page_number_true_after_set_page_number() -> None:
    dest = PDPageFitDestination()
    dest.set_page_number(3)
    assert dest.has_page_number() is True
    assert dest.has_page() is False


def test_has_page_true_after_set_page_with_pd_page() -> None:
    page = PDPage()
    dest = PDPageFitDestination()
    dest.set_page(page)
    assert dest.has_page() is True
    assert dest.has_page_number() is False


def test_has_page_true_when_d0_is_cos_dictionary() -> None:
    page_dict = COSDictionary()
    page_dict.set_item(_TYPE, _PAGE)
    arr = COSArray([page_dict, COSName.get_pdf_name("XYZ")])
    dest = PDPageXYZDestination(arr)
    assert dest.has_page() is True
    assert dest.has_page_number() is False


def test_has_page_predicates_round_trip_after_set_page_none() -> None:
    """After clearing the page slot the page predicates flip back to False."""
    dest = PDPageFitDestination()
    dest.set_page_number(2)
    assert dest.has_page_number() is True

    dest.set_page(None)
    assert dest.has_page() is False
    assert dest.has_page_number() is False


def test_has_page_number_recognizes_negative_values() -> None:
    """``set_page_number(-1)`` still writes a ``COSInteger`` and the
    predicate is independent of the integer's sign."""
    dest = PDPageXYZDestination()
    dest.set_page_number(-1)
    assert dest.has_page_number() is True
    assert dest.get_page_number() == -1


# ---------- retrieve_page_number() no-arg with /Parent walk ----------


def test_retrieve_page_number_returns_integer_index_with_no_arg() -> None:
    """When ``/D[0]`` is a ``COSInteger`` no walk is needed — the integer
    is returned verbatim, mirroring upstream ``retrievePageNumber()``."""
    dest = PDPageXYZDestination()
    dest.set_page_number(4)
    assert dest.retrieve_page_number() == 4


def test_retrieve_page_number_walks_parent_chain_to_pages_root() -> None:
    """Mirrors upstream ``retrievePageNumber()``: with no document context,
    the destination resolves the page index by walking the page dict's
    ``/Parent`` chain to the ``/Type /Pages`` root and computing the
    index via ``PDPageTree.indexOf``."""
    doc = PDDocument()
    pages = [PDPage(), PDPage(), PDPage()]
    for page in pages:
        doc.add_page(page)

    target_dict = pages[2].get_cos_object()
    arr = COSArray([target_dict, COSName.get_pdf_name("Fit")])
    dest = PDPageFitDestination(arr)

    assert dest.retrieve_page_number() == 2


def test_retrieve_page_number_no_arg_returns_minus_one_for_orphan_page_dict() -> None:
    """A page dict with no ``/Parent`` chain can't be resolved without
    a document context — return -1."""
    page_dict = COSDictionary()
    page_dict.set_item(_TYPE, _PAGE)

    arr = COSArray([page_dict, COSName.get_pdf_name("Fit")])
    dest = PDPageFitDestination(arr)

    assert dest.retrieve_page_number() == -1


def test_retrieve_page_number_walks_p_alias_when_parent_missing() -> None:
    """Upstream looks for ``/Parent`` *or* ``/P`` when climbing the page
    tree (PDFBOX page-tree variant). When a page dict only has ``/P``,
    we still resolve the index."""
    # Build a manual /Pages root with a single /Kids entry that uses
    # /P (rather than /Parent) for the upward link.
    page_dict = COSDictionary()
    page_dict.set_item(_TYPE, _PAGE)

    pages_root = COSDictionary()
    pages_root.set_item(_TYPE, _PAGES)
    pages_root.set_item(_KIDS, COSArray([page_dict]))
    pages_root.set_item(COSName.get_pdf_name("Count"), COSInteger.get(1))

    page_dict.set_item(_P, pages_root)

    arr = COSArray([page_dict, COSName.get_pdf_name("XYZ")])
    dest = PDPageXYZDestination(arr)

    assert dest.retrieve_page_number() == 0


def test_retrieve_page_number_returns_minus_one_when_top_lacks_pages_type() -> None:
    """If the chain terminates at a dict that isn't ``/Type /Pages``,
    upstream returns -1. We mirror that."""
    page_dict = COSDictionary()
    page_dict.set_item(_TYPE, _PAGE)

    # Top dict has /Kids but no /Type — not a valid /Pages root.
    rogue_root = COSDictionary()
    rogue_root.set_item(_KIDS, COSArray([page_dict]))
    page_dict.set_item(_PARENT, rogue_root)

    arr = COSArray([page_dict, COSName.get_pdf_name("Fit")])
    dest = PDPageFitDestination(arr)

    assert dest.retrieve_page_number() == -1


def test_retrieve_page_number_returns_minus_one_when_top_lacks_kids() -> None:
    """If the chain terminates at a dict missing ``/Kids`` entirely,
    return -1 even when /Type /Pages is set."""
    page_dict = COSDictionary()
    page_dict.set_item(_TYPE, _PAGE)

    weird_root = COSDictionary()
    weird_root.set_item(_TYPE, _PAGES)
    page_dict.set_item(_PARENT, weird_root)

    arr = COSArray([page_dict, COSName.get_pdf_name("XYZ")])
    dest = PDPageXYZDestination(arr)

    assert dest.retrieve_page_number() == -1


def test_retrieve_page_number_handles_self_referencing_parent_safely() -> None:
    """Defensive: a page dict whose ``/Parent`` points at itself (malformed
    PDF) must not loop forever. We bail with -1."""
    page_dict = COSDictionary()
    page_dict.set_item(_TYPE, _PAGE)
    page_dict.set_item(_PARENT, page_dict)  # cycle

    arr = COSArray([page_dict, COSName.get_pdf_name("Fit")])
    dest = PDPageFitDestination(arr)

    # Page dict itself isn't /Pages, so even though the cycle is one
    # iteration deep, we hit the cycle guard / type-check and return -1.
    assert dest.retrieve_page_number() == -1


def test_retrieve_page_number_no_arg_returns_minus_one_for_null_d0() -> None:
    """A default-constructed destination has ``COSNull`` at slot 0 — it
    is neither a number nor a page dict, so ``retrieve_page_number()``
    yields -1."""
    dest = PDPageFitRectangleDestination()
    assert dest.retrieve_page_number() == -1
    assert dest.find_page_number() == -1


def test_retrieve_page_number_with_document_argument_still_works() -> None:
    """Backwards-compatibility: passing ``document`` still delegates to
    ``find_page_number(document)`` — an existing-API call shape that
    pre-dates the upstream-parity no-arg form."""
    doc = PDDocument()
    pages = [PDPage(), PDPage()]
    for page in pages:
        doc.add_page(page)

    arr = COSArray([pages[1].get_cos_object(), COSName.get_pdf_name("Fit")])
    dest = PDPageFitDestination(arr)

    assert dest.retrieve_page_number(doc) == 1
    assert dest.retrieve_page_number(doc.get_pages()) == 1


# ---------- regression: predicate independence ----------


def test_has_page_and_has_page_number_are_mutually_exclusive() -> None:
    """The two predicates can never both be True for the same destination."""
    dest = PDPageXYZDestination()
    # default: both False (slot is COSNull)
    assert not (dest.has_page() and dest.has_page_number())

    dest.set_page_number(0)
    assert dest.has_page_number() and not dest.has_page()

    page = PDPage()
    dest.set_page(page)
    assert dest.has_page() and not dest.has_page_number()


def test_predicates_consistent_with_get_page_get_page_number() -> None:
    """``has_page()`` ↔ ``get_page() is not None``;
    ``has_page_number()`` ↔ ``get_page_number() != -1`` (when the slot
    isn't a page dict)."""
    dest = PDPageXYZDestination()
    dest.set_page_number(7)
    assert dest.has_page_number() is True
    assert dest.get_page_number() == 7
    assert dest.has_page() is False
    assert dest.get_page() is None

    page = PDPage()
    dest2 = PDPageFitDestination()
    dest2.set_page(page)
    assert dest2.has_page() is True
    assert dest2.get_page() is page.get_cos_object()
    assert dest2.has_page_number() is False
    assert dest2.get_page_number() == -1


def test_predicates_independent_of_destination_subclass() -> None:
    """The predicates live on the base ``PDPageDestination`` so every
    page-destination subclass exposes them with identical semantics."""
    page = PDPage()
    for cls in (
        PDPageXYZDestination,
        PDPageFitDestination,
        PDPageFitRectangleDestination,
    ):
        dest = cls()
        assert dest.has_page() is False
        assert dest.has_page_number() is False
        dest.set_page(page)
        assert dest.has_page() is True
        assert dest.has_page_number() is False


# ---------- COSNull at slot 0 ----------


def test_default_constructor_writes_cos_null_at_slot_zero() -> None:
    """The two-slot default fill grows the array with ``COSNull`` so
    upstream-parity callers can read ``/D`` immediately after construction
    without an IndexError. Predicates correctly see the null."""
    dest = PDPageFitDestination()
    arr = dest.get_cos_array()
    assert arr.size() >= 2
    # ``get_object`` resolves ``COSNull`` to Python ``None`` (matching
    # ``COSDocument.getObjectFromPool``'s null sentinel). The raw item
    # at slot 0 is the ``COSNull`` singleton.
    assert arr.get(0) is COSNull.NULL
    assert dest.has_page() is False
    assert dest.has_page_number() is False
