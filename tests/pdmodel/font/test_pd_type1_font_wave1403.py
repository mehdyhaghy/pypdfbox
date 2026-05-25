"""Wave 1403 branch-closure test for
:meth:`PDType1Font.get_glyph_width`.

* ``252->255`` — on the Standard 14 fallback path, the resolved glyph
  name is ``.notdef`` (StandardEncoding maps the control-range codes to
  notdef), so the ``if glyph_name != ".notdef"`` guard is false and the
  method returns the ``0.0`` final fallback rather than an AFM width.
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

_BASE_FONT = COSName.get_pdf_name("BaseFont")


def test_get_glyph_width_returns_zero_for_notdef_code_on_standard14() -> None:
    """Helvetica (Standard 14) with no /Widths and no embedded program:
    code 0 maps to ``.notdef`` via StandardEncoding, so the Standard 14
    branch hits the ``glyph_name != ".notdef"`` guard's false side
    (252 → 255) and returns 0.0."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    # No /Widths, no /FontFile -> reaches the Standard 14 path; code 0 is
    # .notdef in StandardEncoding -> 0.0.
    assert font.get_glyph_width(0) == 0.0
    # Sanity: a real glyph still resolves to its AFM width (252 true side).
    assert font.get_glyph_width(ord("A")) == 667.0
