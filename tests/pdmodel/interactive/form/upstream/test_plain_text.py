"""Upstream port of ``PlainTextTest``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/PlainTextTest.java``
(PDFBox 3.0.x).

Upstream imports ``org.apache.pdfbox.pdmodel.interactive.PlainText``. In
pypdfbox the same class lives at
``pypdfbox.pdmodel.interactive.form.plain_text`` — the only structural
divergence vs upstream is the package path; behaviour mirrors upstream.
"""

from __future__ import annotations

from pypdfbox.pdmodel.interactive.form.plain_text import PlainText


def test_character_cr() -> None:
    """Upstream: ``characterCR``."""
    text = PlainText("CR\rCR")
    assert len(text.get_paragraphs()) == 2


def test_character_lf() -> None:
    """Upstream: ``characterLF``."""
    text = PlainText("LF\nLF")
    assert len(text.get_paragraphs()) == 2


def test_character_crlf() -> None:
    """Upstream: ``characterCRLF``."""
    text = PlainText("CRLF\r\nCRLF")
    assert len(text.get_paragraphs()) == 2


def test_character_lfcr() -> None:
    """Upstream: ``characterLFCR``."""
    text = PlainText("LFCR\n\rLFCR")
    assert len(text.get_paragraphs()) == 3


def test_character_unicode_linebreak() -> None:
    """Upstream: ``characterUnicodeLinebreak``."""
    text = PlainText("linebreak linebreak")
    assert len(text.get_paragraphs()) == 2


def test_character_unicode_paragraphbreak() -> None:
    """Upstream: ``characterUnicodeParagraphbreak``."""
    text = PlainText("paragraphbreak paragraphbreak")
    assert len(text.get_paragraphs()) == 2
