"""Upstream-ported placeholder for splitter signature handling.

Apache PDFBox 3.0 has no dedicated ``SplitterSignatureTest.java`` —
upstream coverage for "split a signed document" lives in
``PDFMergerUtilityTest.java`` (testParentTreeMerge / testStructureTree*
fixtures plus signed-PDF assets we don't carry yet).

The relevant upstream behaviour we mirror:

- :class:`Splitter` does not whitelist ``/AcroForm`` in
  ``createNewDocument``, so signature-bearing forms naturally don't
  propagate to chunks.
- Defensive widget-level filtering: signature widgets carried on a
  page's ``/Annots`` array are dropped because their
  ``/V /ByteRange`` would no longer be valid in a chunk.

Hand-written coverage lives in
:mod:`tests.multipdf.test_splitter_signatures`.
"""
from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason=(
        "Upstream has no SplitterSignatureTest.java; signature-related "
        "splitter coverage lives in tests/multipdf/test_splitter_signatures.py"
    )
)
def test_upstream_splitter_signature_test_class_does_not_exist() -> None:
    pass
