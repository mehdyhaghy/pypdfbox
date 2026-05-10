"""Ported from ``fontbox/src/test/java/org/apache/fontbox/ttf/TestCMapSubtable.java``.

Both upstream cases require external font binaries (``NotoSansSC-Regular.otf``
and ``ipag.ttf``) that PDFBox downloads into ``target/fonts`` at build time.
We don't ship those fixtures, so the tests are kept here as a skipped record
of the upstream coverage that pypdfbox is meant to satisfy. Hand-written
synthetic equivalents live in ``tests/fontbox/ttf/test_cmap_subtable.py``
(see ``test_format_6_multiple_char_codes_to_same_glyph_returns_sorted_list``
which exercises the same multi-encoding ``get_char_codes`` path that the
PDFBox-5328 test pins down).
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="upstream fixture NotoSansSC-Regular.otf not bundled")
def test_pdfbox_5328() -> None:
    """Multiple character codes must resolve to the same gid (PDFBox-5328).

    Ported from ``TestCMapSubtable#testPDFBox5328()``.
    """


@pytest.mark.skip(reason="upstream fixture ipag.ttf not bundled")
def test_vertical_substitution() -> None:
    """Vertical substitution flips selected gids (PDFBox-4106).

    Ported from ``TestCMapSubtable#testVerticalSubstitution()``.
    """
