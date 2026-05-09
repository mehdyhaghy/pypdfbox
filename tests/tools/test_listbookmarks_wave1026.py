from __future__ import annotations

import tests.tools.test_listbookmarks_wave666 as wave666


def test_wave1026_other_destination_exposes_cos_object() -> None:
    assert wave666._OtherDestination().get_cos_object() is not None  # noqa: SLF001
