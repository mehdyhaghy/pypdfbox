"""Wave 222 parity round-out tests for ``PDViewportDictionary``.

Covers the small surface added to close gaps with upstream PDFBox
``PDViewportDictionary``:

- ``get_name`` accepts a ``COSString`` value at ``/Name`` (parity with
  upstream ``getNameAsString`` which handles both ``COSName`` and
  ``COSString``).
- ``has_b_box`` / ``has_bbox`` / ``has_name`` / ``has_measure``
  predicates: existence checks that don't materialize wrappers.
- ``is_named`` predicate: case-sensitive ``/Name`` comparison.
- ``__repr__``: cheap, COS-layer-only debug formatting.
- ``TYPE`` class constant exposed and exercised through ``get_type``.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.measurement import PDViewportDictionary
from pypdfbox.pdmodel.interactive.measurement.pd_measure_dictionary import (
    PDMeasureDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_BBOX = COSName.get_pdf_name("BBox")
_NAME = COSName.get_pdf_name("Name")
_MEASURE = COSName.get_pdf_name("Measure")


# ----------------------------------------------------------------- /Name parity


def test_get_name_reads_cos_string_value() -> None:
    # Upstream ``getNameAsString`` returns the value of a ``COSString``
    # stored at ``/Name``; a plain ``get_name()`` only handles ``COSName``,
    # so this exercises the parity fix.
    raw = COSDictionary()
    raw.set_item(_NAME, COSString("vp-from-string"))
    vp = PDViewportDictionary(raw)
    assert vp.get_name() == "vp-from-string"


def test_get_name_reads_cos_name_value() -> None:
    # The other half of upstream's ``getNameAsString`` contract — a
    # ``COSName`` value still resolves to its plain string.
    vp = PDViewportDictionary()
    vp.set_name("vp-from-name")
    # Internally ``set_name`` stores a ``COSName`` (verified by the
    # bbox_alias test module); this just confirms that path still reads.
    assert vp.get_name() == "vp-from-name"


def test_get_name_returns_none_for_unrelated_value_type() -> None:
    # A non-name, non-string value at ``/Name`` (e.g. an integer from a
    # broken producer) is treated as absent — matches upstream's default
    # of ``null`` when the value is neither ``COSName`` nor ``COSString``.
    raw = COSDictionary()
    raw.set_item(_NAME, COSInteger.get(42))
    vp = PDViewportDictionary(raw)
    assert vp.get_name() is None


def test_get_name_returns_none_when_absent() -> None:
    vp = PDViewportDictionary()
    assert vp.get_name() is None


# ----------------------------------------------------------------- predicates


def test_has_b_box_predicate_round_trips() -> None:
    vp = PDViewportDictionary()
    assert vp.has_b_box() is False
    assert vp.has_bbox() is False  # acronym alias

    vp.set_b_box(PDRectangle(0.0, 0.0, 100.0, 200.0))
    assert vp.has_b_box() is True
    assert vp.has_bbox() is True

    vp.set_b_box(None)
    assert vp.has_b_box() is False
    assert vp.has_bbox() is False


def test_has_name_predicate_round_trips() -> None:
    vp = PDViewportDictionary()
    assert vp.has_name() is False

    vp.set_name("alpha")
    assert vp.has_name() is True

    vp.set_name(None)
    assert vp.has_name() is False


def test_has_measure_predicate_round_trips() -> None:
    vp = PDViewportDictionary()
    assert vp.has_measure() is False

    vp.set_measure(PDMeasureDictionary())
    assert vp.has_measure() is True

    vp.set_measure(None)
    assert vp.has_measure() is False


def test_predicates_are_pure_existence_checks_no_resolution() -> None:
    # Even if the slot holds a value of the wrong type, ``has_*``
    # predicates report "present" — they are pure ``contains_key`` checks
    # that should not eagerly try to wrap the entry.
    raw = COSDictionary()
    raw.set_item(_BBOX, COSInteger.get(1))
    raw.set_item(_MEASURE, COSInteger.get(2))
    vp = PDViewportDictionary(raw)
    assert vp.has_b_box() is True
    assert vp.has_measure() is True
    # And the typed accessors still reject the bogus value cleanly.
    assert vp.get_b_box() is None
    assert vp.get_measure() is None


# ----------------------------------------------------------------- is_named


def test_is_named_matches_exactly() -> None:
    vp = PDViewportDictionary()
    vp.set_name("Alpha")
    assert vp.is_named("Alpha") is True


def test_is_named_is_case_sensitive() -> None:
    vp = PDViewportDictionary()
    vp.set_name("Alpha")
    assert vp.is_named("alpha") is False
    assert vp.is_named("ALPHA") is False


def test_is_named_returns_false_when_absent() -> None:
    vp = PDViewportDictionary()
    assert vp.is_named("Alpha") is False
    # ``is_named("")`` is also ``False`` because the entry is absent —
    # ``get_name()`` returns ``None`` and ``None == ""`` is ``False``.
    assert vp.is_named("") is False


def test_is_named_works_with_cos_string_storage() -> None:
    # The /Name slot stored as COSString (upstream parity case) — the
    # predicate dispatches through ``get_name`` so it works for both
    # storage flavors.
    raw = COSDictionary()
    raw.set_item(_NAME, COSString("Beta"))
    vp = PDViewportDictionary(raw)
    assert vp.is_named("Beta") is True
    assert vp.is_named("Alpha") is False


# ----------------------------------------------------------------- __repr__


def test_repr_for_empty_viewport() -> None:
    vp = PDViewportDictionary()
    text = repr(vp)
    assert text.startswith("PDViewportDictionary(")
    assert "name=None" in text
    assert "bbox=unset" in text
    assert "measure=unset" in text


def test_repr_for_populated_viewport() -> None:
    vp = PDViewportDictionary()
    vp.set_name("zone-1")
    vp.set_b_box(PDRectangle(0.0, 0.0, 50.0, 100.0))
    vp.set_measure(PDMeasureDictionary())
    text = repr(vp)
    assert "name='zone-1'" in text
    assert "bbox=set" in text
    assert "measure=set" in text


def test_repr_does_not_construct_pd_wrappers() -> None:
    # ``__repr__`` must stay cheap — touching only the COS layer. We
    # verify that even when the slots hold values that *would* fail the
    # typed accessors (``isinstance`` mismatch), ``repr`` still succeeds.
    raw = COSDictionary()
    raw.set_item(_BBOX, COSInteger.get(1))
    raw.set_item(_MEASURE, COSInteger.get(2))
    vp = PDViewportDictionary(raw)
    text = repr(vp)
    # Both slots are reported as present — the repr never tries to
    # resolve them through ``PDRectangle.from_cos_array`` / wrapper.
    assert "bbox=set" in text
    assert "measure=set" in text


# ----------------------------------------------------------------- TYPE constant


def test_type_constant_matches_upstream() -> None:
    # The class constant is exposed and equal to upstream's literal.
    assert PDViewportDictionary.TYPE == "Viewport"


def test_get_type_is_class_constant_invariant() -> None:
    # ``get_type`` is hard-wired to the class constant — independent of
    # what's actually stored at ``/Type``. Mirrors upstream's
    # ``return TYPE;`` body which ignores the dict contents.
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("Type"), "SomethingElse")
    vp = PDViewportDictionary(raw)
    assert vp.get_type() == "Viewport"
