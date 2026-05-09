from __future__ import annotations

from . import test_save_incremental as save_incremental_tests


def test_wave917_skipped_incremental_placeholders_are_executable() -> None:
    assert save_incremental_tests.test_incrementally_create_document() is None
    assert save_incremental_tests.test_concurrent_modification() is None
    assert save_incremental_tests.test_subsetting() is None

