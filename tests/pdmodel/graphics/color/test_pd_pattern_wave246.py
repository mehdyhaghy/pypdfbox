"""Wave 246 — round-out parity additions on
:class:`pypdfbox.pdmodel.graphics.color.pd_pattern.PDPattern`.

Covers the small set of mechanical parity gaps closed in this wave:

* :meth:`PDPattern.get_default_decode` — explicit
  :class:`NotImplementedError` mirroring upstream
  ``PDPattern.getDefaultDecode(int)`` throwing
  ``UnsupportedOperationException`` (the base ``PDColorSpace``
  default would silently return an empty list because
  ``getNumberOfComponents() == 0``).
* :meth:`PDPattern.has_underlying_color_space` — convenience
  predicate paired with :meth:`get_underlying_color_space`.
* :meth:`PDPattern.is_colored` / :meth:`PDPattern.is_uncolored` —
  predicates distinguishing the two PDF Pattern color-space forms
  (``/Pattern`` vs ``[/Pattern <CS>]``) without resource
  resolution. Naming aligns with :class:`PDTilingPattern`'s
  predicates.
* :meth:`PDPattern.get_pattern_or_none` — soft variant of
  :meth:`get_pattern` that returns ``None`` rather than raising
  ``OSError`` for the same three failure modes (no resources,
  no pattern name on the color, named pattern missing).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.graphics.pattern import (
    PDAbstractPattern,
    PDTilingPattern,
)
from pypdfbox.pdmodel.pd_resources import PDResources

_PATTERN = COSName.get_pdf_name("Pattern")
_PATTERN_TYPE = COSName.get_pdf_name("PatternType")


# ---------- get_default_decode ----------


def test_get_default_decode_raises_for_colored_pattern() -> None:
    """Upstream ``PDPattern.getDefaultDecode`` throws
    ``UnsupportedOperationException``. We surface the same intent as
    :class:`NotImplementedError` so the absence of a meaningful decode
    array doesn't silently return ``[]`` (which the base class would
    do because ``get_number_of_components()`` reports 0)."""
    cs = PDPattern()
    with pytest.raises(NotImplementedError):
        cs.get_default_decode(8)


def test_get_default_decode_raises_for_uncolored_pattern() -> None:
    """Even with an underlying CS, the *Pattern* CS itself has no
    decode array — only the underlying CS's decode is meaningful."""
    cs = PDPattern(PDDeviceRGB.INSTANCE)
    with pytest.raises(NotImplementedError):
        cs.get_default_decode(8)


def test_get_default_decode_message_mentions_underlying() -> None:
    """The error message hints at the right next call."""
    cs = PDPattern()
    with pytest.raises(NotImplementedError, match="underlying"):
        cs.get_default_decode(1)


def test_get_default_decode_independent_of_bits_per_component() -> None:
    """Bits-per-component is irrelevant — the unsupported operation
    isn't gated on it."""
    cs = PDPattern()
    for bpc in (1, 2, 4, 8, 16):
        with pytest.raises(NotImplementedError):
            cs.get_default_decode(bpc)


# ---------- has_underlying_color_space ----------


def test_has_underlying_color_space_false_for_colored_pattern() -> None:
    cs = PDPattern()
    assert cs.has_underlying_color_space() is False


def test_has_underlying_color_space_true_for_uncolored_pattern() -> None:
    cs = PDPattern(PDDeviceRGB.INSTANCE)
    assert cs.has_underlying_color_space() is True


def test_has_underlying_color_space_true_for_uncolored_with_cmyk() -> None:
    cs = PDPattern(PDDeviceCMYK.INSTANCE)
    assert cs.has_underlying_color_space() is True


def test_has_underlying_color_space_aligns_with_accessor() -> None:
    """The predicate is precisely ``get_underlying_color_space() is not None``."""
    for cs in (
        PDPattern(),
        PDPattern(PDDeviceGray.INSTANCE),
        PDPattern(PDDeviceRGB.INSTANCE),
        PDPattern(PDDeviceCMYK.INSTANCE),
    ):
        assert cs.has_underlying_color_space() is (
            cs.get_underlying_color_space() is not None
        )


# ---------- is_colored / is_uncolored ----------


def test_is_colored_true_for_bare_name_form() -> None:
    """``/Pattern`` (no underlying CS) is the colored / shading form."""
    cs = PDPattern()
    assert cs.is_colored() is True
    assert cs.is_uncolored() is False


def test_is_uncolored_true_for_array_form_with_underlying() -> None:
    """``[/Pattern <CS>]`` is the uncolored tiling form."""
    cs = PDPattern(PDDeviceRGB.INSTANCE)
    assert cs.is_uncolored() is True
    assert cs.is_colored() is False


