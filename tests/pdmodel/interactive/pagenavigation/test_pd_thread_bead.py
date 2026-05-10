from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.pagenavigation import (
    PDThread,
    PDThreadBead,
)
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


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


def test_iter_beads_single_bead_yields_self_only() -> None:
    bead = PDThreadBead()
    walked = list(bead.iter_beads())
    assert len(walked) == 1
    assert walked[0].get_cos_object() is bead.get_cos_object()


def test_iter_beads_three_bead_chain_walks_in_order() -> None:
    a = PDThreadBead()
    b = PDThreadBead()
    c = PDThreadBead()
    a.append_bead(b)  # a <-> b <-> a
    b.append_bead(c)  # a <-> b <-> c <-> a

    walked = list(a.iter_beads())
    assert [w.get_cos_object() for w in walked] == [
        a.get_cos_object(),
        b.get_cos_object(),
        c.get_cos_object(),
    ]


def test_dunder_iter_walks_chain() -> None:
    a = PDThreadBead()
    b = PDThreadBead()
    a.append_bead(b)
    walked = [w.get_cos_object() for w in a]
    assert walked == [a.get_cos_object(), b.get_cos_object()]


def test_iter_beads_terminates_on_missing_next() -> None:
    # A bead built from a bare dictionary has no /N — iteration must yield
    # exactly the starting bead and stop, not raise.
    bead = PDThreadBead(COSDictionary())
    walked = list(bead.iter_beads())
    assert len(walked) == 1
    assert walked[0].get_cos_object() is bead.get_cos_object()


def test_iter_beads_terminates_on_malformed_self_loop() -> None:
    # A bead that points /N at a different bead which then points back at
    # itself (not at the starting bead) is malformed but the iterator must
    # still terminate via the visited-set guard.
    a = PDThreadBead()
    b = PDThreadBead()
    a.set_next_bead(b)
    b.set_next_bead(b)  # b points to itself, never back to a
    walked = list(a.iter_beads())
    # a is yielded, b is yielded, then b would be re-yielded — bail.
    assert len(walked) == 2
    assert walked[0].get_cos_object() is a.get_cos_object()
    assert walked[1].get_cos_object() is b.get_cos_object()


# ---------- equality / hashing parity with PDDictionaryWrapper ----------


def test_bead_eq_uses_underlying_dictionary_identity() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Bead"))
    a = PDThreadBead(raw)
    b = PDThreadBead(raw)
    assert a == b
    assert a is not b


def test_bead_eq_distinct_dictionaries_are_not_equal() -> None:
    a = PDThreadBead()
    b = PDThreadBead()
    assert a != b


def test_bead_eq_returns_not_implemented_for_other_types() -> None:
    bead = PDThreadBead()
    assert (bead == "not a bead") is False
    assert (bead == 42) is False


def test_bead_hash_matches_equality_contract() -> None:
    raw = COSDictionary()
    a = PDThreadBead(raw)
    b = PDThreadBead(raw)
    assert a == b
    assert hash(a) == hash(b)
    bucket: dict[PDThreadBead, str] = {a: "first"}
    assert bucket[b] == "first"


def test_get_next_bead_uses_eq_across_fresh_wrappers() -> None:
    # ``get_next_bead`` returns a fresh wrapper each call. With the new
    # equality contract those wrappers must compare equal.
    a = PDThreadBead()
    b = PDThreadBead()
    a.append_bead(b)
    first = a.get_next_bead()
    second = a.get_next_bead()
    assert first is not second
    assert first == second
    assert first == b


# ---------- predicate helpers ----------


def test_is_first_bead_true_when_thread_set() -> None:
    bead = PDThreadBead()
    bead.set_thread(PDThread())
    assert bead.is_first_bead() is True


def test_is_first_bead_false_on_default_bead() -> None:
    # A freshly-constructed bead has no /T entry yet — only the first bead
    # of an article is required to carry one.
    bead = PDThreadBead()
    assert bead.is_first_bead() is False


def test_is_first_bead_false_after_thread_cleared() -> None:
    bead = PDThreadBead()
    bead.set_thread(PDThread())
    bead.set_thread(None)
    assert bead.is_first_bead() is False


def test_set_first_bead_makes_bead_first_bead() -> None:
    # Side-effect from ``PDThread.set_first_bead`` should propagate so the
    # ``is_first_bead`` predicate reports True.
    thread = PDThread()
    bead = PDThreadBead()
    assert bead.is_first_bead() is False
    thread.set_first_bead(bead)
    assert bead.is_first_bead() is True


# ---------- is_singleton ----------


def test_is_singleton_true_on_default_bead() -> None:
    bead = PDThreadBead()
    assert bead.is_singleton() is True


def test_is_singleton_false_after_append() -> None:
    a = PDThreadBead()
    b = PDThreadBead()
    a.append_bead(b)
    assert a.is_singleton() is False
    assert b.is_singleton() is False


def test_is_singleton_false_when_only_next_points_self() -> None:
    # Only true singletons (both /N and /V referencing self) qualify; a bead
    # whose /N is self but /V references another bead is *not* a singleton.
    a = PDThreadBead()
    other = PDThreadBead()
    a.set_previous_bead(other)
    assert a.is_singleton() is False


def test_is_singleton_false_on_bead_without_links() -> None:
    # A bead built from a bare dictionary has neither /N nor /V — it is not
    # a singleton in the upstream sense (which requires self-references).
    bead = PDThreadBead(COSDictionary())
    assert bead.is_singleton() is False


# ---------- count_beads ----------


def test_count_beads_singleton_returns_one() -> None:
    bead = PDThreadBead()
    assert bead.count_beads() == 1


def test_count_beads_two_bead_chain() -> None:
    a = PDThreadBead()
    b = PDThreadBead()
    a.append_bead(b)
    assert a.count_beads() == 2
    # Counting from b walks b -> a and stops at the start-id.
    assert b.count_beads() == 2


def test_count_beads_three_bead_chain() -> None:
    a = PDThreadBead()
    b = PDThreadBead()
    c = PDThreadBead()
    a.append_bead(b)
    b.append_bead(c)  # a <-> b <-> c <-> a
    assert a.count_beads() == 3


def test_count_beads_terminates_on_malformed_chain() -> None:
    # The visited-set guard inside iter_beads keeps count_beads finite even
    # when /N points at an already-visited bead.
    a = PDThreadBead()
    b = PDThreadBead()
    a.set_next_bead(b)
    b.set_next_bead(b)
    assert a.count_beads() == 2


def test_count_beads_terminates_on_missing_next() -> None:
    # A bead built from a bare dictionary has no /N; count_beads must yield 1.
    bead = PDThreadBead(COSDictionary())
    assert bead.count_beads() == 1
