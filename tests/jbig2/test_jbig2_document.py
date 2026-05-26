"""Hand-written tests for JBIG2Document / JBIG2Page end-to-end decoding.

These exercise the integration surface — file-header detection, the segment
sequence parsing loop, page/global segment assignment, referred-to-segment
resolution and full page composition — against the real upstream ``.jb2``
fixtures, without requiring the live oracle.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.jbig2_document import JBIG2Document
from pypdfbox.jbig2.jbig2_globals import JBIG2Globals
from pypdfbox.jbig2.jbig2_page import JBIG2Page

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _doc(filename: str, globals_segments: JBIG2Globals | None = None) -> JBIG2Document:
    data = (_FIXTURES / filename).read_bytes()
    return JBIG2Document(ImageInputStream(data), globals_segments)


def _embedded_globals(filename: str) -> JBIG2Globals:
    data = (_FIXTURES / filename).read_bytes()
    return JBIG2Document(ImageInputStream(data)).get_global_segments()


def test_null_input_rejected():
    with pytest.raises(ValueError):
        JBIG2Document(None)


def test_organisation_constants():
    assert JBIG2Document.RANDOM == 0
    assert JBIG2Document.SEQUENTIAL == 1


def test_standalone_file_header_detected():
    # 003.jb2 begins with the JBIG2 file header magic.
    doc = _doc("003.jb2")
    assert doc.get_amount_of_pages() == 1


def test_standalone_single_page_dimensions():
    doc = _doc("003.jb2")
    page = doc.get_page(1)
    assert isinstance(page, JBIG2Page)
    bitmap = page.get_bitmap()
    assert (bitmap.get_width(), bitmap.get_height()) == (2550, 3305)
    assert bitmap.get_row_stride() == 319


def test_005_dimensions():
    bitmap = _doc("005.jb2").get_page(1).get_bitmap()
    assert (bitmap.get_width(), bitmap.get_height()) == (2544, 3330)


def test_multi_page_document():
    doc = _doc("006.jb2")
    assert doc.get_amount_of_pages() == 10
    bitmap = doc.get_page(1).get_bitmap()
    assert bitmap.get_width() == 2496
    assert bitmap.get_height() == 3337


def test_missing_page_returns_none():
    doc = _doc("003.jb2")
    assert doc.get_page(999) is None


def test_get_bitmap_is_cached():
    page = _doc("003.jb2").get_page(1)
    first = page.get_bitmap()
    assert page.get_bitmap() is first


def test_decode_is_deterministic():
    a = _doc("003.jb2").get_page(1).get_bitmap()
    b = _doc("003.jb2").get_page(1).get_bitmap()
    assert bytes(a.get_byte_array()) == bytes(b.get_byte_array())


def test_embedded_organisation_with_external_globals():
    # 21.jb2 is the embedded organisation: no file header, the symbol
    # dictionary lives in the separate 21.glob globals stream, and the page is
    # striped (end-of-stripe + text region).
    globals_segments = _embedded_globals("21.glob")
    doc = _doc("21.jb2", globals_segments)
    assert doc.get_amount_of_pages() == 1
    bitmap = doc.get_page(1).get_bitmap()
    assert (bitmap.get_width(), bitmap.get_height()) == (2560, 3296)


def test_embedded_page_segment_types():
    # The page references a striped text region (50/6) composed over the page,
    # and the symbol dictionary (0) is resolved from globals.
    globals_segments = _embedded_globals("21.glob")
    doc = _doc("21.jb2", globals_segments)
    page = doc.get_page(1)
    types = {s.get_segment_type() for s in page.segments.values()}
    assert 6 in types  # immediate text region
    assert 48 in types  # page information
    # The symbol dictionary is global, not on the page.
    assert {s.get_segment_type() for s in globals_segments.global_segments.values()} == {0}


def test_global_segment_lookup_falls_back_to_document():
    globals_segments = _embedded_globals("21.glob")
    doc = _doc("21.jb2", globals_segments)
    page = doc.get_page(1)
    # The symbol-dictionary number 0 is not on the page; get_segment must fall
    # back to the document's global segments.
    assert page.get_segment(0) is not None
    assert page.get_segment(0).get_segment_type() == 0


def test_page_str():
    page = _doc("003.jb2").get_page(1)
    assert "Page number: 1" in str(page)


def test_get_width_and_resolution_accessors():
    page = _doc("003.jb2").get_page(1)
    assert page.get_width() == 2550
    # Resolution accessors should not raise (values may be 0 for these fixtures).
    page.get_resolution_x()
    page.get_resolution_y()
    assert page.get_height() == 3305
