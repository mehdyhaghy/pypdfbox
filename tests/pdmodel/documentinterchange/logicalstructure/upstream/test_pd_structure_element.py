from __future__ import annotations

# Upstream PDFBox 3.0.x ships ``PDStructureElement`` without a dedicated
# ``PDStructureElementTest.java`` in
# ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/documentinterchange/
# logicalstructure/``. The class is exercised indirectly via integration
# tests against tagged-PDF fixtures (e.g. PDFBOX-2812, PDFBOX-3017).
#
# Behavior parity is covered by the hand-written tests in
# ``test_pd_structure_element.py`` and ``test_pd_structure_element_parity.py``;
# this stub exists so the upstream-test directory layout matches the
# convention from PRD §12.

import pytest

pytest.skip(
    "no standalone upstream PDStructureElementTest.java — behaviour "
    "covered by integration tests upstream and by the hand-written "
    "parity suite in this directory",
    allow_module_level=True,
)
