"""Tests ported from PDFBox 3.0 ``PDFMergerUtilityTest`` (structure-tree slice).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/multipdf/PDFMergerUtilityTest.java``
on the apache/pdfbox 3.0 branch.

This file holds traceability records for the upstream
``testStructureTreeMerge*`` methods and adjacent structural-merge
regressions that are **not** yet bundled with executable fixtures.
``test_pdf_merger_utility.py`` covers the structural surface that can
be exercised against in-memory synthetic documents; the entries below
mirror the upstream test class for cross-reference, declaring why each
is skipped.

Upstream's ``ElementCounter`` walker and its private
``checkWithNumberTree`` / ``checkForPageOrphans`` / ``checkStructTreeRootCount``
helpers are not ported here — they only matter inside the skipped
tests, and re-creating them without exercising the corresponding
fixtures would just be dead code.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="needs target/pdfs/PDFBOX-3999-GeneralForbearance.pdf "
    "(Maven-downloaded JIRA-attachment corpus, not in upstream source tree)"
)
def test_structure_tree_merge() -> None:
    """Port placeholder for ``testStructureTreeMerge`` (PDFBOX-3999)."""


@pytest.mark.skip(
    reason="needs target/pdfs/PDFBOX-3999-GeneralForbearance.pdf "
    "(Maven-downloaded JIRA-attachment corpus, not in upstream source tree)"
)
def test_structure_tree_merge_2() -> None:
    """Port placeholder for ``testStructureTreeMerge2`` (PDFBOX-3999 flatten variant)."""


@pytest.mark.skip(
    reason="needs target/pdfs/PDFBOX-4408.pdf "
    "(Maven-downloaded JIRA-attachment corpus, not in upstream source tree)"
)
def test_structure_tree_merge_3() -> None:
    """Port placeholder for ``testStructureTreeMerge3`` (PDFBOX-4408)."""


# ``testStructureTreeMerge4`` is fully ported in
# :mod:`tests.multipdf.upstream.test_pdf_merger_utility_struct_tree_4`
# (the PDFBOX-4417-001031.pdf fixture is bundled in-tree).


# ``testStructureTreeMerge5`` is fully ported in
# :mod:`tests.multipdf.upstream.test_pdf_merger_utility_struct_tree_4`
# (the PDFBOX-4417-054080.pdf fixture is bundled in-tree).


@pytest.mark.skip(
    reason="needs target/pdfs/PDFBOX-4418-000314.pdf "
    "(Maven-downloaded JIRA-attachment corpus, not in upstream source tree)"
)
def test_structure_tree_merge_6() -> None:
    """Port placeholder for ``testStructureTreeMerge6`` (PDFBOX-4418 ParentTree)."""


@pytest.mark.skip(
    reason="needs target/pdfs/PDFBOX-4423.pdf "
    "(Maven-downloaded JIRA-attachment corpus, not in upstream source tree)"
)
def test_structure_tree_merge_7() -> None:
    """Port placeholder for ``testStructureTreeMerge7`` (PDFBOX-4423)."""


@pytest.mark.skip(
    reason="needs target/pdfs/PDFBOX-4418-000314.pdf "
    "(Maven-downloaded JIRA-attachment corpus, not in upstream source tree)"
)
def test_missing_parent_tree_next_key() -> None:
    """Port placeholder for ``testMissingParentTreeNextKey`` (PDFBOX-4009)."""


# ``testStructureTreeMergeIDTree`` is fully ported in
# :mod:`tests.multipdf.upstream.test_pdf_merger_utility_struct_tree_4`
# (both PDFBOX-4417-001031.pdf and PDFBOX-4417-054080.pdf fixtures
# are bundled in-tree).
