"""Port of upstream ``GsubWorkerForSmcpTest`` from
``fontbox/src/test/java/org/apache/fontbox/ttf/gsub/GsubWorkerForSmcpTest.java``.

Wave 1375 ported :class:`GsubWorkerForSMCP`. The upstream end-to-end
test is platform-gated to ``c:/windows/fonts/calibri.ttf`` via
``Assumptions.assumeTrue(file.exists(), ...)`` — Calibri is proprietary
Microsoft Office content and cannot be redistributed; synthetic
coverage of the same code paths lives in
``tests/fontbox/ttf/gsub/test_gsub_worker_for_smcp.py``.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="Calibri is not redistributable (proprietary Microsoft "
    "Office content; upstream gates this case on a Windows-only "
    "system path); GsubWorkerForSMCP itself is now ported and "
    "covered synthetically in "
    "tests/fontbox/ttf/gsub/test_gsub_worker_for_smcp.py"
)
def test_calibri() -> None:
    """Ported from ``GsubWorkerForSmcpTest#testCalibri()``.

    Original asserts the worker decomposes the ``ﬀ`` ligature glyph
    via the "smcp" feature into ``[165, 165]`` (small-capital F twice)
    after lookup list 24 fires.
    """
