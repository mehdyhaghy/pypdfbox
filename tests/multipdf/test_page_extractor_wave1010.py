from __future__ import annotations

from tests.multipdf.test_page_extractor_wave369 import _InfoSource


def test_wave1010_info_source_reports_empty_page_count() -> None:
    assert _InfoSource(object()).get_number_of_pages() == 0
