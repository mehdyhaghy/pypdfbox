from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.interactive.pagenavigation import PDThread, PDThreadBead
from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation

_F = COSName.get_pdf_name("F")
_I = COSName.get_pdf_name("I")
_N = COSName.get_pdf_name("N")
_P = COSName.get_pdf_name("P")
_R = COSName.get_pdf_name("R")
_T = COSName.get_pdf_name("T")
_V = COSName.get_pdf_name("V")


def test_wave276_thread_first_bead_sets_back_reference_and_links_chain() -> None:
    thread = PDThread()
    first = PDThreadBead()
    second = PDThreadBead()

    thread.set_first_bead(first)
    first.append_bead(second)

    assert thread.get_first_bead() == first
    assert first.get_thread() == thread
    assert [bead.get_cos_object() for bead in first.iter_beads()] == [
        first.get_cos_object(),
        second.get_cos_object(),
    ]
    assert first.count_beads() == 2


def test_wave276_next_previous_aliases_share_bead_slots() -> None:
    first = PDThreadBead()
    second = PDThreadBead()
    third = PDThreadBead()

    first.set_next(second)
    first.set_previous(third)

    assert first.get_next() == second
    assert first.get_next_bead() == second
    assert first.get_previous() == third
    assert first.get_previous_bead() == third

    first.set_next(None)
    first.set_previous(None)

    assert first.get_next() is None
    assert first.get_previous() is None
    assert not first.get_cos_object().contains_key(_N)
    assert not first.get_cos_object().contains_key(_V)


def test_wave276_thread_info_aliases_share_info_slot() -> None:
    thread = PDThread()
    info = PDDocumentInformation()
    info.set_title("Wave 276 Article")

    thread.set_info(info)

    fetched = thread.get_thread_info()
    alias_fetched = thread.get_info()
    assert fetched is not None
    assert alias_fetched is not None
    assert fetched.get_cos_object() is alias_fetched.get_cos_object()
    assert fetched.get_title() == "Wave 276 Article"
    assert thread.get_cos_object().get_dictionary_object(_I) is info.get_cos_object()

    thread.set_thread_info(None)
    assert thread.get_info() is None
    assert not thread.get_cos_object().contains_key(_I)


def test_wave276_equality_returns_not_implemented_for_unrelated_types() -> None:
    thread = PDThread()
    bead = PDThreadBead()

    assert PDThread.__eq__(thread, object()) is NotImplemented
    assert PDThreadBead.__eq__(bead, object()) is NotImplemented
    assert (thread == object()) is False
    assert (bead == object()) is False


def test_wave276_equality_and_hash_use_wrapped_dictionary_identity() -> None:
    raw_thread = COSDictionary()
    raw_bead = COSDictionary()

    thread_a = PDThread(raw_thread)
    thread_b = PDThread(raw_thread)
    bead_a = PDThreadBead(raw_bead)
    bead_b = PDThreadBead(raw_bead)

    assert thread_a == thread_b
    assert hash(thread_a) == hash(thread_b)
    assert bead_a == bead_b
    assert hash(bead_a) == hash(bead_b)
    assert thread_a != PDThread()
    assert bead_a != PDThreadBead()


def test_wave276_malformed_thread_references_return_none() -> None:
    raw = COSDictionary()
    raw.set_item(_F, COSName.get_pdf_name("not-a-bead"))
    raw.set_item(_I, COSInteger.get(276))
    thread = PDThread(raw)

    assert thread.get_first_bead() is None
    assert thread.get_thread_info() is None
    assert thread.get_info() is None


def test_wave276_malformed_bead_references_return_none() -> None:
    raw = COSDictionary()
    raw.set_item(_T, COSName.get_pdf_name("not-a-thread"))
    raw.set_item(_N, COSInteger.get(1))
    raw.set_item(_V, COSInteger.get(2))
    raw.set_item(_P, COSInteger.get(3))
    raw.set_item(_R, COSDictionary())
    bead = PDThreadBead(raw)

    assert bead.get_thread() is None
    assert bead.get_next_bead() is None
    assert bead.get_next() is None
    assert bead.get_previous_bead() is None
    assert bead.get_previous() is None
    assert bead.get_page() is None
    assert bead.get_rectangle() is None


def test_wave276_iter_beads_stops_on_malformed_next_reference() -> None:
    raw = COSDictionary()
    raw.set_item(_N, COSArray())
    bead = PDThreadBead(raw)

    walked = list(bead.iter_beads())

    assert len(walked) == 1
    assert walked[0] == bead
