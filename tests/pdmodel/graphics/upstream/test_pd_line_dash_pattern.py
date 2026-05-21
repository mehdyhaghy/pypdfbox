"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/PDLineDashPatternTest.java

Upstream baseline: PDFBox 3.0.x. Java's ``System.out.println(dash)`` at the
end of ``testGetCOSObject`` is dropped — Java-only plumbing per
CLAUDE.md test porting conventions — but the ``toString`` form is asserted
explicitly to keep the diagnostic surface pinned.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger
from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern


def test_get_cos_object() -> None:
    # Java: COSArray ar = new COSArray(); ar.add(COSInteger.ONE); ar.add(COSInteger.TWO);
    # PDLineDashPattern dash = new PDLineDashPattern(ar, 3);
    array = COSArray()
    array.add(COSInteger.ONE)
    array.add(COSInteger.TWO)
    dash = PDLineDashPattern(array, 3)

    dash_base = dash.get_cos_object()
    assert isinstance(dash_base, COSArray)

    dash_array = dash_base.get_object(0)
    assert isinstance(dash_array, COSArray)

    # Java: assertEquals(2, dashBase.size());
    assert dash_base.size() == 2
    # Java: assertEquals(2, dashArray.size());
    assert dash_array.size() == 2

    # Java: assertEquals(COSFloat.ONE, dashArray.get(0));
    assert dash_array.get(0) == COSFloat.ONE
    # Java: assertEquals(new COSFloat(2), dashArray.get(1));
    assert dash_array.get(1) == COSFloat(2)
    # Java: assertEquals(COSInteger.THREE, dashBase.get(1));
    assert dash_base.get(1) == COSInteger.THREE

    # Java: System.out.println(dash); — replaced with a direct ``str()``
    # round-trip so the toString surface is pinned rather than silently dropped.
    text = str(dash)
    assert "PDLineDashPattern" in text
    assert "phase=3" in text
