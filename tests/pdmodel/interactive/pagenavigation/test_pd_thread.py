from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation
from pypdfbox.pdmodel.interactive.pagenavigation import (
    PDThread,
    PDThreadBead,
)


def test_default_thread_has_type_thread() -> None:
    thread = PDThread()
    cos = thread.get_cos_object()
    assert cos.get_name(COSName.get_pdf_name("Type")) == "Thread"


def test_wrap_existing_dictionary_preserves_identity() -> None:
    raw = COSDictionary()
    thread = PDThread(raw)
    assert thread.get_cos_object() is raw


def test_thread_info_round_trip() -> None:
    thread = PDThread()
    info = PDDocumentInformation()
    info.set_title("Test Article")
    thread.set_thread_info(info)

    fetched = thread.get_thread_info()
    assert fetched is not None
    assert fetched.get_title() == "Test Article"
    # The /I entry must point at the same underlying dictionary.
    assert (
        thread.get_cos_object().get_dictionary_object(COSName.get_pdf_name("I"))
        is info.get_cos_object()
    )


def test_thread_info_absent_returns_none() -> None:
    thread = PDThread()
    assert thread.get_thread_info() is None


def test_set_thread_info_none_removes_entry() -> None:
    thread = PDThread()
    info = PDDocumentInformation()
    thread.set_thread_info(info)
    assert thread.get_thread_info() is not None
    thread.set_thread_info(None)
    assert thread.get_thread_info() is None
    assert not thread.get_cos_object().contains_key(COSName.get_pdf_name("I"))


def test_first_bead_round_trip_sets_back_reference() -> None:
    thread = PDThread()
    bead = PDThreadBead()
    thread.set_first_bead(bead)

    fetched = thread.get_first_bead()
    assert fetched is not None
    assert fetched.get_cos_object() is bead.get_cos_object()
    # set_first_bead must update the bead's /T pointer per upstream contract.
    bead_thread = bead.get_thread()
    assert bead_thread is not None
    assert bead_thread.get_cos_object() is thread.get_cos_object()


def test_first_bead_absent_returns_none() -> None:
    thread = PDThread()
    assert thread.get_first_bead() is None


def test_set_first_bead_none_removes_entry() -> None:
    thread = PDThread()
    bead = PDThreadBead()
    thread.set_first_bead(bead)
    thread.set_first_bead(None)
    assert thread.get_first_bead() is None
    assert not thread.get_cos_object().contains_key(COSName.get_pdf_name("F"))


def test_get_cos_object_returns_dictionary() -> None:
    thread = PDThread()
    assert isinstance(thread.get_cos_object(), COSDictionary)


def test_get_info_alias_matches_get_thread_info() -> None:
    thread = PDThread()
    info = PDDocumentInformation()
    info.set_author("Ada Lovelace")
    thread.set_info(info)
    fetched = thread.get_info()
    assert fetched is not None
    assert fetched.get_author() == "Ada Lovelace"
    # Both accessors must observe the same /I entry.
    via_thread_info = thread.get_thread_info()
    assert via_thread_info is not None
    assert via_thread_info.get_cos_object() is fetched.get_cos_object()


def test_set_info_none_removes_entry() -> None:
    thread = PDThread()
    thread.set_info(PDDocumentInformation())
    thread.set_info(None)
    assert thread.get_info() is None
    assert not thread.get_cos_object().contains_key(COSName.get_pdf_name("I"))
