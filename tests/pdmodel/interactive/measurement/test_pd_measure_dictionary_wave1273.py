"""Wave 1273 round-out: ``PDMeasureDictionary.set_subtype()`` public hook."""

from __future__ import annotations

from pypdfbox.pdmodel.interactive.measurement.pd_measure_dictionary import (
    PDMeasureDictionary,
)


def test_set_subtype_changes_value() -> None:
    measure = PDMeasureDictionary()
    # Default subtype defaults to ``"RL"`` per :meth:`get_subtype`.
    assert measure.get_subtype() == "RL"
    measure.set_subtype("GEO")
    assert measure.get_subtype() == "GEO"


def test_set_subtype_writes_name_entry() -> None:
    measure = PDMeasureDictionary()
    measure.set_subtype("RL")
    cos = measure.get_cos_object()
    assert cos.get_name("Subtype") == "RL"


def test_set_subtype_public_matches_protected_hook() -> None:
    a = PDMeasureDictionary()
    b = PDMeasureDictionary()
    a.set_subtype("CUSTOM")
    b._set_subtype("CUSTOM")
    assert a.get_subtype() == b.get_subtype() == "CUSTOM"
