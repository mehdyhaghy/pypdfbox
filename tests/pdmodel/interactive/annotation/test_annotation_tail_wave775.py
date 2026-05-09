from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_free_text import (
    PDAnnotationFreeText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polyline import (
    PDAnnotationPolyline,
)
from pypdfbox.pdmodel.interactive.annotation.pd_line_info import PDLineInfo


def test_wave775_polyline_clear_vertices_removes_entry() -> None:
    ann = PDAnnotationPolyline()
    ann.set_vertices([1.0, 2.0, 3.0, 4.0])

    ann.set_vertices(None)

    assert ann.get_vertices() is None
    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("Vertices"))


def test_wave775_free_text_get_callout_absent_returns_none() -> None:
    assert PDAnnotationFreeText().get_callout() is None


def test_wave775_free_text_rect_differences_rejects_bool_in_four_values() -> None:
    ann = PDAnnotationFreeText()

    with pytest.raises(TypeError, match="set_rect_differences expects 1 or 4 values"):
        ann.set_rect_differences(1.0, True, 3.0, 4.0)

    assert ann.get_rect_differences() == []


def test_wave775_line_info_pads_short_array_and_defaults_non_numeric_entries() -> None:
    raw = COSArray([COSInteger(7), COSName.get_pdf_name("Bad"), COSFloat(9.0)])

    line = PDLineInfo(raw)

    assert raw.size() == 4
    assert line.get_start() == (7.0, 0.0)
    assert line.get_end() == (9.0, 0.0)
