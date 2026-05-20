"""Port of upstream ``GsubWorkerForTamilTest`` from
``fontbox/src/test/java/org/apache/fontbox/ttf/gsub/GsubWorkerForTamilTest.java``.

Upstream's test loads ``src/test/resources/ttf/Lohit-Tamil.ttf`` and
asserts the factory returns a :class:`DefaultGsubWorker` (a placeholder
for the future "GsubWorkerForTamil" shaper which upstream has never
shipped — the comment in the Java source reads
``// change to GsubWorkerForTamil when implemented``).

pypdfbox does not bundle Lohit-Tamil.ttf (released under SIL OFL 1.1 —
a Free Font license but not interchangeable with Apache 2.0 source
re-licensing). The factory's Tamil fallback path is already covered
synthetically by ``tests/fontbox/ttf/gsub/test_gsub_worker_factory.py``;
this file exists as the parity placeholder so future re-syncs see the
upstream test mapped.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="Lohit-Tamil.ttf is not bundled (SIL OFL 1.1, not "
    "Apache-2.0 interchangeable); factory fallback to "
    "DefaultGsubWorker is covered synthetically in "
    "tests/fontbox/ttf/gsub/test_gsub_worker_factory.py"
)
def test_dummy() -> None:
    """Ported from ``GsubWorkerForTamilTest#testDummy()``.

    Original asserts the worker returned by the factory is an instance
    of :class:`DefaultGsubWorker` because no Tamil-specific shaper is
    implemented yet.
    """
