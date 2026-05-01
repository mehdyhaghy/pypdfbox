"""Ported from upstream's ``CompositeTest.java``.

Source:
``pdfbox/fontbox/src/test/java/org/apache/fontbox/afm/CompositeTest.java``
(Apache PDFBox 3.0.x).
"""
from __future__ import annotations

from pypdfbox.fontbox.afm import Composite, CompositePart


def test_composite() -> None:
    composite = Composite("name")
    assert composite.get_name() == "name"
    assert len(composite.get_parts()) == 0
    composite_part = CompositePart("name", 10, 20)
    composite.add_part(composite_part)
    parts = composite.get_parts()
    assert len(parts) == 1
    assert parts[0].get_name() == "name"
    # Returned list is a copy — mutating it must not change Composite.
    parts.append(composite_part)
    assert len(composite.get_parts()) == 1
