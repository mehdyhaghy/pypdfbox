"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSIncrement.java

Upstream lives under ``cos/`` (not ``pdfwriter/``) but the surface it
exercises — ``saveIncremental`` — belongs to the writer cluster, so we
mirror it here.

Every upstream test in this file requires infrastructure that pypdfbox
does not yet ship:

- ``testIncrementallyCreateDocument`` exercises ``PDDocument`` + ``PDPage``
  + ``PDPageContentStream`` + ``PDImageXObject`` + ``PDAnnotationText``.
- ``testConcurrentModification`` requires a network-fetched fixture PDF
  plus security-removal flow.
- ``testSubsetting`` requires Type0 / TrueType font subsetting.

All three are skipped here. The hand-written incremental tests in
``test_cos_writer_incremental.py`` cover the bytes-level contracts
(byte-prefix preservation, ``/Prev`` chain, ``/Size``, ``/ID``) that
``saveIncremental`` upstream guarantees.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="needs PDDocument + PDPageContentStream + image / annotation pdmodel"
)
def test_incrementally_create_document() -> None:
    pass


@pytest.mark.skip(
    reason="needs network-fetched PDFBOX-5263 fixture + setAllSecurityToBeRemoved"
)
def test_concurrent_modification() -> None:
    pass


@pytest.mark.skip(reason="needs PDType0Font subsetting (fontbox + pdmodel)")
def test_subsetting() -> None:
    pass
