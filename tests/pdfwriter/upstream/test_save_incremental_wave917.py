"""Wave 917 originally pinned that the upstream stubs were callable
empty placeholders. With the Wave 1287 unskip round those placeholders
are now real ports (``test_incrementally_create_document`` and
``test_subsetting`` run against synthetic inputs; ``test_concurrent_
modification`` still requires a network-fetched fixture). The original
contract — "calling these returns ``None`` because they have no body" —
no longer applies, so this wave's assertion is left as a no-op
provenance marker.
"""

from __future__ import annotations


def test_wave917_skipped_incremental_placeholders_are_executable() -> None:
    # Provenance marker: see test_save_incremental.py for the live ports.
    from . import test_save_incremental as save_incremental_tests

    assert save_incremental_tests.test_incrementally_create_document is not None
    assert save_incremental_tests.test_concurrent_modification is not None
    assert save_incremental_tests.test_subsetting is not None
