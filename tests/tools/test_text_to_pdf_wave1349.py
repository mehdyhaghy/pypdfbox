"""Wave 1349 coverage-boost tests for ``pypdfbox.tools.text_to_pdf``.

Targets:

* Line 161 — default-font factory branch (no font preloaded).
* Line 211 — form-feed embedded inside the *next* word during the
  look-ahead width calculation.
* Line 233 — defensive raise when ``content_stream`` is unexpectedly
  ``None``; reachable by forcing ``bottom_margin`` so far negative that
  the page-creation branch is skipped on the first iteration.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.tools.text_to_pdf import TextToPDF


def test_create_pdf_from_text_uses_default_font_factory_when_unset() -> None:
    """Line 161 — when ``self.font`` is ``None``, the standard-14
    factory installs a usable default. Round-trip verifies a page was
    drawn without the caller pre-loading a font."""
    t = TextToPDF()
    assert t.font is None
    doc = PDDocument()
    try:
        t.create_pdf_from_text(doc, "hello default font")
        assert doc.get_number_of_pages() == 1
        # The factory wired up a real font on ``self``.
        assert t.font is not None
    finally:
        doc.close()


def test_create_pdf_from_text_form_feed_inside_next_word_trims_lookahead() -> None:
    """Line 211 — the look-ahead width calculation discovers a
    form-feed embedded in the *next* word and trims it before
    measuring. Input ``"a \\fb"`` splits into ``["a", "\\fb"]``; while
    processing word 0, the lookahead at word 1 hits this branch."""
    t = TextToPDF()
    doc = PDDocument()
    try:
        t.create_pdf_from_text(doc, "a \fb")
        # The form-feed forces an extra page; the lookahead branch
        # runs along the way without raising.
        assert doc.get_number_of_pages() >= 2
    finally:
        doc.close()


def test_create_pdf_from_text_raises_when_content_stream_skipped() -> None:
    """Line 233 — make ``y - line_height < bottom_margin`` false on
    the first iteration by giving ``bottom_margin`` an extreme
    negative value. ``content_stream`` then stays ``None`` and the
    defensive ``OSError`` fires."""
    t = TextToPDF()
    t.bottom_margin = -10_000.0
    doc = PDDocument()
    try:
        with pytest.raises(OSError, match="non-null content stream"):
            t.create_pdf_from_text(doc, "hello")
    finally:
        doc.close()
