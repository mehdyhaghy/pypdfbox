from __future__ import annotations

import pytest

# Upstream PDFBox 3.0 has no standalone PDStructureClassMap class — the
# ClassMap is handled inline on PDStructureTreeRoot.{getClassMap,setClassMap}.
# No PDStructureClassMapTest.java exists upstream; behavior is exercised via
# our hand-written tests in ``test_pd_structure_class_map.py`` and the
# ``ClassMap`` round-trip tests in ``test_pd_structure_tree_root_parity.py``.

pytest.skip(
    "no upstream PDStructureClassMapTest.java — class introduced in port",
    allow_module_level=True,
)
