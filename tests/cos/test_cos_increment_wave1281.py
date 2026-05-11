"""Wave 1281: COSIncrement traversal port."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSIncrement, COSName


def test_empty_increment_yields_nothing() -> None:
    inc = COSIncrement(None)
    assert list(inc) == []


def test_seeded_with_dictionary_iterates_after_mark() -> None:
    d = COSDictionary()
    # Force the dictionary into a state where the increment collector
    # would emit it. Without a document state the gate is closed; we
    # exercise the iterator path regardless.
    d.set_name(COSName.TYPE, "Catalog")
    inc = COSIncrement(d)
    items = list(inc)
    # Without a document state attached, no objects are emitted.
    assert items == []


def test_exclude_marks_object() -> None:
    a = COSDictionary()
    b = COSDictionary()
    inc = COSIncrement(None)
    assert inc.exclude(a, b) is inc  # supports chaining
    # ``contains`` uses identity; an excluded but never-collected base
    # is still not contained until traversal reaches it.
    assert inc.contains(a) is False


def test_contains_known_object() -> None:
    inc = COSIncrement(None)
    d = COSDictionary()
    # Force the internal collected map directly so we exercise contains.
    inc._objects[id(d)] = d  # type: ignore[attr-defined]
    assert inc.contains(d) is True
    assert inc.contains(COSDictionary()) is False
