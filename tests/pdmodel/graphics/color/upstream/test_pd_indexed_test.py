"""Ported from upstream
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/color/PDIndexedTest.java``
(PDFBox 3.0.x). Mirrors the ``PDIndexed.create`` factory tests for
PDFBOX-6192.

The upstream tests round-trip the indexed array through ``PDDocument.save``
to assert on the literal PDF output (``"/Indexed /DeviceRGB 5 <...hex...>"``).
We cover the factory contract directly here — round-trip through
``PDDocument.save`` is exercised by the broader writer parity suite.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName, COSString
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed

# ---------- testFactory (PDFBOX-6192) ----------


def test_factory() -> None:
    """Direct port of ``PDIndexedTest.testFactory()``."""
    base_color_space = PDDeviceRGB.INSTANCE
    hival = 5
    # 6 RGB triples — same hex literal as upstream.
    lookup_data = bytes.fromhex("AA1166112233000000FEDC014561FEDC34DA")
    pd_indexed = PDIndexed.create(base_color_space, hival, lookup_data)
    indexed_cos_array = pd_indexed.get_cos_object()
    assert isinstance(indexed_cos_array, COSArray)
    # array[2] is hival.
    assert indexed_cos_array.get_object(2).int_value() == hival, (
        "unexpected value for hival"
    )
    assert pd_indexed.get_name() == COSName.get_pdf_name("Indexed").get_name(), (
        "unexpected value for name"
    )
    assert pd_indexed.get_base_color_space() is base_color_space, (
        "unexpected value for base colorspace"
    )
    # array[3] is the lookup-data COSString.
    cos_lookup = indexed_cos_array.get_object(3)
    assert isinstance(cos_lookup, COSString)
    assert cos_lookup.get_bytes() == lookup_data, (
        "unexpected value for lookup data"
    )


# ---------- testFactoryParameterChecks (PDFBOX-6192) ----------


def test_factory_parameter_checks_lookup_data_not_null() -> None:
    """Lookup data must not be None."""
    with pytest.raises(ValueError):
        PDIndexed.create(PDDeviceRGB.INSTANCE, 0, None)


def test_factory_parameter_checks_base_not_null() -> None:
    """Base color space must not be None."""
    lookup_data_empty = b"\x00" * 5
    with pytest.raises(ValueError):
        PDIndexed.create(None, 0, lookup_data_empty)


def test_factory_parameter_checks_hival_not_negative() -> None:
    """hival must be >= 0."""
    lookup_data_empty = b"\x00" * 5
    with pytest.raises(ValueError):
        PDIndexed.create(PDDeviceRGB.INSTANCE, -1, lookup_data_empty)


def test_factory_parameter_checks_hival_not_over_255() -> None:
    """hival must be <= 255."""
    lookup_data_empty = b"\x00" * 5
    with pytest.raises(ValueError):
        PDIndexed.create(PDDeviceRGB.INSTANCE, 256, lookup_data_empty)


def test_factory_parameter_checks_lookup_data_minimum_size() -> None:
    """Lookup data must be at least (hival + 1) * components long."""
    lookup_data_empty = b"\x00" * 5
    hival = 5
    # Expected = 6 * 3 = 18 bytes; supplied = 5 bytes.
    with pytest.raises(ValueError):
        PDIndexed.create(PDDeviceRGB.INSTANCE, hival, lookup_data_empty)


def test_factory_parameter_checks_valid_input_does_not_raise() -> None:
    """Valid input doesn't raise."""
    lookup_data = bytes.fromhex("AA1166112233000000FEDC014561FEDC34DA")
    cs = PDIndexed.create(PDDeviceRGB.INSTANCE, 5, lookup_data)
    assert cs is not None
    assert cs.get_hival() == 5


# ---------- Smoke: PDColorSpace.create dispatch on a factory-built array ----------


def test_factory_produced_array_routes_back_through_pdcolorspace_create() -> None:
    """A factory-built PDIndexed should re-dispatch through PDColorSpace.create."""
    lookup_data = bytes.fromhex("AA1166112233000000FEDC014561FEDC34DA")
    pd_indexed = PDIndexed.create(PDDeviceRGB.INSTANCE, 5, lookup_data)
    arr = pd_indexed.get_cos_object()
    dispatched = PDColorSpace.create(arr)
    assert isinstance(dispatched, PDIndexed)
    assert dispatched.get_hival() == 5
    # Round-trip the lookup bytes through dispatch.
    assert dispatched.get_lookup_data() == lookup_data
