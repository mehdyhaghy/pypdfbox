"""Port of upstream ``GsubWorkerForSmcpTest`` from
``fontbox/src/test/java/org/apache/fontbox/ttf/gsub/GsubWorkerForSmcpTest.java``.

The upstream test is platform-gated to ``c:/windows/fonts/calibri.ttf``
via ``Assumptions.assumeTrue(file.exists(), ...)`` — it only runs on a
Windows machine that ships Calibri. We mirror the skip with
:func:`pytest.skip`, since:

1. pypdfbox does not port the upstream ``GsubWorkerForSmcp`` worker
   (the "smcp" Type 2 multiple-substitution shaper, "ﬀ → F F" small
   capitals). The factory falls back to :class:`DefaultGsubWorker` for
   fonts that lack an explicit Latin / Bengali / Devanagari / Gujarati
   / DFLT worker match.
2. ``calibri.ttf`` is proprietary Microsoft Office content and cannot
   be redistributed under pypdfbox's Apache-2.0 licence.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="GsubWorkerForSmcp is not ported (small-caps multiple "
    "substitution out of scope) and Calibri is not redistributable."
)
def test_calibri() -> None:
    """Ported from ``GsubWorkerForSmcpTest#testCalibri()``.

    Original asserts the worker decomposes the ``ﬀ`` ligature glyph
    via the "smcp" feature into ``[165, 165]`` (small-capital F twice)
    after lookup list 24 fires.
    """
