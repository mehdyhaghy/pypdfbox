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


# ---------- equality / hashing parity with PDDictionaryWrapper ----------


def test_eq_uses_underlying_dictionary_identity() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Thread"))
    a = PDThread(raw)
    b = PDThread(raw)
    # Different wrapper instances over the same dictionary compare equal.
    assert a == b
    assert a is not b


def test_eq_distinct_dictionaries_are_not_equal() -> None:
    a = PDThread()
    b = PDThread()
    # Different default-constructed threads each have their own dictionary.
    assert a != b


def test_eq_returns_not_implemented_for_other_types() -> None:
    thread = PDThread()
    # Equality with an unrelated object falls back to NotImplemented and
    # therefore evaluates to False without raising.
    assert (thread == "not a thread") is False
    assert (thread == 42) is False
    assert (thread == None) is False  # noqa: E711 — explicit equality test


def test_hash_matches_equality_contract() -> None:
    raw = COSDictionary()
    a = PDThread(raw)
    b = PDThread(raw)
    assert a == b
    assert hash(a) == hash(b)
    # Equal wrappers can be used interchangeably as dict keys.
    bucket: dict[PDThread, str] = {a: "marker"}
    assert bucket[b] == "marker"


def test_hash_differs_for_distinct_dictionaries() -> None:
    a = PDThread()
    b = PDThread()
    # Hash collisions are allowed in principle, but ``id``-based hashing of
    # two freshly-allocated COSDictionary objects should not collide in
    # practice — guard the equality contract via a set of two members.
    assert len({a, b}) == 2


def test_get_thread_round_trip_via_set_first_bead_uses_eq() -> None:
    # When ``set_first_bead`` writes the back-reference on the bead, the
    # bead's ``get_thread()`` returns a *fresh* PDThread wrapper. With the
    # new equality contract that wrapper compares equal to the original.
    thread = PDThread()
    bead = PDThreadBead()
    thread.set_first_bead(bead)
    fetched = bead.get_thread()
    assert fetched == thread
