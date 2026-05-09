from __future__ import annotations

from tests.cos.upstream import test_cos_update_info as target


def test_wave1223_executes_skipped_cos_update_info_body() -> None:
    target.test_is_set_need_to_be_update()
