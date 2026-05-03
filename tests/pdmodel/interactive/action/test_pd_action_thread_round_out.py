"""Wave 241 — round out :class:`PDActionThread` typed accessors.

The PDF 32000-1 §12.6.4.7 ``/D`` entry of a Thread action may be a
thread dictionary, an integer thread index, or a text-string thread
title. ``/B`` may be a bead dictionary or an integer bead index. The
upstream PDFBox surface returns raw COS for both; pypdfbox layers
typed and form-aware accessors on top while preserving the raw
``get_d``/``set_d`` and ``get_b``/``set_b`` parity surface.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSDictionary,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.interactive.action.pd_action_thread import PDActionThread
from pypdfbox.pdmodel.interactive.pagenavigation.pd_thread import PDThread
from pypdfbox.pdmodel.interactive.pagenavigation.pd_thread_bead import PDThreadBead

_D: COSName = COSName.D  # type: ignore[attr-defined]
_B: COSName = COSName.get_pdf_name("B")


# ---------- /D typed accessors ----------


def test_get_thread_typed_returns_pd_thread_for_dict_form() -> None:
    """A ``/D`` thread dict is wrapped as a :class:`PDThread`."""
    action = PDActionThread()
    thread = PDThread()
    action.set_thread(thread)

    typed = action.get_thread_typed()
    assert typed is not None
    assert isinstance(typed, PDThread)
    assert typed.get_cos_object() is thread.get_cos_object()


def test_get_thread_typed_returns_none_for_integer_form() -> None:
    """When ``/D`` is an integer thread index, the typed wrapper view
    yields ``None`` and callers should reach for :meth:`get_thread_index`."""
    action = PDActionThread()
    action.set_thread(3)

    assert action.get_thread_typed() is None
    assert action.get_thread_index() == 3


def test_get_thread_typed_returns_none_for_string_form() -> None:
    """When ``/D`` is a text-string thread title, the typed wrapper view
    yields ``None`` and callers should reach for :meth:`get_thread_title`."""
    action = PDActionThread()
    action.set_thread("Chapter 1")

    assert action.get_thread_typed() is None
    assert action.get_thread_title() == "Chapter 1"


def test_get_thread_typed_returns_none_when_d_absent() -> None:
    action = PDActionThread()
    assert action.get_thread_typed() is None
    assert action.get_thread_index() is None
    assert action.get_thread_title() is None


def test_get_thread_index_returns_none_for_dict_form() -> None:
    action = PDActionThread()
    action.set_thread(PDThread())
    assert action.get_thread_index() is None


def test_get_thread_title_returns_none_for_integer_form() -> None:
    action = PDActionThread()
    action.set_thread(0)
    assert action.get_thread_title() is None


def test_set_thread_with_pd_thread_stores_underlying_cos() -> None:
    """``set_thread(PDThread)`` writes the underlying ``COSDictionary``,
    not a fresh wrapper, so identity round-trips."""
    action = PDActionThread()
    thread = PDThread()
    action.set_thread(thread)

    raw = action.get_cos_object().get_dictionary_object(_D)
    assert raw is thread.get_cos_object()


def test_set_thread_with_int_writes_cos_integer() -> None:
    action = PDActionThread()
    action.set_thread(7)

    raw = action.get_cos_object().get_dictionary_object(_D)
    assert isinstance(raw, COSInteger)
    assert raw.value == 7


def test_set_thread_with_int_zero_writes_cos_integer() -> None:
    """The 0 thread index (the first thread) survives — bool guard
    must not swallow ``int(0)``."""
    action = PDActionThread()
    action.set_thread(0)

    raw = action.get_cos_object().get_dictionary_object(_D)
    assert isinstance(raw, COSInteger)
    assert raw.value == 0
    assert action.get_thread_index() == 0


def test_set_thread_with_negative_int_round_trips() -> None:
    """Out-of-range / negative integer indexes are stored verbatim;
    spec compliance is the conforming reader's responsibility."""
    action = PDActionThread()
    action.set_thread(-1)

    assert action.get_thread_index() == -1


def test_set_thread_with_string_writes_cos_string() -> None:
    action = PDActionThread()
    action.set_thread("My Article")

    raw = action.get_cos_object().get_dictionary_object(_D)
    assert isinstance(raw, COSString)
    assert raw.get_string() == "My Article"


def test_set_thread_rejects_bool() -> None:
    """``bool`` is an ``int`` subclass — guard so callers who pass
    ``True``/``False`` get a clear error rather than silently storing
    the integer values 1 / 0 as a thread index."""
    action = PDActionThread()
    with pytest.raises(TypeError):
        action.set_thread(True)
    with pytest.raises(TypeError):
        action.set_thread(False)


