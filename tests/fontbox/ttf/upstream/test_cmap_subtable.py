"""Ported from ``fontbox/src/test/java/org/apache/fontbox/ttf/TestCMapSubtable.java``.

Both upstream cases require font binaries that PDFBox's Maven build
downloads on demand into ``target/fonts``. The fonts are **not** part of
the Apache-2.0-licensed source tree and we cannot redistribute them
under pypdfbox's Apache-2.0 license:

* ``NotoSansSC-Regular.otf`` (PDFBOX-5328) — Noto Sans SC ships under the
  SIL Open Font License 1.1 (incompatible with re-licensing under
  Apache-2.0; we'd have to ship a separate LICENSE/NOTICE per font).
  Upstream pulls it from
  ``https://issues.apache.org/jira/secure/attachment/13036376/NotoSansSC-Regular.otf``
  at build time (see ``fontbox/pom.xml``).
* ``ipag.ttf`` (PDFBOX-4106) — distributed under the IPA Font License,
  which permits redistribution only as the original archive (not as a
  single file extracted out of ``ipag00303.zip``). Upstream downloads it
  from ``https://moji.or.jp/wp-content/ipafont/IPAfont/ipag00303.zip``.

Both fixtures stay out of the repository. The skip reasons below name the
licensing blocker so future audits don't re-open this question. Synthetic
equivalents covering the same code paths live in
``tests/fontbox/ttf/test_cmap_subtable.py``
(see ``test_format_6_multiple_char_codes_to_same_glyph_returns_sorted_list``
which exercises the same multi-encoding ``get_char_codes`` path that the
PDFBOX-5328 test pins down).
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="PDFBOX-5328 needs NotoSansSC-Regular.otf (SIL OFL 1.1) — "
    "cannot redistribute under Apache-2.0; upstream downloads it at "
    "build time, see fontbox/pom.xml"
)
def test_pdfbox_5328() -> None:
    """Multiple character codes must resolve to the same gid (PDFBox-5328).

    Ported from ``TestCMapSubtable#testPDFBox5328()``.
    """


@pytest.mark.skip(
    reason="PDFBOX-4106 needs ipag.ttf (IPA Font License — archive-only "
    "redistribution); upstream downloads ipag00303.zip at build time, "
    "see fontbox/pom.xml"
)
def test_vertical_substitution() -> None:
    """Vertical substitution flips selected gids (PDFBox-4106).

    Ported from ``TestCMapSubtable#testVerticalSubstitution()``.
    """
