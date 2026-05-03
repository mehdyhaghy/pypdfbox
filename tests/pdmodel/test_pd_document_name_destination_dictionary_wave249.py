"""Wave 249 — write/iteration round-out for PDDocumentNameDestinationDictionary.

Covers ``__bool__``, ``keys()``, ``set_destination(...)`` (PDDestination /
COSArray / COSDictionary / None forms), and ``remove_destination(...)``.
Avoids re-asserting Wave 211 surface (``KEY_*``, ``has_*``, ``__iter__`` /
``items``, ``is_empty``, ``get_names``, ``__contains__``, ``__len__``).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.pd_document_name_destination_dictionary import (
    PDDocumentNameDestinationDictionary,
)


def _xyz_array() -> COSArray:
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSName.get_pdf_name("XYZ"))
    arr.add(COSFloat(0.0))
    arr.add(COSFloat(0.0))
    arr.add(COSFloat(1.0))
    return arr


# ---------- __bool__ ----------


def test_bool_is_false_for_empty_dict() -> None:
    dd = PDDocumentNameDestinationDictionary(COSDictionary())
    assert bool(dd) is False
    assert not dd


def test_bool_is_true_when_destinations_present() -> None:
    backing = COSDictionary()
    backing.set_item("home", _xyz_array())
    dd = PDDocumentNameDestinationDictionary(backing)
    assert bool(dd) is True


def test_bool_round_trip_with_set_and_remove() -> None:
    dd = PDDocumentNameDestinationDictionary()
    assert not dd
    dd.set_destination("a", _xyz_array())
    assert dd
    dd.remove_destination("a")
    assert not dd


# ---------- keys() ----------


def test_keys_yields_string_keys_in_insertion_order() -> None:
    backing = COSDictionary()
    backing.set_item("first", _xyz_array())
    backing.set_item("second", _xyz_array())
    backing.set_item("third", _xyz_array())
    dd = PDDocumentNameDestinationDictionary(backing)

    out = list(dd.keys())
    assert out == ["first", "second", "third"]
    assert all(isinstance(name, str) for name in out)


def test_keys_returns_fresh_iterator_each_call() -> None:
    backing = COSDictionary()
    backing.set_item("home", _xyz_array())
    dd = PDDocumentNameDestinationDictionary(backing)

    it1 = dd.keys()
    it2 = dd.keys()
    assert next(it1) == "home"
    # Second iterator independent — first entry still available.
    assert next(it2) == "home"


def test_keys_empty_for_empty_dict() -> None:
    dd = PDDocumentNameDestinationDictionary(COSDictionary())
    assert list(dd.keys()) == []


def test_keys_matches_items_keys_order() -> None:
    backing = COSDictionary()
    backing.set_item("alpha", _xyz_array())
    backing.set_item("beta", _xyz_array())
    dd = PDDocumentNameDestinationDictionary(backing)

    via_keys = list(dd.keys())
    via_items = [name for name, _ in dd.items()]
    assert via_keys == via_items


# ---------- set_destination(..., COSArray) ----------


def test_set_destination_stores_cos_array_directly() -> None:
    dd = PDDocumentNameDestinationDictionary()
    arr = _xyz_array()
    dd.set_destination("home", arr)
    # Stored under the key as the same array.
    assert dd.get_cos_object().get_dictionary_object("home") is arr
    # Round-trips through the resolver.
    fetched = dd.get_destination("home")
    assert isinstance(fetched, PDPageXYZDestination)


def test_set_destination_with_array_overwrites_existing() -> None:
    dd = PDDocumentNameDestinationDictionary()
    dd.set_destination("home", _xyz_array())
    new_arr = _xyz_array()
    dd.set_destination("home", new_arr)
    assert dd.get_cos_object().get_dictionary_object("home") is new_arr
    assert len(dd) == 1


# ---------- set_destination(..., COSDictionary with /D) ----------


def test_set_destination_stores_dict_with_d_form() -> None:
    """{/D <array>} wrapper round-trips through get_destination."""
    dd = PDDocumentNameDestinationDictionary()
    inner_arr = _xyz_array()
    wrapper = COSDictionary()
    wrapper.set_item("D", inner_arr)
    dd.set_destination("intro", wrapper)

    assert dd.get_cos_object().get_dictionary_object("intro") is wrapper
    fetched = dd.get_destination("intro")
    assert isinstance(fetched, PDPageXYZDestination)


# ---------- set_destination(..., PDDestination) ----------


def test_set_destination_with_pd_destination_unwraps_cos() -> None:
    dd = PDDocumentNameDestinationDictionary()
    dest = PDPageXYZDestination()
    dest.set_page_number(3)

    dd.set_destination("chapter3", dest)

    # The COS payload from the wrapper is what got stored.
    stored = dd.get_cos_object().get_dictionary_object("chapter3")
    assert stored is dest.get_cos_object()
    # Round-trip: resolver yields a PDPageXYZDestination with the same array.
    fetched = dd.get_destination("chapter3")
    assert isinstance(fetched, PDPageXYZDestination)
    assert fetched.get_cos_object() is dest.get_cos_object()
    assert fetched.get_page_number() == 3


def test_set_destination_pd_destination_round_trips_via_iter() -> None:
    """Newly added PDDestination shows up under iteration too."""
    dd = PDDocumentNameDestinationDictionary()
    dest = PDPageXYZDestination()
    dest.set_page_number(5)
    dd.set_destination("end", dest)

    pairs = dict(dd.items())
    assert "end" in pairs
    assert isinstance(pairs["end"], PDPageXYZDestination)
    assert pairs["end"].get_page_number() == 5


# ---------- set_destination(..., None) ----------


def test_set_destination_none_removes_entry() -> None:
    dd = PDDocumentNameDestinationDictionary()
    dd.set_destination("home", _xyz_array())
    assert "home" in dd

    dd.set_destination("home", None)

    assert "home" not in dd
    assert dd.get_destination("home") is None
    assert dd.get_cos_object().get_dictionary_object("home") is None


def test_set_destination_none_for_missing_key_is_noop() -> None:
    dd = PDDocumentNameDestinationDictionary()
    # Should not raise.
    dd.set_destination("never-there", None)
    assert len(dd) == 0


# ---------- set_destination type-checking ----------


class _BogusDestination:
    """Quacks like a PDDestination but yields a non-COS payload."""

    def get_cos_object(self) -> object:
        return "not a cos value"


def test_set_destination_rejects_payload_that_is_not_array_or_dict() -> None:
    dd = PDDocumentNameDestinationDictionary()
    with pytest.raises(TypeError):
        dd.set_destination("oops", _BogusDestination())  # type: ignore[arg-type]


# ---------- remove_destination ----------


def test_remove_destination_drops_entry() -> None:
    dd = PDDocumentNameDestinationDictionary()
    dd.set_destination("a", _xyz_array())
    dd.set_destination("b", _xyz_array())
    assert len(dd) == 2

    dd.remove_destination("a")

    assert len(dd) == 1
    assert "a" not in dd
    assert "b" in dd


def test_remove_destination_missing_key_is_noop() -> None:
    dd = PDDocumentNameDestinationDictionary()
    # Should not raise.
    dd.remove_destination("missing")
    assert len(dd) == 0


def test_remove_destination_round_trips_with_set_destination() -> None:
    dd = PDDocumentNameDestinationDictionary()
    dest = PDPageXYZDestination()
    dest.set_page_number(0)
    dd.set_destination("home", dest)
    assert dd.get_destination("home") is not None

    dd.remove_destination("home")
    assert dd.get_destination("home") is None
    assert dd.is_empty() is True
