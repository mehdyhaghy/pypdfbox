from __future__ import annotations

import pytest

# Upstream PDFBox 3.0 has no standalone PDStructureClassMap class — the
# ClassMap is handled inline on PDStructureTreeRoot.{getClassMap,setClassMap}.
# No PDStructureClassMapTest.java exists upstream; behavior is exercised via
# our hand-written tests in ``test_pd_structure_class_map.py`` and the
# ``ClassMap`` round-trip tests in ``test_pd_structure_tree_root_parity.py``.
#
# Re-verified wave 1296 against upstream 3.0 branch HEAD ``e48bce8``:
# ``find /tmp/pdfbox -name "*PDStructureClassMap*.java"`` still returns no
# results (no class, no test).

pytest.skip(
    "no upstream PDStructureClassMapTest.java — class introduced in port",
    allow_module_level=True,
)
