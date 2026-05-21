"""Upstream-parity port for ``AnnotationBorder``.

Mirrors ``AnnotationBorder.java`` (PDFBox 3.0.x) — the package-private
helper used by appearance handlers to resolve effective stroke width,
dash array, and underline flag. Upstream ships no JUnit test for it.
This module ports the source's behavioural contract: the precedence
between an explicit ``PDBorderStyleDictionary`` and the legacy ``/Border``
array, the all-zero dash-array drop, and the underline flag on
``STYLE_UNDERLINE``.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.interactive.annotation.handlers.annotation_border import (
    AnnotationBorder,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text import PDAnnotationText
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)

_BORDER = COSName.get_pdf_name("Border")


def test_default_instance_has_zero_width_no_dash_no_underline():
    ab = AnnotationBorder()
    assert ab.width == 0.0
    assert ab.dash_array is None
    assert ab.underline is False


def test_border_array_three_element_resolves_width():
    # Upstream: when /BS is null, /Border[2] is the stroke width.
    ann = PDAnnotationText()
    border = COSArray([COSInteger.get(0), COSInteger.get(0), COSFloat(2.5)])
    ann.get_cos_object().set_item(_BORDER, border)
    ab = AnnotationBorder.get_annotation_border(ann, None)
    assert ab.width == 2.5
    assert ab.dash_array is None


def test_border_array_four_element_resolves_dash():
    # Upstream: /Border[3] is the dash-array sub-array.
    ann = PDAnnotationText()
    dash = COSArray([COSFloat(3.0), COSFloat(2.0)])
    border = COSArray(
        [COSInteger.get(0), COSInteger.get(0), COSFloat(1.5), dash]
    )
    ann.get_cos_object().set_item(_BORDER, border)
    ab = AnnotationBorder.get_annotation_border(ann, None)
    assert ab.width == 1.5
    assert ab.dash_array == [3.0, 2.0]


def test_all_zero_dash_array_is_dropped():
    # Upstream drops dash arrays whose every entry compares equal to 0.0.
    ann = PDAnnotationText()
    dash = COSArray([COSFloat(0.0), COSFloat(0.0)])
    border = COSArray(
        [COSInteger.get(0), COSInteger.get(0), COSFloat(1.0), dash]
    )
    ann.get_cos_object().set_item(_BORDER, border)
    ab = AnnotationBorder.get_annotation_border(ann, None)
    assert ab.dash_array is None


def test_border_style_supersedes_border_array():
    # Upstream: when a PDBorderStyleDictionary is passed, the /Border
    # array is ignored and only /BS is consulted.
    ann = PDAnnotationText()
    border = COSArray([COSInteger.get(0), COSInteger.get(0), COSFloat(99.0)])
    ann.get_cos_object().set_item(_BORDER, border)
    bs = PDBorderStyleDictionary()
    bs.set_width(5.0)
    bs.set_style(PDBorderStyleDictionary.STYLE_SOLID)
    ab = AnnotationBorder.get_annotation_border(ann, bs)
    assert ab.width == 5.0
    assert ab.dash_array is None
    assert ab.underline is False


def test_border_style_dashed_pulls_dash_array():
    ann = PDAnnotationText()
    bs = PDBorderStyleDictionary()
    bs.set_width(2.0)
    bs.set_style(PDBorderStyleDictionary.STYLE_DASHED)
    bs.set_dash_style(COSArray([COSFloat(4.0), COSFloat(2.0)]))
    ab = AnnotationBorder.get_annotation_border(ann, bs)
    assert ab.width == 2.0
    assert ab.dash_array == [4.0, 2.0]
    assert ab.underline is False


def test_border_style_underline_sets_flag():
    ann = PDAnnotationText()
    bs = PDBorderStyleDictionary()
    bs.set_width(1.0)
    bs.set_style(PDBorderStyleDictionary.STYLE_UNDERLINE)
    ab = AnnotationBorder.get_annotation_border(ann, bs)
    assert ab.underline is True
    assert ab.width == 1.0


def test_missing_border_array_yields_default_width_zero():
    # No /Border at all — upstream's get_border returns null, and the
    # if-block sees border.size() < 3 (default is [0,0,1]) but width
    # stays 0 because we only read /Border[2] when size >= 3. Upstream
    # synthesises [0,0,1] in get_border so width comes out as 1.
    ann = PDAnnotationText()
    ann.get_cos_object().remove_item(_BORDER)
    ab = AnnotationBorder.get_annotation_border(ann, None)
    # Upstream's PDAnnotation.getBorder returns [0,0,1] by default →
    # width = 1.0.
    assert ab.width == 1.0