def test_is_colored_and_is_uncolored_are_mutually_exclusive() -> None:
    for cs in (
        PDPattern(),
        PDPattern(PDDeviceGray.INSTANCE),
        PDPattern(PDDeviceRGB.INSTANCE),
        PDPattern(PDDeviceCMYK.INSTANCE),
    ):
        assert cs.is_colored() is not cs.is_uncolored()


def test_is_colored_round_trips_through_factory() -> None:
    """A Pattern color space round-tripped through ``PDColorSpace.create``
    in its name form must report ``is_colored()`` true."""
    from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace

    cs = PDColorSpace.create(COSName.get_pdf_name("Pattern"))
    assert isinstance(cs, PDPattern)
    assert cs.is_colored() is True
    assert cs.is_uncolored() is False


def test_is_uncolored_round_trips_through_factory_array_form() -> None:
    """``[/Pattern /DeviceRGB]`` reified by the factory must report
    ``is_uncolored()`` true and expose its underlying color space."""
    from pypdfbox.cos import COSArray
    from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace

    arr = COSArray()
    arr.add(COSName.get_pdf_name("Pattern"))
    arr.add(COSName.get_pdf_name("DeviceRGB"))
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDPattern)
    assert cs.is_uncolored() is True
    assert cs.is_colored() is False
    assert cs.get_underlying_color_space() is PDDeviceRGB.INSTANCE


# ---------- get_pattern_or_none ----------


def _resources_with_pattern(name: str, pattern_dict: COSDictionary) -> PDResources:
    """Build a ``PDResources`` whose ``/Pattern`` sub-dictionary
    contains exactly one pattern under ``name``."""
    resources = PDResources()
    pattern_subdict = COSDictionary()
    pattern_subdict.set_item(COSName.get_pdf_name(name), pattern_dict)
    resources.get_cos_object().set_item(_PATTERN, pattern_subdict)
    return resources


def test_get_pattern_or_none_resolves_when_present() -> None:
    tiling_stream = COSStream()
    tiling_stream.set_int(_PATTERN_TYPE, PDAbstractPattern.TYPE_TILING_PATTERN)
    resources = _resources_with_pattern("P1", tiling_stream)

    cs = PDPattern(resources=resources)
    color = PDColor([], cs, COSName.get_pdf_name("P1"))

    pattern = cs.get_pattern_or_none(color)
    assert isinstance(pattern, PDTilingPattern)
    assert pattern.get_cos_object() is tiling_stream


def test_get_pattern_or_none_returns_none_when_no_resources() -> None:
    cs = PDPattern()
    color = PDColor([], cs, COSName.get_pdf_name("P1"))
    assert cs.get_pattern_or_none(color) is None


def test_get_pattern_or_none_returns_none_when_color_has_no_pattern_name() -> None:
    resources = PDResources()
    cs = PDPattern(resources=resources)
    color = PDColor([], cs)  # no pattern name attached
    assert cs.get_pattern_or_none(color) is None


def test_get_pattern_or_none_returns_none_when_named_pattern_missing() -> None:
    """Resources attached but no /Pattern entry — the soft accessor
    returns ``None`` where the throwing :meth:`get_pattern` raises."""
    resources = PDResources()  # no /Pattern subdict at all
    cs = PDPattern(resources=resources)
    color = PDColor([], cs, COSName.get_pdf_name("Missing"))
    assert cs.get_pattern_or_none(color) is None


def test_get_pattern_or_none_does_not_raise_in_hot_path() -> None:
    """Smoke-test the contract: across all three failure modes,
    ``get_pattern_or_none`` must never raise."""
    cs_no_res = PDPattern()
    cs_with_res = PDPattern(resources=PDResources())
    bad_name = COSName.get_pdf_name("AbsentPattern")
    color_no_name = PDColor([], cs_no_res)
    color_bad_name = PDColor([], cs_no_res, bad_name)

    # All four (cs, color) combos that exercise the failure paths.
    assert cs_no_res.get_pattern_or_none(color_no_name) is None
    assert cs_no_res.get_pattern_or_none(color_bad_name) is None
    assert cs_with_res.get_pattern_or_none(color_no_name) is None
    assert cs_with_res.get_pattern_or_none(color_bad_name) is None


def test_get_pattern_and_get_pattern_or_none_return_same_pattern() -> None:
    """Happy path: both accessors resolve to the same underlying
    pattern dictionary (the typed wrappers are constructed afresh on
    each ``PDResources.get_pattern`` lookup)."""
    tiling_stream = COSStream()
    tiling_stream.set_int(_PATTERN_TYPE, PDAbstractPattern.TYPE_TILING_PATTERN)
    resources = _resources_with_pattern("P1", tiling_stream)

    cs = PDPattern(resources=resources)
    color = PDColor([], cs, COSName.get_pdf_name("P1"))

    raising = cs.get_pattern(color)
    soft = cs.get_pattern_or_none(color)
    assert soft is not None
    assert isinstance(soft, PDTilingPattern)
    assert soft.get_cos_object() is raising.get_cos_object() is tiling_stream
