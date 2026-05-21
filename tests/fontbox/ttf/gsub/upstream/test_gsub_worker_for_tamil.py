"""Port of upstream ``GsubWorkerForTamilTest`` from
``fontbox/src/test/java/org/apache/fontbox/ttf/gsub/GsubWorkerForTamilTest.java``.

Upstream's test is itself a placeholder — ``testDummy`` only asserts
the factory returns a :class:`DefaultGsubWorker` because no Tamil
shaper was implemented in upstream when the test was written
(``// change to GsubWorkerForTamil when implemented``). Wave 1375 ports
:class:`GsubWorkerForTamil` ahead of upstream; running the original
assertion would now flip from ``DefaultGsubWorker`` to
:class:`GsubWorkerForTamil`, so the upstream test no longer matches our
behaviour at the assertion level. Synthetic coverage of the new worker
lives in ``tests/fontbox/ttf/gsub/test_gsub_worker_for_tamil.py``;
factory dispatch is covered in
``tests/fontbox/ttf/gsub/test_gsub_worker_factory.py``.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="Lohit-Tamil.ttf is not bundled (SIL OFL 1.1, not "
    "Apache-2.0 interchangeable); wave 1375 ports GsubWorkerForTamil "
    "ahead of upstream (upstream's testDummy still asserts a "
    "DefaultGsubWorker fallback); factory dispatch + per-worker "
    "behaviour are covered in "
    "tests/fontbox/ttf/gsub/test_gsub_worker_for_tamil.py and "
    "tests/fontbox/ttf/gsub/test_gsub_worker_factory.py"
)
def test_dummy() -> None:
    """Ported from ``GsubWorkerForTamilTest#testDummy()``.

    Original asserts the worker returned by the factory is an instance
    of :class:`DefaultGsubWorker` because no Tamil-specific shaper is
    implemented yet.
    """