def test_set_thread_with_none_clears_entry() -> None:
    action = PDActionThread()
    action.set_thread(5)
    assert action.get_cos_object().contains_key(_D)

    action.set_thread(None)
    assert not action.get_cos_object().contains_key(_D)
    assert action.get_thread() is None


def test_set_thread_with_raw_cos_base_round_trips() -> None:
    """A bare ``COSBase`` (e.g. a pre-existing dict from disk) is
    stored as-is for back-compat with the historical raw-COS surface."""
    action = PDActionThread()
    raw = COSDictionary()
    action.set_thread(raw)

    assert action.get_thread() is raw
    typed = action.get_thread_typed()
    assert typed is not None
    assert typed.get_cos_object() is raw


# ---------- /B typed accessors ----------


def test_get_bead_typed_returns_pd_thread_bead_for_dict_form() -> None:
    action = PDActionThread()
    bead = PDThreadBead()
    action.set_bead(bead)

    typed = action.get_bead_typed()
    assert typed is not None
    assert isinstance(typed, PDThreadBead)
    assert typed.get_cos_object() is bead.get_cos_object()


def test_get_bead_typed_returns_none_for_integer_form() -> None:
    action = PDActionThread()
    action.set_bead(2)
    assert action.get_bead_typed() is None
    assert action.get_bead_index() == 2


def test_get_bead_typed_returns_none_when_b_absent() -> None:
    action = PDActionThread()
    assert action.get_bead_typed() is None
    assert action.get_bead_index() is None


def test_get_bead_index_returns_none_for_dict_form() -> None:
    action = PDActionThread()
    action.set_bead(PDThreadBead())
    assert action.get_bead_index() is None


def test_set_bead_with_pd_thread_bead_stores_underlying_cos() -> None:
    action = PDActionThread()
    bead = PDThreadBead()
    action.set_bead(bead)

    raw = action.get_cos_object().get_dictionary_object(_B)
    assert raw is bead.get_cos_object()


def test_set_bead_with_int_writes_cos_integer() -> None:
    action = PDActionThread()
    action.set_bead(4)

    raw = action.get_cos_object().get_dictionary_object(_B)
    assert isinstance(raw, COSInteger)
    assert raw.value == 4


def test_set_bead_with_int_zero_writes_cos_integer() -> None:
    """The first bead in a thread is index 0 — bool guard must not
    consume ``int(0)``."""
    action = PDActionThread()
    action.set_bead(0)

    assert action.get_bead_index() == 0


def test_set_bead_rejects_bool() -> None:
    action = PDActionThread()
    with pytest.raises(TypeError):
        action.set_bead(True)
    with pytest.raises(TypeError):
        action.set_bead(False)


def test_set_bead_with_none_clears_entry() -> None:
    action = PDActionThread()
    action.set_bead(2)
    assert action.get_cos_object().contains_key(_B)

    action.set_bead(None)
    assert not action.get_cos_object().contains_key(_B)
    assert action.get_bead() is None


def test_set_bead_with_raw_cos_base_round_trips() -> None:
    action = PDActionThread()
    raw = COSDictionary()
    action.set_bead(raw)

    assert action.get_bead() is raw
    typed = action.get_bead_typed()
    assert typed is not None
    assert typed.get_cos_object() is raw


# ---------- legacy raw-COS surface still works ----------


def test_get_d_set_d_still_use_raw_cos_contract() -> None:
    """``set_d`` keeps the raw-COS contract — passing an int or string
    is not auto-converted (callers who want that should use
    :meth:`set_thread`)."""
    action = PDActionThread()
    bare = COSInteger.get(9)
    action.set_d(bare)

    assert action.get_d() is bare
    assert action.get_thread_index() == 9

    action.set_d(None)
    assert action.get_d() is None


def test_get_b_set_b_still_use_raw_cos_contract() -> None:
    action = PDActionThread()
    bare = COSInteger.get(0)
    action.set_b(bare)

    assert action.get_b() is bare
    assert action.get_bead_index() == 0

    action.set_b(None)
    assert action.get_b() is None


# ---------- factory dispatch keeps wrapping the right shape ----------


def test_pd_action_thread_with_existing_dict_recovers_typed_views() -> None:
    """Wrapping a pre-existing parsed-from-disk action dict still gives
    full access to the typed views without a constructor-time rewrite."""
    raw_dict = COSDictionary()
    raw_dict.set_name("S", "Thread")
    raw_dict.set_item(_D, COSInteger.get(1))
    raw_dict.set_item(_B, COSInteger.get(0))

    action = PDActionThread(raw_dict)
    assert action.get_thread_index() == 1
    assert action.get_bead_index() == 0
    assert action.get_thread_typed() is None
    assert action.get_bead_typed() is None
