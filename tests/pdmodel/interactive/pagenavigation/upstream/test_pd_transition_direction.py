"""Port of upstream ``PDTransitionDirectionTest`` (PDFBox 3.0.x).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/
pagenavigation/PDTransitionDirectionTest.java``.

Upstream ``PDTransitionDirection`` is a Java enum whose members each have
their own ``getCOSBase()`` method. The pypdfbox port surfaces the same
direction values as ``int`` constants on the :class:`PDTransitionDirection`
class with a single class-level ``get_cos_base(direction)`` factory — see
``pypdfbox/pdmodel/interactive/pagenavigation/pd_transition_direction.py``.
"""

from __future__ import annotations

from pypdfbox.cos import COSInteger, COSName
from pypdfbox.pdmodel.interactive.pagenavigation import PDTransitionDirection


def test_get_cos_base() -> None:
    """Each spec direction maps to the expected COS representation."""
    get_cos_base = PDTransitionDirection.get_cos_base
    assert get_cos_base(PDTransitionDirection.NONE) == COSName.get_pdf_name("None")
    assert get_cos_base(PDTransitionDirection.LEFT_TO_RIGHT).int_value() == 0
    assert get_cos_base(PDTransitionDirection.BOTTOM_TO_TOP).int_value() == 90
    assert get_cos_base(PDTransitionDirection.RIGHT_TO_LEFT).int_value() == 180
    assert get_cos_base(PDTransitionDirection.TOP_TO_BOTTOM).int_value() == 270
    cos_315 = get_cos_base(PDTransitionDirection.TOP_LEFT_TO_BOTTOM_RIGHT)
    assert isinstance(cos_315, COSInteger)
    assert cos_315.int_value() == 315
