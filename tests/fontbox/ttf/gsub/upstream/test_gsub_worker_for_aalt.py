"""Port of upstream ``GsubWorkerForAaltTest`` from
``fontbox/src/test/java/org/apache/fontbox/ttf/gsub/GsubWorkerForAaltTest.java``.

Wave 1375 ported :class:`GsubWorkerForAALT`. The upstream end-to-end
test still needs the ``FoglihtenNo07.otf`` fixture (custom non-Apache
license, not redistributable); synthetic coverage of the same code
paths lives in ``tests/fontbox/ttf/gsub/test_gsub_worker_for_aalt.py``.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="FoglihtenNo07.otf is not bundled (custom non-Apache "
    "license); GsubWorkerForAALT itself is now ported and covered "
    "synthetically in tests/fontbox/ttf/gsub/test_gsub_worker_for_aalt.py"
)
def test_foglihten_no07() -> None:
    """Ported from ``GsubWorkerForAaltTest#testFoglihtenNo07()``.

    Original asserts the worker maps the GIDs for ``"Abc"`` to
    ``[1139, 1562, 1477]`` via GSUB lookup lists 12/13.
    """
