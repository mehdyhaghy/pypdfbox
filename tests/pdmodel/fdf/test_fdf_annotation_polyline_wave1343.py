"""Coverage round-out for
:class:`pypdfbox.pdmodel.fdf.fdf_annotation_polyline.FDFAnnotationPolyline`
(wave 1343).

Closes off ``init_vertices`` error paths, ``init_styles`` bad-hex
short-circuit, ``set_vertices(None)`` removal, ``get_vertices`` when
the slot holds a non-array object, and the default-return branch of
``get_end_point_ending_style``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.fdf import FDFAnnotationPolyline


def test_init_vertices_none_raises_ose_error() -> None:
    poly = FDFAnnotationPolyline()
    with pytest.raises(OSError, match="missing element 'vertices'"):
        poly.init_vertices(None)


def test_init_vertices_empty_string_raises_ose_error() -> None:
    poly = FDFAnnotationPolyline()
    with pytest.raises(OSError, match="missing element 'vertices'"):
        poly.init_vertices("")


def test_init_vertices_with_non_float_token_raises_ose_error() -> None:
    poly = FDFAnnotationPolyline()
    with pytest.raises(OSError, match="vertices values must be floats"):
        poly.init_vertices("1.0,not-a-number,3.0")


def test_init_vertices_with_comma_separated_floats() -> None:
    poly = FDFAnnotationPolyline()
    poly.init_vertices("1.5,2.5,3.5,4.5")
    assert poly.get_vertices() == pytest.approx([1.5, 2.5, 3.5, 4.5])


def test_init_vertices_with_semicolon_separator() -> None:
    poly = FDFAnnotationPolyline()
    poly.init_vertices("10;20;30;40")
    assert poly.get_vertices() == pytest.approx([10.0, 20.0, 30.0, 40.0])


def test_init_styles_with_bad_hex_interior_color_is_a_noop() -> None:
    """``init_styles`` swallows a malformed ``#RRGGBB`` colour silently —
    the surrounding XFDF attribute is best-effort. Hits the ``ValueError``
    branch (lines 72-73)."""
    poly = FDFAnnotationPolyline()
    poly.init_styles(interior_color="#ZZZZZZ")
    assert poly.get_interior_color() is None


def test_init_styles_with_valid_hex_interior_color_parses_rgb() -> None:
    poly = FDFAnnotationPolyline()
    poly.init_styles(interior_color="#FF8040")
    # 0xFF/255, 0x80/255, 0x40/255
    assert poly.get_interior_color() == pytest.approx(
        (1.0, 0x80 / 255.0, 0x40 / 255.0)
    )


def test_init_styles_with_wrong_length_interior_color_is_a_noop() -> None:
    poly = FDFAnnotationPolyline()
    poly.init_styles(interior_color="#FFF")  # too short
    assert poly.get_interior_color() is None


def test_init_styles_without_hash_prefix_is_a_noop() -> None:
    poly = FDFAnnotationPolyline()
    poly.init_styles(interior_color="FF8040A")  # 7 chars but no '#'
    assert poly.get_interior_color() is None


def test_init_styles_sets_head_and_tail() -> None:
    poly = FDFAnnotationPolyline()
    poly.init_styles(head="OpenArrow", tail="Square")
    assert poly.get_start_point_ending_style() == "OpenArrow"
    assert poly.get_end_point_ending_style() == "Square"


def test_set_vertices_none_removes_existing_entry() -> None:
    poly = FDFAnnotationPolyline()
    poly.set_vertices([10.0, 20.0])
    assert poly.get_vertices() == pytest.approx([10.0, 20.0])
    poly.set_vertices(None)
    assert poly.get_vertices() is None
    # And the underlying dictionary slot is truly removed.
    assert poly.get_cos_object().get_dictionary_object("Vertices") is None


def test_get_vertices_returns_none_when_slot_is_not_an_array() -> None:
    """If something other than a COSArray sits at /Vertices the getter
    must return ``None`` (line 102 — the ``isinstance`` guard fall-through)."""
    cos = COSDictionary()
    cos.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Polyline"))
    cos.set_item(COSName.get_pdf_name("Vertices"), COSInteger(42))
    poly = FDFAnnotationPolyline(cos)
    assert poly.get_vertices() is None


def test_get_end_point_ending_style_default_when_absent() -> None:
    """Hits line 158 — default return when /LE is missing."""
    poly = FDFAnnotationPolyline()
    assert poly.get_end_point_ending_style() == "None"
