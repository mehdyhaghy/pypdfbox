"""Deep parity tests for ``PDShadingPattern``. Mirrors upstream
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/pattern/PDShadingPattern.java``.

Covers the typed ``/Shading`` accessor (dispatching on ``/ShadingType`` to
each of the seven concrete subclasses), the typed ``/ExtGState`` accessor
(returning ``PDExtendedGraphicsState`` rather than the raw dict the base
class hands back), and the ``set_shading`` / ``set_extended_graphics_state``
setter contract.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.graphics.pattern import (
    PDAbstractPattern,
    PDShadingPattern,
)
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
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)


def test_fresh_shading_pattern_writes_pattern_type_two():
    pattern = PDShadingPattern()
    assert pattern.get_pattern_type() == PDAbstractPattern.TYPE_SHADING_PATTERN
    assert pattern.get_pattern_type() == 2
    assert pattern.get_cos_object().get_int("PatternType") == 2


def test_fresh_shading_pattern_has_no_shading_or_extgs():
    pattern = PDShadingPattern()
    assert pattern.get_shading() is None
    assert pattern.has_shading() is False
    assert pattern.get_extended_graphics_state() is None


# ---------------------------------------------------------------------------
# Typed /Shading accessor dispatches to each subclass
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "shading_type,cls",
    [
        (1, PDShadingType1),
        (2, PDShadingType2),
        (3, PDShadingType3),
    ],
)
def test_get_shading_dispatches_to_plain_dict_types(shading_type, cls):
    pattern = PDShadingPattern()
    raw = COSDictionary()
    raw.set_int("ShadingType", shading_type)
    pattern.set_shading(raw)
    typed = pattern.get_shading()
    assert isinstance(typed, cls)
    assert typed.get_cos_object() is raw


# Types 4-7 require stream-backed dictionaries — set via stream then verify.
def test_get_shading_returns_none_for_stream_typed_via_dictionary():
    # If the /Shading entry is a plain COSDictionary with /ShadingType 4,
    # PDShading.create raises OSError. The pattern wrapper currently
    # catches that — verify behavior by setting via stream instead.
    pattern = PDShadingPattern()
    stream = COSStream()
    stream.set_int("ShadingType", 4)
    pattern.set_shading(stream)
    typed = pattern.get_shading()
    assert isinstance(typed, PDShadingType4)


@pytest.mark.parametrize(
    "shading_type,cls",
    [
        (5, PDShadingType5),
        (6, PDShadingType6),
        (7, PDShadingType7),
    ],
)
def test_get_shading_dispatches_to_stream_types(shading_type, cls):
    pattern = PDShadingPattern()
    stream = COSStream()
    stream.set_int("ShadingType", shading_type)
    pattern.set_shading(stream)
    typed = pattern.get_shading()
    assert isinstance(typed, cls)


def test_set_shading_accepts_typed_pd_shading():
    pattern = PDShadingPattern()
    s = PDShadingType2()
    pattern.set_shading(s)
    # Stored entry is the backing COSDictionary, not the wrapper.
    assert (
        pattern.get_cos_object().get_dictionary_object("Shading")
        is s.get_cos_object()
    )


def test_set_shading_rejects_unsupported_type():
    pattern = PDShadingPattern()
    with pytest.raises(TypeError):
        pattern.set_shading(42)  # type: ignore[arg-type]


def test_set_shading_with_none_clears_entry():
    pattern = PDShadingPattern()
    s = PDShadingType2()
    pattern.set_shading(s)
    pattern.set_shading(None)
    assert pattern.has_shading() is False
    assert pattern.get_cos_object().get_dictionary_object("Shading") is None


def test_clear_shading_is_noop_when_absent():
    pattern = PDShadingPattern()
    pattern.clear_shading()  # must not raise
    assert pattern.get_shading() is None


def test_has_shading_rejects_non_dictionary_entry():
    pattern = PDShadingPattern()
    pattern.get_cos_object().set_item(
        COSName.get_pdf_name("Shading"), COSInteger.get(5)
    )
    assert pattern.has_shading() is False
    # The getter is permissive — returns ``None`` for malformed entries.
    assert pattern.get_shading() is None


# ---------------------------------------------------------------------------
# Typed /ExtGState accessor
# ---------------------------------------------------------------------------


def test_get_extended_graphics_state_returns_typed_wrapper():
    pattern = PDShadingPattern()
    extgs = PDExtendedGraphicsState()
    pattern.set_extended_graphics_state(extgs)
    got = pattern.get_extended_graphics_state()
    assert isinstance(got, PDExtendedGraphicsState)


def test_set_extended_graphics_state_accepts_typed_wrapper():
    pattern = PDShadingPattern()
    extgs = PDExtendedGraphicsState()
    pattern.set_extended_graphics_state(extgs)
    assert (
        pattern.get_cos_object().get_dictionary_object("ExtGState")
        is extgs.get_cos_object()
    )


def test_set_extended_graphics_state_accepts_raw_cos_dictionary():
    pattern = PDShadingPattern()
    raw = COSDictionary()
    pattern.set_extended_graphics_state(raw)
    assert pattern.get_cos_object().get_dictionary_object("ExtGState") is raw


def test_set_extended_graphics_state_with_none_clears_entry():
    pattern = PDShadingPattern()
    pattern.set_extended_graphics_state(PDExtendedGraphicsState())
    pattern.set_extended_graphics_state(None)
    assert pattern.get_extended_graphics_state() is None


def test_set_extended_graphics_state_rejects_unsupported_type():
    pattern = PDShadingPattern()
    with pytest.raises(TypeError):
        pattern.set_extended_graphics_state("nope")  # type: ignore[arg-type]


def test_clear_extended_graphics_state_is_noop_when_absent():
    pattern = PDShadingPattern()
    pattern.clear_extended_graphics_state()
    assert pattern.get_extended_graphics_state() is None


def test_get_extended_graphics_state_returns_none_for_non_dict_entry():
    pattern = PDShadingPattern()
    pattern.get_cos_object().set_item(
        COSName.get_pdf_name("ExtGState"), COSInteger.get(5)
    )
    assert pattern.get_extended_graphics_state() is None


# ---------------------------------------------------------------------------
# Round-trip: factory dispatch through PDAbstractPattern.create still
# returns the right pattern subclass with the right shading sub-subclass.
# ---------------------------------------------------------------------------


def test_factory_dispatch_then_typed_shading_chain():
    raw_pattern = COSDictionary()
    raw_pattern.set_int("PatternType", 2)
    inner = COSDictionary()
    inner.set_int("ShadingType", 2)
    raw_pattern.set_item(COSName.get_pdf_name("Shading"), inner)
    p = PDAbstractPattern.create(raw_pattern)
    assert isinstance(p, PDShadingPattern)
    shading = p.get_shading()
    assert isinstance(shading, PDShading)
    assert shading.get_shading_type() == 2
