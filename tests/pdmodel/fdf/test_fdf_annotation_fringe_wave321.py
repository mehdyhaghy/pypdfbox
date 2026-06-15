from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName, COSObject, COSString
from pypdfbox.pdmodel.fdf import FDFAnnotationCircle, FDFAnnotationSquare
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_RD = COSName.get_pdf_name("RD")


@pytest.mark.parametrize(
    "annotation_cls",
    [FDFAnnotationSquare, FDFAnnotationCircle],
)
def test_wave321_fringe_round_trips_and_clears(annotation_cls: type) -> None:
    annotation = annotation_cls()
    fringe = PDRectangle(1.0, 2.0, 3.0, 4.0)

    assert annotation.get_fringe() is None

    annotation.set_fringe(fringe)
    assert annotation.get_fringe() == fringe

    annotation.set_fringe(None)
    assert annotation.get_fringe() is None
    assert not annotation.get_cos_object().contains_key(_RD)


@pytest.mark.parametrize(
    "annotation_cls",
    [FDFAnnotationSquare, FDFAnnotationCircle],
)
def test_wave321_fringe_resolves_indirect_numeric_entries(annotation_cls: type) -> None:
    annotation = annotation_cls()
    annotation.get_cos_object().set_item(
        _RD,
        COSArray(
            [
                COSObject(1, resolved=COSFloat(4.0)),
                COSObject(2, resolved=COSFloat(3.0)),
                COSObject(3, resolved=COSFloat(2.0)),
                COSObject(4, resolved=COSFloat(1.0)),
            ]
        ),
    )

    assert annotation.get_fringe() == PDRectangle(2.0, 1.0, 4.0, 3.0)


@pytest.mark.parametrize(
    "raw",
    [
        COSString("not an array"),
        COSArray([COSFloat(1.0), COSFloat(2.0), COSFloat(3.0)]),
    ],
)
def test_wave321_malformed_fringe_reports_absent(raw: object) -> None:
    """Non-array values and short (<4 entry) arrays are still reported
    absent via the caller's own length guard."""
    annotation = FDFAnnotationSquare()
    annotation.get_cos_object().set_item(_RD, raw)  # type: ignore[arg-type]

    assert annotation.get_fringe() is None


def test_wave321_four_entry_malformed_fringe_coerces_to_rectangle() -> None:
    """A 4-entry /RD with a non-numeric slot passes the length guard;
    upstream ``new PDRectangle(COSArray)`` coerces the bad slot to ``0.0``
    and normalizes, so ``[1, /Bad, 3, 4]`` yields ``PDRectangle(1, 0, 3, 4)``."""
    annotation = FDFAnnotationSquare()
    annotation.get_cos_object().set_item(
        _RD,
        COSArray(
            [
                COSFloat(1.0),
                COSName.get_pdf_name("Bad"),
                COSFloat(3.0),
                COSFloat(4.0),
            ]
        ),
    )

    assert annotation.get_fringe() == PDRectangle(1.0, 0.0, 3.0, 4.0)
