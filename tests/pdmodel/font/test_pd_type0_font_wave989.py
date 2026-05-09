from __future__ import annotations

from tests.pdmodel.font.test_pd_type0_font_wave487 import _Descendant


def test_wave989_descendant_cid_to_gid_records_call() -> None:
    descendant = _Descendant()

    assert descendant.cid_to_gid(23) == 1023
    assert descendant.calls == [("gid", 23)]
