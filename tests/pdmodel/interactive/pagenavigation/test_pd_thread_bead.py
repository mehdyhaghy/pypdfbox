from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.interactive.pagenavigation import (
    PDThread,
    PDThreadBead,
)


def test_default_bead_has_type_bead_and_circular_links() -> None:
    bead = PDThreadBead()
    cos = bead.get_cos_object()
    assert cos.get_name(COSName.get_pdf_name("Type")) == "Bead"
    # On a fresh bead /N and /V both point back to the bead itself.
    assert (
        cos.get_dictionary_object(COSName.get_pdf_name("N"))
        is cos
    )
    assert (
        cos.get_dictionary_object(COSName.get_pdf_name("V"))
        is cos
    )


def test_wrap_existing_dictionary_preserves_identity() -> None:
    raw = COSDictionary()
    bead = PDThreadBead(raw)
    assert bead.get_cos_object() is raw


def test_thread_round_trip() -> None:
    bead = PDThreadBead()
    thread = PDThread()
    bead.set_thread(thread)
    fetched = bead.get_thread()
    assert fetched is not None
    assert fetched.get_cos_object() is thread.get_cos_object()


def test_thread_absent_returns_none() -> None:
    bead = PDThreadBead(COSDictionary())
    assert bead.get_thread() is None


def test_next_bead_round_trip() -> None:
    a = PDThreadBead()
    b = PDThreadBead()
    a.set_next_bead(b)
    fetched = a.get_next_bead()
    assert fetched is not None
    assert fetched.get_cos_object() is b.get_cos_object()


def test_previous_bead_round_trip() -> None:
    a = PDThreadBead()
    b = PDThreadBead()
    a.set_previous_bead(b)
    fetched = a.get_previous_bead()
    assert fetched is not None
    assert fetched.get_cos_object() is b.get_cos_object()


def test_next_and_previous_absent_return_none() -> None:
    bead = PDThreadBead(COSDictionary())
    assert bead.get_next_bead() is None
    assert bead.get_previous_bead() is None


def test_append_bead_links_correctly_in_two_bead_chain() -> None:
    # Start from a single bead — its /N and /V point to itself (a one-element
    # circular list). Appending another bead should produce a two-element
    # circular list: a <-> b <-> a.
    a = PDThreadBead()
    b = PDThreadBead()
    a.append_bead(b)

    a_next = a.get_next_bead()
    a_prev = a.get_previous_bead()
    b_next = b.get_next_bead()
    b_prev = b.get_previous_bead()
    assert a_next is not None and a_next.get_cos_object() is b.get_cos_object()
    assert a_prev is not None and a_prev.get_cos_object() is b.get_cos_object()
    assert b_next is not None and b_next.get_cos_object() is a.get_cos_object()
    assert b_prev is not None and b_prev.get_cos_object() is a.get_cos_object()


def test_append_bead_in_three_bead_chain() -> None:
    a = PDThreadBead()
    b = PDThreadBead()
    c = PDThreadBead()
    a.append_bead(b)  # a <-> b <-> a
    a.append_bead(c)  # a <-> c <-> b <-> a

    a_next = a.get_next_bead()
    c_next = c.get_next_bead()
    b_next = b.get_next_bead()
    assert a_next is not None and a_next.get_cos_object() is c.get_cos_object()
    assert c_next is not None and c_next.get_cos_object() is b.get_cos_object()
    assert b_next is not None and b_next.get_cos_object() is a.get_cos_object()


def test_page_round_trip() -> None:
    bead = PDThreadBead()
    page = PDPage()
    bead.set_page(page)
    fetched = bead.get_page()
    assert fetched is not None
    assert fetched.get_cos_object() is page.get_cos_object()


def test_page_absent_returns_none() -> None:
    bead = PDThreadBead(COSDictionary())
    assert bead.get_page() is None


def test_rectangle_round_trip() -> None:
    bead = PDThreadBead()
    rect = PDRectangle(10.0, 20.0, 110.0, 220.0)
    bead.set_rectangle(rect)
    fetched = bead.get_rectangle()
    assert fetched is not None
    assert fetched.get_lower_left_x() == 10.0
    assert fetched.get_lower_left_y() == 20.0
    assert fetched.get_upper_right_x() == 110.0
    assert fetched.get_upper_right_y() == 220.0


def test_rectangle_absent_returns_none() -> None:
    bead = PDThreadBead(COSDictionary())
    assert bead.get_rectangle() is None


def test_set_rectangle_none_removes_entry() -> None:
    bead = PDThreadBead()
    bead.set_rectangle(PDRectangle(0, 0, 10, 10))
    bead.set_rectangle(None)
    assert bead.get_rectangle() is None
    assert not bead.get_cos_object().contains_key(COSName.get_pdf_name("R"))


def test_set_page_none_removes_entry() -> None:
    bead = PDThreadBead()
    bead.set_page(PDPage())
    bead.set_page(None)
    assert bead.get_page() is None
    assert not bead.get_cos_object().contains_key(COSName.get_pdf_name("P"))


def test_set_thread_none_removes_entry() -> None:
    bead = PDThreadBead()
    bead.set_thread(PDThread())
    bead.set_thread(None)
    assert bead.get_thread() is None
    assert not bead.get_cos_object().contains_key(COSName.get_pdf_name("T"))
