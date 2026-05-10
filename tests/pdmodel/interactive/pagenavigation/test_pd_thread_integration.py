from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.pagenavigation import (
    PDThread,
    PDThreadBead,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def test_document_catalog_get_threads_empty_when_absent() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    assert catalog.get_threads() == []


def test_document_catalog_set_threads_round_trip() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()

    t1 = PDThread()
    t2 = PDThread()
    catalog.set_threads([t1, t2])

    threads = catalog.get_threads()
    assert len(threads) == 2
    assert threads[0].get_cos_object() is t1.get_cos_object()
    assert threads[1].get_cos_object() is t2.get_cos_object()
    # /Threads must be a COSArray of dictionaries.
    arr = catalog.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Threads")
    )
    assert isinstance(arr, COSArray)
    assert arr.size() == 2


def test_document_catalog_set_threads_none_removes_entry() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    catalog.set_threads([PDThread()])
    catalog.set_threads(None)
    # ``set_threads(None)`` strips ``/Threads`` from the catalog. Note the
    # check happens before any read, since :meth:`get_threads` mirrors
    # upstream by auto-creating an empty array on miss.
    assert not catalog.get_cos_object().contains_key(
        COSName.get_pdf_name("Threads")
    )
    assert catalog.get_threads() == []


def test_document_catalog_set_threads_rejects_non_thread() -> None:
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    try:
        catalog.set_threads(["not a thread"])  # type: ignore[list-item]
    except TypeError:
        pass
    else:
        raise AssertionError("expected TypeError for non-PDThread element")


def test_pd_page_get_thread_beads_empty_when_absent() -> None:
    page = PDPage()
    assert page.get_thread_beads() == []


def test_pd_page_set_thread_beads_round_trip() -> None:
    page = PDPage()

    b1 = PDThreadBead()
    b1.set_rectangle(PDRectangle(0.0, 0.0, 50.0, 50.0))
    b1.set_page(page)

    b2 = PDThreadBead()
    b2.set_rectangle(PDRectangle(50.0, 50.0, 100.0, 100.0))
    b2.set_page(page)

    page.set_thread_beads([b1, b2])

    beads = page.get_thread_beads()
    assert len(beads) == 2
    assert beads[0].get_cos_object() is b1.get_cos_object()
    assert beads[1].get_cos_object() is b2.get_cos_object()
    arr = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("B"))
    assert isinstance(arr, COSArray)
    assert arr.size() == 2


def test_pd_page_set_thread_beads_none_removes_entry() -> None:
    page = PDPage()
    page.set_thread_beads([PDThreadBead()])
    page.set_thread_beads(None)
    assert page.get_thread_beads() == []
    assert not page.get_cos_object().contains_key(COSName.get_pdf_name("B"))


def test_pd_page_set_thread_beads_rejects_non_bead() -> None:
    page = PDPage()
    try:
        page.set_thread_beads(["not a bead"])  # type: ignore[list-item]
    except TypeError:
        pass
    else:
        raise AssertionError("expected TypeError for non-PDThreadBead element")


def test_pd_page_get_thread_beads_skips_non_dict_with_none_placeholder() -> None:
    page = PDPage()
    arr = COSArray()
    bead = PDThreadBead()
    arr.add(bead.get_cos_object())
    # Insert a non-dictionary entry to verify defensive handling.
    arr.add(COSName.get_pdf_name("oops"))
    page.get_cos_object().set_item(COSName.get_pdf_name("B"), arr)

    beads = page.get_thread_beads()
    assert len(beads) == 2
    assert beads[0] is not None
    assert beads[1] is None


def test_thread_with_first_bead_back_reference_round_trip() -> None:
    # End-to-end: a Thread referenced from /Threads carrying its first bead
    # which itself references the page.
    doc = PDDocument()
    page = doc.get_page(0) if doc.get_number_of_pages() > 0 else PDPage()
    if doc.get_number_of_pages() == 0:
        doc.add_page(page)

    thread = PDThread()
    bead = PDThreadBead()
    bead.set_page(page)
    bead.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 100.0))
    thread.set_first_bead(bead)

    doc.get_document_catalog().set_threads([thread])
    page.set_thread_beads([bead])

    threads = doc.get_document_catalog().get_threads()
    assert len(threads) == 1
    fetched_thread = threads[0]
    fetched_bead = fetched_thread.get_first_bead()
    assert fetched_bead is not None
    assert fetched_bead.get_cos_object() is bead.get_cos_object()
    bead_thread = fetched_bead.get_thread()
    assert bead_thread is not None
    assert bead_thread.get_cos_object() is thread.get_cos_object()
    bead_page = fetched_bead.get_page()
    assert bead_page is not None
    assert bead_page.get_cos_object() is page.get_cos_object()


def test_pd_page_thread_beads_wrap_existing_dict() -> None:
    raw_page = COSDictionary()
    raw_page.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    arr = COSArray()
    raw_bead = COSDictionary()
    raw_bead.set_item(COSName.TYPE, COSName.get_pdf_name("Bead"))  # type: ignore[attr-defined]
    arr.add(raw_bead)
    raw_page.set_item(COSName.get_pdf_name("B"), arr)

    page = PDPage(raw_page)
    beads = page.get_thread_beads()
    assert len(beads) == 1
    assert beads[0].get_cos_object() is raw_bead
