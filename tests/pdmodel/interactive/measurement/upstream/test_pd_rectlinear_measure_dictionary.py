"""Upstream-mirrored tests for PDRectlinearMeasureDictionary.

Apache PDFBox 3.0.x has no JUnit test for
``org.apache.pdfbox.pdmodel.interactive.measurement.PDRectlinearMeasureDictionary``
(no ``PDRectlinearMeasureDictionaryTest.java`` exists in
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/measurement/``).

We therefore translate behaviour expressed by the upstream class' own
Javadoc contract — type/subtype tagging, the seven number-format-array
accessors, the coordinate-system origin, and the CYX factor — into
pytest-style tests. Should upstream add a real test file in the future,
this module should be replaced with a direct port.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.measurement import (
    PDNumberFormatDictionary,
    PDRectlinearMeasureDictionary,
)


def test_default_constructor_assigns_type_and_subtype():
    rl = PDRectlinearMeasureDictionary()
    cos = rl.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "Measure"
    assert cos.get_name(COSName.SUBTYPE) == "RL"
    assert rl.get_subtype() == PDRectlinearMeasureDictionary.SUBTYPE


def test_wrap_existing_dictionary_preserves_identity():
    src = COSDictionary()
    rl = PDRectlinearMeasureDictionary(src)
    assert rl.get_cos_object() is src


def test_scale_ratio_round_trip():
    rl = PDRectlinearMeasureDictionary()
    assert rl.get_scale_ratio() is None
    rl.set_scale_ratio("1in = 1mi")
    assert rl.get_scale_ratio() == "1in = 1mi"


@pytest.mark.parametrize(
    ("getter", "setter"),
    [
        ("get_change_xs", "set_change_xs"),
        ("get_change_ys", "set_change_ys"),
        ("get_distances", "set_distances"),
        ("get_areas", "set_areas"),
        ("get_angles", "set_angles"),
        ("get_line_sloaps", "set_line_sloaps"),
    ],
)
def test_number_format_array_round_trip(getter, setter):
    rl = PDRectlinearMeasureDictionary()
    assert getattr(rl, getter)() is None

    nf = PDNumberFormatDictionary()
    getattr(rl, setter)([nf])

    fetched = getattr(rl, getter)()
    assert fetched is not None
    assert len(fetched) == 1
    assert fetched[0].get_cos_object() is nf.get_cos_object()


def test_coord_system_origin_round_trip():
    rl = PDRectlinearMeasureDictionary()
    assert rl.get_coord_system_origin() is None
    rl.set_coord_system_origin([12.0, 34.0])
    assert rl.get_coord_system_origin() == [12.0, 34.0]
    assert isinstance(
        rl.get_cos_object().get_dictionary_object(COSName.get_pdf_name("O")),
        COSArray,
    )


def test_cyx_round_trip():
    rl = PDRectlinearMeasureDictionary()
    # Upstream getFloat default is -1; pypdfbox COSDictionary.get_float
    # mirrors that with -1.0.
    assert rl.get_cyx() == -1.0
    rl.set_cyx(2.5)
    assert rl.get_cyx() == pytest.approx(2.5)


def test_subclasses_pd_measure_dictionary():
    from pypdfbox.pdmodel.interactive.measurement import PDMeasureDictionary

    rl = PDRectlinearMeasureDictionary()
    assert isinstance(rl, PDMeasureDictionary)
