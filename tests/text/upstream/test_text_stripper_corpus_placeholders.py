"""Upstream-parity placeholders for the two corpus-driven tests in
``TestTextStripper.java`` that cannot be ported verbatim.

Upstream baseline: PDFBox 3.0.x. Source:
``pdfbox/src/test/java/org/apache/pdfbox/text/TestTextStripper.java``
(lines 559-588 / 590-615).

Both ``testExtract`` and ``testTabula`` are file-driven harnesses that
walk ``src/test/resources/input/`` (or a single PDF file named via the
``org.apache.pdfbox.util.TextStripper.file`` system property) and
line-by-line compare the extracted text against expected-text fixtures.
The fixture tree is large (hundreds of MB of PDFs sourced from JIRA
attachments + the Tabula research corpus) and we deliberately do not
bundle it. The Python-side public API is exercised by ``test_extract``
and ``test_strip_by_outline_items`` in
``tests/text/upstream/test_text_stripper.py`` against the small
self-contained fixtures that *are* bundled.

These two tests are therefore registered as ``pytest.skip`` placeholders
so that re-syncs against future upstream re-runs can spot the gap
without grepping. Once a downstream consumer wants a full PDFBox-corpus
regression run, they can drop the upstream ``src/test/resources/input``
tree into ``tests/fixtures/text/input/`` and the placeholders flip into
live tests with no other code change.
"""
from __future__ import annotations

import pytest


def test_extract() -> None:
    """Mirror of ``TestTextStripper.testExtract`` (line 559).

    Skipped: the upstream test scans every PDF in
    ``src/test/resources/input/`` and compares against per-file
    ``.expected.txt`` fixtures. We do not bundle the corpus.
    """
    pytest.skip(
        "upstream PDFBox input corpus not bundled; testExtract would "
        "require tests/fixtures/text/input/*.pdf + *.expected.txt"
    )


def test_tabula() -> None:
    """Mirror of ``TestTextStripper.testTabula`` (line 590).

    Skipped: requires ``eu-001.pdf`` + ``eu-001.pdf-tabula.txt`` from
    upstream's Tabula research corpus, and the upstream test relies on
    a private ``PDFTabulaTextStripper`` subclass that overrides
    ``computeFontHeight`` to defend against malformed font bounding
    boxes (PDFBOX-2158 / PDFBOX-3130). The override hook is in scope
    for pypdfbox's ``PDFTextStripper.compute_font_height``; once the
    corpus is bundled this placeholder flips to a live test.
    """
    pytest.skip(
        "upstream PDFBox tabula corpus not bundled; testTabula "
        "requires tests/fixtures/text/input/eu-001.pdf + "
        "eu-001.pdf-tabula.txt"
    )
