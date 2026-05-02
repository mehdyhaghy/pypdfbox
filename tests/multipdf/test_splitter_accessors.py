"""Wave 178 — Splitter typed accessors / predicates / fluent setters.

Covers the new surface added to ``pypdfbox.multipdf.Splitter``:

- typed getters (``get_split_at_page``, ``get_start_page``,
  ``get_end_page``);
- ``has_*`` predicate helpers that distinguish "untouched defaults"
  from "explicitly set";
- class-level constants (``DEFAULT_SPLIT_LENGTH``, ``START_PAGE_DEFAULT``,
  ``END_PAGE_DEFAULT``);
- fluent setters that return ``self`` so configuration calls can be
  chained.
"""

from __future__ import annotations

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.multipdf import Splitter


def _make_doc(n_pages: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(n_pages):
        doc.add_page(PDPage())
    return doc


# ---------- class-level constants ----------


def test_default_split_length_constant() -> None:
    assert Splitter.DEFAULT_SPLIT_LENGTH == 1


def test_start_page_default_constant_is_int_min() -> None:
    """Mirrors upstream's ``Integer.MIN_VALUE`` sentinel."""
    assert Splitter.START_PAGE_DEFAULT == -(2**31)


def test_end_page_default_constant_is_int_max() -> None:
    """Mirrors upstream's ``Integer.MAX_VALUE`` sentinel."""
    assert Splitter.END_PAGE_DEFAULT == 2**31 - 1


def test_constants_are_class_attributes_not_instance_attributes() -> None:
    """Constants live on the class so subclasses / tests can refer to
    them without instantiating."""
    assert "DEFAULT_SPLIT_LENGTH" in Splitter.__dict__
    assert "START_PAGE_DEFAULT" in Splitter.__dict__
    assert "END_PAGE_DEFAULT" in Splitter.__dict__


# ---------- typed getters ----------


def test_get_split_at_page_returns_default_when_unset() -> None:
    splitter = Splitter()
    assert splitter.get_split_at_page() == Splitter.DEFAULT_SPLIT_LENGTH


def test_get_split_at_page_round_trips() -> None:
    splitter = Splitter()
    splitter.set_split_at_page(7)
    assert splitter.get_split_at_page() == 7


def test_get_start_page_returns_default_when_unset() -> None:
    splitter = Splitter()
    assert splitter.get_start_page() == Splitter.START_PAGE_DEFAULT


def test_get_start_page_round_trips() -> None:
    splitter = Splitter()
    splitter.set_start_page(3)
    assert splitter.get_start_page() == 3


def test_get_end_page_returns_default_when_unset() -> None:
    splitter = Splitter()
    assert splitter.get_end_page() == Splitter.END_PAGE_DEFAULT


def test_get_end_page_round_trips() -> None:
    splitter = Splitter()
    splitter.set_start_page(2)
    splitter.set_end_page(7)
    assert splitter.get_end_page() == 7


# ---------- has_* predicates ----------


def test_has_start_page_false_by_default() -> None:
    assert not Splitter().has_start_page()


def test_has_start_page_true_after_explicit_set() -> None:
    splitter = Splitter()
    splitter.set_start_page(2)
    assert splitter.has_start_page()


def test_has_end_page_false_by_default() -> None:
    assert not Splitter().has_end_page()


def test_has_end_page_true_after_explicit_set() -> None:
    splitter = Splitter()
    splitter.set_end_page(5)
    assert splitter.has_end_page()


def test_has_predicates_independent() -> None:
    """Setting one bound must not flip the other's predicate."""
    splitter = Splitter()
    splitter.set_start_page(2)
    assert splitter.has_start_page()
    assert not splitter.has_end_page()
    splitter.set_end_page(7)
    assert splitter.has_start_page()
    assert splitter.has_end_page()


def test_has_stream_cache_create_function_round_trip() -> None:
    splitter = Splitter()
    assert not splitter.has_stream_cache_create_function()

    def factory():  # noqa: ANN202
        return None

    splitter.set_stream_cache_create_function(factory)
    assert splitter.has_stream_cache_create_function()
    splitter.set_stream_cache_create_function(None)
    assert not splitter.has_stream_cache_create_function()


def test_has_memory_usage_setting_round_trip() -> None:
    from pypdfbox.io import MemoryUsageSetting

    splitter = Splitter()
    assert not splitter.has_memory_usage_setting()
    splitter.set_memory_usage_setting(MemoryUsageSetting.setup_main_memory_only())
    assert splitter.has_memory_usage_setting()
    splitter.set_memory_usage_setting(None)
    assert not splitter.has_memory_usage_setting()


# ---------- fluent setters ----------


def test_set_split_at_page_returns_self() -> None:
    splitter = Splitter()
    assert splitter.set_split_at_page(2) is splitter


def test_set_split_returns_self() -> None:
    splitter = Splitter()
    assert splitter.set_split(2) is splitter


def test_set_start_page_returns_self() -> None:
    splitter = Splitter()
    assert splitter.set_start_page(1) is splitter


def test_set_end_page_returns_self() -> None:
    splitter = Splitter()
    assert splitter.set_end_page(5) is splitter


def test_set_stream_cache_create_function_returns_self() -> None:
    splitter = Splitter()
    assert splitter.set_stream_cache_create_function(None) is splitter


def test_set_memory_usage_setting_returns_self() -> None:
    splitter = Splitter()
    assert splitter.set_memory_usage_setting(None) is splitter


def test_fluent_chain_configures_full_run() -> None:
    """End-to-end: chained config produces a working split."""
    src = _make_doc(8)
    chunks = (
        Splitter()
        .set_start_page(2)
        .set_end_page(7)
        .set_split_at_page(3)
        .split(src)
    )
    # 6 pages in [2..7], chunks of 3 → 2 docs of 3 pages each.
    assert [c.get_number_of_pages() for c in chunks] == [3, 3]
    for c in chunks:
        c.close()
    src.close()


# ---------- failing setters do not mutate state ----------


def test_set_split_at_page_zero_keeps_previous_value() -> None:
    splitter = Splitter()
    splitter.set_split_at_page(4)
    with pytest.raises(ValueError):
        splitter.set_split_at_page(0)
    assert splitter.get_split_at_page() == 4


def test_set_start_page_zero_keeps_previous_value() -> None:
    splitter = Splitter()
    splitter.set_start_page(3)
    with pytest.raises(ValueError):
        splitter.set_start_page(0)
    assert splitter.get_start_page() == 3
    assert splitter.has_start_page()


def test_set_end_page_below_start_keeps_previous_value() -> None:
    splitter = Splitter()
    splitter.set_start_page(5)
    splitter.set_end_page(10)
    with pytest.raises(ValueError, match="smaller than startPage"):
        splitter.set_end_page(3)
    assert splitter.get_end_page() == 10


def test_set_end_page_zero_keeps_previous_value() -> None:
    splitter = Splitter()
    splitter.set_end_page(7)
    with pytest.raises(ValueError):
        splitter.set_end_page(0)
    assert splitter.get_end_page() == 7
    assert splitter.has_end_page()


# ---------- subclass still sees constants ----------


def test_subclass_inherits_constants() -> None:
    class MySplitter(Splitter):
        pass

    assert MySplitter.DEFAULT_SPLIT_LENGTH == 1
    assert MySplitter.START_PAGE_DEFAULT == Splitter.START_PAGE_DEFAULT
    assert MySplitter.END_PAGE_DEFAULT == Splitter.END_PAGE_DEFAULT


def test_subclass_default_predicates_match() -> None:
    class MySplitter(Splitter):
        pass

    s = MySplitter()
    assert not s.has_start_page()
    assert not s.has_end_page()
    assert s.get_split_at_page() == Splitter.DEFAULT_SPLIT_LENGTH
