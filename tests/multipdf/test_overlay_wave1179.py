from __future__ import annotations

import tests.multipdf.test_overlay_wave639 as wave639


class PageWithoutResources:
    def get_resources(self) -> None:
        return None


def test_xobject_streams_returns_empty_when_page_has_no_resources() -> None:
    assert wave639._xobject_streams(PageWithoutResources()) == []
