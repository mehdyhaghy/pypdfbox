"""Wave 1403 branch-closure test for
:meth:`PDType1CFont.generate_bounding_box`.

* ``684->686`` — the descriptor is present and returns a bounding box,
  but it is the all-zero default (``is_non_zero_bounding_box`` false), so
  the ``if self.is_non_zero_bounding_box(bbox)`` guard is false and we
  fall through to the embedded CFF program lookup.
"""

from __future__ import annotations

from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def test_generate_bounding_box_falls_through_on_all_zero_descriptor_bbox() -> None:
    """An all-zero descriptor /FontBBox is the unset sentinel — the guard
    is false (684 → 686). With no embedded CFF program the method then
    returns None from the program branch."""
    font = PDType1CFont()
    fd = PDFontDescriptor()
    fd.set_font_bounding_box(PDRectangle(0.0, 0.0, 0.0, 0.0))
    font.set_font_descriptor(fd)
    # is_non_zero_bounding_box([0,0,0,0]) is False -> fall through to
    # _get_cff_font(), which is None for a bare font -> return None.
    assert font.generate_bounding_box() is None
