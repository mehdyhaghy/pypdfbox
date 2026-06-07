"""Deep parity tests for ``PDShading.create`` factory dispatch.

Mirrors the upstream switch statement in
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/shading/PDShading.java``
which dispatches on ``/ShadingType`` and threads through to the concrete
subclass. ``test_pd_shading.py`` covers the happy paths for ShadingType
1–7; the cases below pin the edge contracts:

  * ``None`` input → ``None`` output (not an error).
  * Non-COSDictionary inputs raise ``TypeError``.
  * Stream-required types (4–7) refuse plain dictionaries with ``OSError``.
  * Plain-dict types (1–3) accept both ``COSDictionary`` and ``COSStream``.
  * Unknown ``/ShadingType`` raises ``OSError`` (mirrors upstream
    ``IOException``).
  * Round-trip: ``create(dict)``'s ``get_cos_object()`` is the same dict.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSStream
from pypdfbox.pdmodel.graphics.shading import (
    PDShading,
    PDShadingType1,
    PDShadingType2,
    PDShadingType3,
    PDShadingType4,
    PDShadingType5,
    PDShadingType6,
    PDShadingType7,
)

_PLAIN_DICT_TYPES = {1: PDShadingType1, 2: PDShadingType2, 3: PDShadingType3}
_STREAM_TYPES = {
    4: PDShadingType4,
    5: PDShadingType5,
    6: PDShadingType6,
    7: PDShadingType7,
}


def test_create_returns_none_for_none_input():
    assert PDShading.create(None) is None


def test_create_rejects_cos_array():
    with pytest.raises(TypeError):
        PDShading.create(COSArray())  # type: ignore[arg-type]


def test_create_rejects_cos_integer():
    with pytest.raises(TypeError):
        PDShading.create(COSInteger.get(2))  # type: ignore[arg-type]


@pytest.mark.parametrize("shading_type,cls", list(_PLAIN_DICT_TYPES.items()))
def test_create_dispatches_plain_dict_types(shading_type, cls):
    d = COSDictionary()
    d.set_int("ShadingType", shading_type)
    result = PDShading.create(d)
    assert isinstance(result, cls)
    assert result.get_shading_type() == shading_type
    assert result.get_cos_object() is d


@pytest.mark.parametrize("shading_type,cls", list(_PLAIN_DICT_TYPES.items()))
def test_create_accepts_cos_stream_for_plain_dict_types(shading_type, cls):
    # Plain-dict types (1-3) also accept streams — a COSStream IS-A
    # COSDictionary in our model, so the dispatch should still succeed.
    s = COSStream()
    s.set_int("ShadingType", shading_type)
    result = PDShading.create(s)
    assert isinstance(result, cls)
    assert result.get_shading_type() == shading_type


@pytest.mark.parametrize("shading_type,cls", list(_STREAM_TYPES.items()))
def test_create_dispatches_stream_types(shading_type, cls):
    s = COSStream()
    s.set_int("ShadingType", shading_type)
    result = PDShading.create(s)
    assert isinstance(result, cls)
    assert result.get_shading_type() == shading_type
    assert result.get_cos_object() is s


@pytest.mark.parametrize("shading_type,cls", list(_STREAM_TYPES.items()))
def test_create_accepts_plain_dict_for_mesh_types(shading_type, cls):
    # Upstream PDShading.create constructs the mesh PDShadingType4..7 directly
    # from a plain COSDictionary (their constructors take a COSDictionary, not
    # a stream). The earlier stream-required guard diverged from upstream and
    # was removed in wave 1513 (ShadingPatternFuzzProbe oracle).
    d = COSDictionary()
    d.set_int("ShadingType", shading_type)
    result = PDShading.create(d)
    assert isinstance(result, cls)
    assert result.get_shading_type() == shading_type
    assert result.get_cos_object() is d


@pytest.mark.parametrize("shading_type", [0, 8, 99, -1, 100])
def test_create_rejects_invalid_shading_type(shading_type):
    d = COSDictionary()
    d.set_int("ShadingType", shading_type)
    with pytest.raises(OSError):
        PDShading.create(d)


def test_create_rejects_missing_shading_type_as_invalid():
    # Missing /ShadingType → COSDictionary.get_int defaults to 0 → invalid.
    d = COSDictionary()
    with pytest.raises(OSError):
        PDShading.create(d)


# ---------------------------------------------------------------------------
# Round-trip parity: get_shading_type on instance matches what was stored
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "shading_type",
    [1, 2, 3, 4, 5, 6, 7],
)
def test_round_trip_shading_type_via_factory(shading_type):
    d = COSDictionary() if shading_type in _PLAIN_DICT_TYPES else COSStream()
    d.set_int("ShadingType", shading_type)
    shading = PDShading.create(d)
    assert shading is not None
    assert shading.get_shading_type() == shading_type
    assert (
        shading.get_cos_object().get_int("ShadingType") == shading_type
    )


def test_factory_predicates_partition_cleanly():
    # Each created shading must answer exactly one of the family predicates
    # ``True`` — no double-counting and no orphan types.
    for shading_type in (1, 2, 3, 4, 5, 6, 7):
        d = (
            COSDictionary()
            if shading_type in _PLAIN_DICT_TYPES
            else COSStream()
        )
        d.set_int("ShadingType", shading_type)
        shading = PDShading.create(d)
        family_flags = [
            shading.is_function_based(),
            shading.is_axial(),
            shading.is_radial(),
            shading.is_mesh_based(),
        ]
        assert sum(family_flags) == 1, shading_type


def test_create_on_type1_dict_works_through_get_function_default():
    # Round-trip via factory then immediately query an inherited surface.
    # No /Function set — get_function on Type 1 returns ``None`` (not error).
    d = COSDictionary()
    d.set_int("ShadingType", 1)
    shading = PDShading.create(d)
    assert shading is not None
    assert shading.get_function() is None


# ---------------------------------------------------------------------------
# Type predicates on each dispatched instance
# ---------------------------------------------------------------------------


def test_is_function_based_only_type_1():
    for shading_type in (1, 2, 3):
        d = COSDictionary()
        d.set_int("ShadingType", shading_type)
        shading = PDShading.create(d)
        assert shading.is_function_based() is (shading_type == 1)


def test_is_axial_only_type_2():
    for shading_type in (1, 2, 3):
        d = COSDictionary()
        d.set_int("ShadingType", shading_type)
        shading = PDShading.create(d)
        assert shading.is_axial() is (shading_type == 2)


def test_is_radial_only_type_3():
    for shading_type in (1, 2, 3):
        d = COSDictionary()
        d.set_int("ShadingType", shading_type)
        shading = PDShading.create(d)
        assert shading.is_radial() is (shading_type == 3)


def test_is_mesh_based_types_4_through_7():
    for shading_type in (4, 5, 6, 7):
        s = COSStream()
        s.set_int("ShadingType", shading_type)
        shading = PDShading.create(s)
        assert shading.is_mesh_based() is True
    for shading_type in (1, 2, 3):
        d = COSDictionary()
        d.set_int("ShadingType", shading_type)
        shading = PDShading.create(d)
        assert shading.is_mesh_based() is False
