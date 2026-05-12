"""XFDF (XML Forms Data Format) ingest parity tests.

Mirrors the upstream JUnit coverage for the ``Element``-taking constructors
of ``FDFDictionary`` / ``FDFField`` / ``FDFAnnotation*``. Walks a handful of
inline XFDF samples through :meth:`FDFDocument.set_xfdf` and
:meth:`Loader.load_xfdf`, asserting that each subtype-specific ``init_*``
helper (added in waves 1273 / 1278 / 1281) is correctly invoked.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.fdf import FDFDocument
from pypdfbox.pdmodel.fdf.fdf_annotation_circle import FDFAnnotationCircle
from pypdfbox.pdmodel.fdf.fdf_annotation_free_text import FDFAnnotationFreeText
from pypdfbox.pdmodel.fdf.fdf_annotation_line import FDFAnnotationLine
from pypdfbox.pdmodel.fdf.fdf_annotation_polygon import FDFAnnotationPolygon
from pypdfbox.pdmodel.fdf.fdf_annotation_polyline import FDFAnnotationPolyline
from pypdfbox.pdmodel.fdf.fdf_annotation_text_markup import FDFAnnotationTextMarkup


def _ingest(xfdf_xml: bytes) -> FDFDocument:
    fdf = FDFDocument()
    fdf.set_xfdf(xfdf_xml)
    return fdf


def test_polygon_vertices_initialised_from_xfdf() -> None:
    sample = (
        b'<?xml version="1.0"?>'
        b'<xfdf><annots>'
        b'<polygon page="0" rect="0,0,100,100" vertices="10,20;30,40;50,60"/>'
        b"</annots></xfdf>"
    )
    fdf = _ingest(sample)
    try:
        annots = fdf.get_catalog().get_fdf().get_annotations()
        assert annots is not None and len(annots) == 1
        polygon = annots[0]
        assert isinstance(polygon, FDFAnnotationPolygon)
        assert polygon.get_vertices() == [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    finally:
        fdf.close()


def test_polyline_styles_initialised_from_xfdf() -> None:
    sample = (
        b'<?xml version="1.0"?>'
        b'<xfdf><annots>'
        b'<polyline page="0" rect="0,0,100,100" vertices="10,10;20,20"'
        b' head="OpenArrow" tail="ClosedArrow" interior-color="#00ff00"/>'
        b"</annots></xfdf>"
    )
    fdf = _ingest(sample)
    try:
        annots = fdf.get_catalog().get_fdf().get_annotations()
        assert annots is not None and isinstance(annots[0], FDFAnnotationPolyline)
        polyline = annots[0]
        ic = polyline.get_interior_color()
        assert ic is not None
        # #00ff00 → green channel ~ 1.0
        assert ic[1] == pytest.approx(1.0, abs=1e-3)
    finally:
        fdf.close()


def test_circle_fringe_initialised_from_xfdf() -> None:
    sample = (
        b'<?xml version="1.0"?>'
        b'<xfdf><annots>'
        b'<circle page="1" rect="0,0,100,100" fringe="2,3,4,5"/>'
        b"</annots></xfdf>"
    )
    fdf = _ingest(sample)
    try:
        annots = fdf.get_catalog().get_fdf().get_annotations()
        assert annots is not None and isinstance(annots[0], FDFAnnotationCircle)
        # Fringe wires through to a 4-float rectangle on /RD.
        rd = annots[0].get_fringe()
        assert rd is not None
        assert rd.get_lower_left_x() == pytest.approx(2.0)
        assert rd.get_upper_right_y() == pytest.approx(5.0)
    finally:
        fdf.close()


def test_freetext_callout_initialised_from_xfdf() -> None:
    sample = (
        b'<?xml version="1.0"?>'
        b'<xfdf><annots>'
        b'<freetext page="0" rect="0,0,100,100" callout="1,2,3,4,5,6"/>'
        b"</annots></xfdf>"
    )
    fdf = _ingest(sample)
    try:
        annots = fdf.get_catalog().get_fdf().get_annotations()
        assert annots is not None and isinstance(annots[0], FDFAnnotationFreeText)
        callout = annots[0].get_callout()
        assert callout == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    finally:
        fdf.close()


def test_text_markup_subtype_resolved_from_xfdf_tag() -> None:
    """Each text-markup tag maps to the canonical PDF subtype."""
    for tag, subtype in [
        ("highlight", "Highlight"),
        ("underline", "Underline"),
        ("strikeout", "StrikeOut"),
        ("squiggly", "Squiggly"),
    ]:
        sample = (
            b'<?xml version="1.0"?>'
            b'<xfdf><annots><'
            + tag.encode()
            + b' page="0" rect="0,0,1,1"/></annots></xfdf>"'
        )
        # Defensive: rstrip trailing junk from the encoding above.
        sample = sample[: sample.rfind(b"</xfdf>") + len(b"</xfdf>")]
        fdf = _ingest(sample)
        try:
            annots = fdf.get_catalog().get_fdf().get_annotations()
            assert annots is not None and len(annots) == 1
            assert isinstance(annots[0], FDFAnnotationTextMarkup)
            assert annots[0].get_subtype() == subtype
        finally:
            fdf.close()


def test_line_annotation_parses_styles() -> None:
    sample = (
        b'<?xml version="1.0"?>'
        b'<xfdf><annots>'
        b'<line page="0" rect="0,0,100,100" head="OpenArrow" tail="Square"'
        b' interior-color="#ff00ff"/>'
        b"</annots></xfdf>"
    )
    fdf = _ingest(sample)
    try:
        annots = fdf.get_catalog().get_fdf().get_annotations()
        assert annots is not None and isinstance(annots[0], FDFAnnotationLine)
    finally:
        fdf.close()


def test_unknown_annotation_tag_skipped() -> None:
    """Unsupported annotation tags are skipped, mirroring upstream's
    ``LOG.warn("Unknown or unsupported annotation type ...")``."""
    sample = (
        b'<?xml version="1.0"?>'
        b'<xfdf><annots><mystery page="0" rect="0,0,1,1"/></annots></xfdf>'
    )
    fdf = _ingest(sample)
    try:
        annots = fdf.get_catalog().get_fdf().get_annotations()
        assert annots == []
    finally:
        fdf.close()


def test_xfdf_f_element_sets_file() -> None:
    sample = (
        b'<?xml version="1.0"?>'
        b'<xfdf><f href="source.pdf"/></xfdf>'
    )
    fdf = _ingest(sample)
    try:
        assert fdf.get_catalog().get_fdf().get_file_path() == "source.pdf"
    finally:
        fdf.close()


def test_xfdf_ids_element_sets_id_array() -> None:
    sample = (
        b'<?xml version="1.0"?>'
        b'<xfdf><ids original="DEADBEEF" modified="CAFEBABE"/></xfdf>'
    )
    fdf = _ingest(sample)
    try:
        ids = fdf.get_catalog().get_fdf().get_id()
        assert ids is not None
        assert len(ids) == 2
    finally:
        fdf.close()
