from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.graphics.pattern import PDShadingPattern
from pypdfbox.pdmodel.graphics.shading import PDShadingType2


def test_shading_pattern_clear_shading_removes_typed_shading_entry() -> None:
    pattern = PDShadingPattern()
    pattern.set_shading(PDShadingType2())

    assert pattern.has_shading() is True
    assert pattern.get_shading() is not None

    pattern.clear_shading()

    assert pattern.has_shading() is False
    assert pattern.get_shading() is None


def test_shading_pattern_malformed_shading_entry_reports_absent() -> None:
    pattern = PDShadingPattern()
    pattern.set_shading(COSName.get_pdf_name("BadShading"))

    assert pattern.has_shading() is False
    assert pattern.get_shading() is None
