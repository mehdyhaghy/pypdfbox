from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel import SearchContext
from pypdfbox.pdmodel.pd_page import PDPage


def test_initial_state() -> None:
    ctx = SearchContext(COSDictionary())
    assert ctx.index == -1
    assert ctx.found is False


def test_visit_page_increments_index() -> None:
    ctx = SearchContext(COSDictionary())
    ctx.visit_page(COSDictionary())
    ctx.visit_page(COSDictionary())
    assert ctx.index == 1


def test_visit_page_sets_found_when_match() -> None:
    target = COSDictionary()
    target.set_name("Type", "Page")
    ctx = SearchContext(target)
    ctx.visit_page(COSDictionary())
    assert ctx.found is False
    ctx.visit_page(target)
    assert ctx.found is True


def test_accepts_pd_page() -> None:
    page = PDPage()
    ctx = SearchContext(page)
    assert ctx.searched is page.get_cos_object()


def test_invalid_type_raises() -> None:
    with pytest.raises(TypeError):
        SearchContext("not a page")  # type: ignore[arg-type]
