"""Port of upstream ``LigatureTest`` from
``fontbox/src/test/java/org/apache/fontbox/afm/LigatureTest.java``.
"""

from __future__ import annotations

from pypdfbox.fontbox.afm import Ligature


# Translated from testLigature -- constructor + accessor parity.
def test_ligature() -> None:
    ligature = Ligature("successor", "ligature")
    assert ligature.get_successor() == "successor"
    assert ligature.get_ligature() == "ligature"
