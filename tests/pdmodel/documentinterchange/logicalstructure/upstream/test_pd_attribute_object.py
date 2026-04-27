from __future__ import annotations

# Upstream PDFBox 3.0.x ships ``PDAttributeObject`` without a dedicated
# ``PDAttributeObjectTest.java`` in
# ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/documentinterchange/
# logicalstructure/``. The class is exercised indirectly via the
# ``Revisions`` round-trip tests on ``PDStructureElement`` and through
# tagged-PDF integration fixtures.
#
# Behavior parity is covered by ``test_pd_attribute_object_parity.py``;
# this stub keeps the upstream-test directory layout aligned with PRD
# §12 conventions.

import pytest

pytest.skip(
    "no standalone upstream PDAttributeObjectTest.java — behaviour "
    "covered by Revisions round-trip tests upstream and by the "
    "hand-written parity suite in this directory",
    allow_module_level=True,
)
