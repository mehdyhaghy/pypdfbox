"""Wave 1351 coverage boost: ``FDFAnnotationPolygon.init_vertices``.

Targets lines 33 and 38 of
``pypdfbox/pdmodel/fdf/fdf_annotation_polygon.py``:
 * line 33 — ``None`` input is a no-op
 * line 38 — empty ``""`` segments between consecutive ``;`` separators
   are skipped silently
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.fdf import FDFAnnotationPolygon


def test_init_vertices_none_is_noop() -> None:
    """Covers line 33: ``None`` input returns early without touching
    ``/Vertices``.
    """
    p = FDFAnnotationPolygon()
    p.init_vertices(None)
    assert p._annot.get_dictionary_object(COSName.get_pdf_name("Vertices")) is None


def test_init_vertices_skips_empty_segments() -> None:
    """Covers line 38: empty segments between consecutive ``;`` are
    skipped silently; surrounding valid pairs are kept.
    """
    p = FDFAnnotationPolygon()
    # leading ; → "", trailing ; → "", middle ;; → ""
    p.init_vertices(";1,2;;3,4;")
    assert p.get_vertices() == [1.0, 2.0, 3.0, 4.0]
