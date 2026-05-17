"""Coverage-boost tests for the public ``FieldIterator`` alias (wave 1332).

The class is a thin subclass of ``_FieldIterator`` that surfaces the
upstream ``enqueueKids`` method name. The previously uncovered line was
the body of :meth:`FieldIterator.enqueue_kids`; these tests exercise it
both for a terminal field (no descendants pushed beyond ``node`` itself)
and a non-terminal field (push ``node`` then walk ``/Kids``).
"""

from __future__ import annotations

from pypdfbox.pdmodel.interactive.form import (
    PDAcroForm,
    PDFieldStub,
    PDNonTerminalField,
)
from pypdfbox.pdmodel.interactive.form.field_iterator import FieldIterator


def test_enqueue_kids_appends_terminal_field_only() -> None:
    form = PDAcroForm()
    leaf = PDFieldStub(form)
    leaf.set_partial_name("leaf")
    form.set_fields([leaf])

    it = FieldIterator(form)
    # Drain the initial leaf so the queue starts empty.
    assert next(it).get_fully_qualified_name() == "leaf"
    assert it.has_next() is False

    # A second terminal field, re-enqueued through the public alias,
    # should land in the queue verbatim — no descendants to walk.
    other = PDFieldStub(form)
    other.set_partial_name("other")
    it.enqueue_kids(other)

    assert it.has_next() is True
    drained = list(it)
    assert [f.get_fully_qualified_name() for f in drained] == ["other"]


def test_enqueue_kids_walks_non_terminal_descendants() -> None:
    form = PDAcroForm()
    # Build a parent/child cluster but DON'T attach it to the form, so
    # the iterator starts empty and the only walk performed comes from
    # the public ``enqueue_kids`` call below.
    parent = PDNonTerminalField(form)
    parent.set_partial_name("parent")
    a = PDFieldStub(form)
    a.set_partial_name("a")
    b = PDFieldStub(form)
    b.set_partial_name("b")
    parent.set_children([a, b])

    it = FieldIterator(form)
    assert it.has_next() is False

    it.enqueue_kids(parent)

    drained = [f.get_fully_qualified_name() for f in it]
    # Parent first, then each kid in /Kids order — same shape as the
    # underlying ``_FieldIterator._enqueue_kids`` worker.
    assert drained == ["parent", "parent.a", "parent.b"]
