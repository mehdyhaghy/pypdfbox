from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel import PageIterator


def _page(name: str = "P") -> COSDictionary:
    d = COSDictionary()
    d.set_name("Type", "Page")
    d.set_name("Name", name)
    return d


def _node(*kids: COSDictionary) -> COSDictionary:
    n = COSDictionary()
    n.set_name("Type", "Pages")
    arr = COSArray()
    for kid in kids:
        arr.add(kid)
    n.set_item("Kids", arr)
    return n


def test_iterates_flat_pages() -> None:
    root = _node(_page("A"), _page("B"))
    it = PageIterator(root)
    pages = list(it)
    assert len(pages) == 2


def test_iterates_nested_pages() -> None:
    inner = _node(_page("C"), _page("D"))
    root = _node(_page("A"), inner, _page("E"))
    it = PageIterator(root)
    pages = list(it)
    assert len(pages) == 4


def test_has_next_method() -> None:
    root = _node(_page("A"))
    it = PageIterator(root)
    assert it.has_next()
    _ = it.next()
    assert not it.has_next()


def test_next_raises_stop_iteration_when_exhausted() -> None:
    root = _node()
    it = PageIterator(root)
    with pytest.raises(StopIteration):
        it.next()


def test_remove_unsupported() -> None:
    it = PageIterator(_node())
    with pytest.raises(NotImplementedError):
        it.remove()


def test_circular_kids_avoided() -> None:
    inner = _node(_page("X"))
    # Make inner reference itself via /Kids — should be deduped.
    cycle_root = _node(inner)
    inner.get_dictionary_object(COSName.get_pdf_name("Kids")).add(inner)
    pages = list(PageIterator(cycle_root))
    assert len(pages) == 1
