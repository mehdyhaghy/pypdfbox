"""Ported from upstream's ``KernPairTest.java``.

Source:
``pdfbox/fontbox/src/test/java/org/apache/fontbox/afm/KernPairTest.java``
(Apache PDFBox 3.0.x).
"""
from __future__ import annotations

from pypdfbox.fontbox.afm import KernPair


def test_kern_pair() -> None:
    kp = KernPair("firstKernCharacter", "secondKernCharacter", 10, 20)
    assert kp.get_first_kern_character() == "firstKernCharacter"
    assert kp.get_second_kern_character() == "secondKernCharacter"
    assert kp.get_x() == 10.0
    assert kp.get_y() == 20.0
