"""Port of upstream ``CompositePartTest`` from
``fontbox/src/test/java/org/apache/fontbox/afm/CompositePartTest.java``.
"""

from __future__ import annotations

from pypdfbox.fontbox.afm import CompositePart


# Translated from testCompositePart -- constructor + accessor parity.
def test_composite_part() -> None:
    composite_part = CompositePart("name", 10, 20)
    assert composite_part.get_name() == "name"
    assert composite_part.get_x_displacement() == 10
    assert composite_part.get_y_displacement() == 20
