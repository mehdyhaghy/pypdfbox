from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.measurement import PDViewportDictionary
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_BBOX = COSName.get_pdf_name("BBox")
_NAME = COSName.get_pdf_name("Name")
_MEASURE = COSName.get_pdf_name("Measure")


def test_default_construction_is_empty() -> None:
    vp = PDViewportDictionary()
    assert isinstance(vp.get_cos_object(), COSDictionary)
    assert vp.get_cos_object().is_empty()
    assert vp.get_type() == "Viewport" == PDViewportDictionary.TYPE
    assert vp.get_b_box() is None
    assert vp.get_name() is None
    assert vp.get_measure() is None


def test_wraps_existing_dictionary() -> None:
    raw = COSDictionary()
    vp = PDViewportDictionary(raw)
    assert vp.get_cos_object() is raw


def test_b_box_round_trip() -> None:
    vp = PDViewportDictionary()
    rect = PDRectangle(10.0, 20.0, 110.0, 220.0)
    vp.set_b_box(rect)

    # Underlying dictionary is updated.
    arr = vp.get_cos_object().get_dictionary_object(_BBOX)
    assert arr is not None

    resolved = vp.get_b_box()
    assert resolved is not None
    assert resolved.get_lower_left_x() == 10.0
    assert resolved.get_lower_left_y() == 20.0
    assert resolved.get_upper_right_x() == 110.0
    assert resolved.get_upper_right_y() == 220.0

    vp.set_b_box(None)
    assert vp.get_b_box() is None
    assert not vp.get_cos_object().contains_key(_BBOX)


def test_name_round_trip() -> None:
    vp = PDViewportDictionary()
    vp.set_name("vp-1")
    assert vp.get_name() == "vp-1"
    assert vp.get_cos_object().get_name(_NAME) == "vp-1"

    vp.set_name(None)
    assert vp.get_name() is None
    assert not vp.get_cos_object().contains_key(_NAME)


def test_measure_round_trip() -> None:
    # Use the actual PDMeasureDictionary via the lazy import path; if the
    # collaborating port is not yet available, fall back to a minimal stub
    # that satisfies ``get_cos_object()`` so the round-trip is still
    # exercised against a real ``COSDictionary``.
    try:
        from pypdfbox.pdmodel.interactive.measurement.pd_measure_dictionary import (
            PDMeasureDictionary,
        )

        measure = PDMeasureDictionary()
    except ImportError:
        class _Stub:
            def __init__(self) -> None:
                self._d = COSDictionary()

            def get_cos_object(self) -> COSDictionary:
                return self._d

        measure = _Stub()  # type: ignore[assignment]

    vp = PDViewportDictionary()
    vp.set_measure(measure)  # type: ignore[arg-type]

    assert vp.get_cos_object().contains_key(_MEASURE)
    # The stored entry is the measure's underlying dictionary.
    assert (
        vp.get_cos_object().get_dictionary_object(_MEASURE)
        is measure.get_cos_object()
    )

    # Round-trip ``get_measure`` only when the real port is present —
    # otherwise the constructor signature differs from the stub.
    try:
        from pypdfbox.pdmodel.interactive.measurement.pd_measure_dictionary import (
            PDMeasureDictionary as _PDMD,
        )

        resolved = vp.get_measure()
        assert isinstance(resolved, _PDMD)
        assert resolved.get_cos_object() is measure.get_cos_object()
    except ImportError:
        pass

    vp.set_measure(None)
    assert vp.get_measure() is None
    assert not vp.get_cos_object().contains_key(_MEASURE)
