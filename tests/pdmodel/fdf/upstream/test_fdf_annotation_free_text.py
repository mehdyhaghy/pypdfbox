"""Upstream-style parity tests for ``FDFAnnotationFreeText``.

There is no dedicated ``FDFAnnotationFreeTextTest.java`` upstream; the FreeText
class is exercised indirectly via ``FDFAnnotationTest.loadXFDFAnnotations``
which depends on an XFDF ``Loader`` that has not yet been ported. This module
ports the API surface contracts that those upstream tests transitively rely on
(JavaDoc + tests below cover ``setCallout``/``getCallout``,
``setJustification``/``getJustification``, ``setRotation``/``getRotation``,
``setDefaultAppearance``/``getDefaultAppearance``,
``setDefaultStyle``/``getDefaultStyle``, ``setFringe``/``getFringe``,
``setLineEndingStyle``/``getLineEndingStyle``).

Keep tests upstream-shaped: assert names and return types as documented in
``FDFAnnotationFreeText.java`` (e.g. ``getJustification`` returns ``String``,
``getRotation`` returns ``String``).
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.fdf import FDFAnnotationFreeText
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def test_subtype_default_constructor_stamps_free_text() -> None:
    a = FDFAnnotationFreeText()
    # Upstream constructor (line 49): annot.setName(SUBTYPE, "FreeText").
    assert a.get_subtype() == "FreeText"
    assert FDFAnnotationFreeText.SUBTYPE == "FreeText"


def test_set_callout_round_trip() -> None:
    # Upstream lines 132-151.
    a = FDFAnnotationFreeText()
    assert a.get_callout() is None
    a.set_callout([1.0, 2.0, 3.0, 4.0])
    assert a.get_callout() == [1.0, 2.0, 3.0, 4.0]
    a.set_callout([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    assert a.get_callout() == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


def test_set_justification_centered() -> None:
    # Upstream lines 158-180.
    a = FDFAnnotationFreeText()
    a.set_justification("centered")
    assert a.get_justification() == "1"


def test_set_justification_right() -> None:
    a = FDFAnnotationFreeText()
    a.set_justification("right")
    assert a.get_justification() == "2"


def test_set_justification_default_left() -> None:
    a = FDFAnnotationFreeText()
    a.set_justification("left")  # anything != "centered" / "right" -> 0
    assert a.get_justification() == "0"


def test_get_justification_default_zero() -> None:
    a = FDFAnnotationFreeText()
    assert a.get_justification() == "0"


def test_set_rotation_stores_int_under_rotate() -> None:
    # Upstream lines 187-200: setRotation(int) writes COSInteger to /Rotate;
    # getRotation() routes through COSDictionary.getString which returns null
    # for non-string entries, so it yields None even after set_rotation. Match
    # that quirk and assert the raw int landed under the right key.
    a = FDFAnnotationFreeText()
    a.set_rotation(90)
    assert a.get_rotation() is None
    assert a.get_cos_object().get_int(COSName.get_pdf_name("Rotate")) == 90


def test_get_rotation_returns_none_when_absent() -> None:
    # Upstream getRotation calls getString which yields null when /Rotate is
    # absent; pypdfbox's COSDictionary.get_string returns None.
    a = FDFAnnotationFreeText()
    assert a.get_rotation() is None


def test_default_appearance_round_trip() -> None:
    # Upstream lines 207-221.
    a = FDFAnnotationFreeText()
    assert a.get_default_appearance() is None
    a.set_default_appearance("/Helv 12 Tf 0 g")
    assert a.get_default_appearance() == "/Helv 12 Tf 0 g"


def test_default_style_round_trip() -> None:
    # Upstream lines 228-241.
    a = FDFAnnotationFreeText()
    assert a.get_default_style() is None
    a.set_default_style("font:12pt Helvetica;color:#000000")
    assert a.get_default_style() == "font:12pt Helvetica;color:#000000"


def test_set_fringe_round_trip() -> None:
    # Upstream lines 250-265.
    a = FDFAnnotationFreeText()
    assert a.get_fringe() is None
    rect = PDRectangle()
    rect.set_lower_left_x(1.0)
    rect.set_lower_left_y(2.0)
    rect.set_upper_right_x(3.0)
    rect.set_upper_right_y(4.0)
    a.set_fringe(rect)
    out = a.get_fringe()
    assert out is not None
    assert out.get_lower_left_x() == 1.0
    assert out.get_upper_right_y() == 4.0


def test_set_line_ending_style_round_trip() -> None:
    # Upstream lines 272-285.
    a = FDFAnnotationFreeText()
    assert a.get_line_ending_style() is None
    a.set_line_ending_style("OpenArrow")
    assert a.get_line_ending_style() == "OpenArrow"


def test_callout_stored_under_cl_name() -> None:
    # Upstream uses COSName.CL ("CL").
    a = FDFAnnotationFreeText()
    a.set_callout([0.0, 0.0, 1.0, 1.0])
    assert a.get_cos_object().get_dictionary_object(COSName.get_pdf_name("CL")) is not None


def test_fringe_stored_under_rd_name() -> None:
    # Upstream uses COSName.RD ("RD").
    a = FDFAnnotationFreeText()
    rect = PDRectangle()
    a.set_fringe(rect)
    assert a.get_cos_object().get_dictionary_object(COSName.get_pdf_name("RD")) is not None


def test_rotation_stored_under_rotate_name() -> None:
    # Upstream uses COSName.ROTATE which resolves to "Rotate" (not "Rotation").
    a = FDFAnnotationFreeText()
    a.set_rotation(90)
    assert a.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Rotate")) is not None
