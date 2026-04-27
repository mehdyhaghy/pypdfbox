"""Upstream-mirrored tests for PDMeasureDictionary.

Apache PDFBox 3.0.x has no JUnit test for
``org.apache.pdfbox.pdmodel.interactive.measurement.PDMeasureDictionary``
(no ``PDMeasureDictionaryTest.java`` exists in
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/measurement/``).

We therefore translate behaviour expressed by the upstream class' own Javadoc
contract — defaults and round-tripping through the wrapped ``COSDictionary``
— into pytest-style tests. Should upstream add a real test file in the
future, this module should be replaced with a direct port.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.measurement import (
    PDMeasureDictionary,
    PDRectlinearMeasureDictionary,
)


def test_default_constructor_assigns_type():
    md = PDMeasureDictionary()
    assert md.get_cos_object().get_name(COSName.TYPE) == PDMeasureDictionary.TYPE
    assert md.get_type() == "Measure"


def test_wrap_existing_dictionary_preserves_identity():
    src = COSDictionary()
    md = PDMeasureDictionary(src)
    assert md.get_cos_object() is src


def test_get_subtype_defaults_to_rl():
    # Upstream: getNameAsString(COSName.SUBTYPE, PDRectlinearMeasureDictionary.SUBTYPE)
    md = PDMeasureDictionary()
    assert md.get_subtype() == PDRectlinearMeasureDictionary.SUBTYPE


def test_get_subtype_returns_explicit_entry():
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "GEO")
    md = PDMeasureDictionary(raw)
    assert md.get_subtype() == "GEO"


def test_set_subtype_writes_name_entry():
    md = PDMeasureDictionary()
    md._set_subtype("RL")
    assert md.get_cos_object().get_name(COSName.SUBTYPE) == "RL"
    assert md.get_subtype() == "RL"
