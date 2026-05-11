"""Wave 1286.3 — round-trip tests for the four newly-implemented examples.

Verifies that ``create_gradient_shading_pdf``, ``create_patterns_pdf``,
``add_annotations``, and ``create_separation_color_box`` drive their
public entry points end-to-end against in-memory PDFs without relying
on external fixtures, and that the resulting PDF parses back cleanly.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.pdmodel.add_annotations import AddAnnotations
from pypdfbox.examples.pdmodel.create_gradient_shading_pdf import (
    CreateGradientShadingPDF,
)
from pypdfbox.examples.pdmodel.create_patterns_pdf import CreatePatternsPDF
from pypdfbox.examples.pdmodel.create_separation_color_box import (
    CreateSeparationColorBox,
)
from pypdfbox.loader import Loader
from pypdfbox.pdmodel.pd_document import PDDocument


def _assert_roundtrip(path: Path, *, expected_pages: int = 1) -> PDDocument:
    """Open ``path`` via the loader, assert it has ``expected_pages``, and
    return the opened :class:`PDDocument` so the caller can drill in
    further. The caller must close the document when finished.
    """
    assert path.exists(), f"output file missing: {path}"
    assert path.stat().st_size > 0, f"output file empty: {path}"
    cos_doc = Loader.load_pdf(path)
    doc = PDDocument(cos_doc)
    assert doc.get_number_of_pages() == expected_pages
    return doc


def test_create_gradient_shading_pdf_produces_three_shadings(
    tmp_path: Path,
) -> None:
    out = tmp_path / "gradient.pdf"
    CreateGradientShadingPDF.main([str(out)])
    doc = _assert_roundtrip(out, expected_pages=1)
    try:
        page = doc.get_page(0)
        resources = page.get_resources()
        # Three shadings (axial, radial, gouraud) should be registered
        # under /Resources/Shading.
        shading_names = list(resources.get_shading_names())
        assert len(shading_names) == 3
    finally:
        doc.close()


def test_create_patterns_pdf_registers_tiling_patterns(
    tmp_path: Path,
) -> None:
    out = tmp_path / "patterns.pdf"
    CreatePatternsPDF.main([str(out)])
    doc = _assert_roundtrip(out, expected_pages=1)
    try:
        page = doc.get_page(0)
        resources = page.get_resources()
        # Two tiling patterns get registered (one colored, one uncolored).
        pattern_names = list(resources.get_pattern_names())
        assert len(pattern_names) == 2
    finally:
        doc.close()


def test_add_annotations_writes_three_pages_with_annotations(
    tmp_path: Path,
) -> None:
    out = tmp_path / "annotations.pdf"
    AddAnnotations.main([str(out)])
    doc = _assert_roundtrip(out, expected_pages=3)
    try:
        page1 = doc.get_page(0)
        annots = page1.get_annotations()
        # Highlight + 2 links + circle + square + line + free-text + polygon.
        assert len(annots) == 8
        kinds = {ann.__class__.__name__ for ann in annots}
        assert "PDAnnotationHighlight" in kinds
        assert "PDAnnotationLink" in kinds
        assert "PDAnnotationCircle" in kinds
        assert "PDAnnotationSquare" in kinds
        assert "PDAnnotationLine" in kinds
        assert "PDAnnotationFreeText" in kinds
        assert "PDAnnotationPolygon" in kinds
        # AcroForm got a /Helv default resource.
        catalog = doc.get_document_catalog()
        acro_form = catalog.get_acro_form()
        assert acro_form is not None
        dr = acro_form.get_default_resources()
        assert dr is not None
        assert dr.get_font_names()
    finally:
        doc.close()


def test_create_separation_color_box_writes_spot_color(
    tmp_path: Path,
) -> None:
    out = tmp_path / "gold.pdf"
    CreateSeparationColorBox.main([str(out)])
    doc = _assert_roundtrip(out, expected_pages=1)
    try:
        page = doc.get_page(0)
        # Re-opening should resolve the page without surfacing a parse
        # error for the embedded /Separation array + tint transform.
        assert page is not None
    finally:
        doc.close()
