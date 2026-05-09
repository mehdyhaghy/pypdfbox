from __future__ import annotations

from tests.tools.test_listbookmarks_wave445 import _OtherDestination


def test_wave1027_other_destination_cos_object_returns_object() -> None:
    assert _OtherDestination().get_cos_object() is not None
