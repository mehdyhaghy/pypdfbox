from __future__ import annotations

import pytest

# PDFBox 3.0 ships PDObjectReference (logical structure / OBJR dictionary)
# but does NOT include a standalone PDObjectReferenceTest.java — the class
# is exercised indirectly through PDStructureElement round-trips. Behavior
# parity is covered by our hand-written suite in
# ``test_pd_object_reference.py`` (alongside the OBJR wiring tests in
# ``test_pd_structure_element.py``).
#
# Re-verified wave 1296 against upstream 3.0 branch HEAD ``e48bce8``:
# ``find /tmp/pdfbox -name "*PDObjectReference*Test*.java"`` still
# returns no results.

pytest.skip(
    "no upstream PDObjectReferenceTest.java — exercised via "
    "PDStructureElement round-trip tests upstream; covered by hand-written "
    "tests in this directory",
    allow_module_level=True,
)
