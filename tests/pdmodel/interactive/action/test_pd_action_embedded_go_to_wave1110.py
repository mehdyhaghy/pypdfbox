from __future__ import annotations

import sys
from typing import Any

from tests.pdmodel.interactive.action.test_pd_action_embedded_go_to_wave539 import (
    test_wave539_resolve_named_destination_uses_names_dests_get_destination as _target_test,
)


def test_wave1110_invokes_wave539_catalog_get_dests_none_helper() -> None:
    captured: dict[str, Any] = {}

    def capture_catalog(frame: Any, event: str, arg: object) -> None:
        if event == "return" and frame.f_code is _target_test.__code__:
            captured["catalog_cls"] = frame.f_locals["Catalog"]

    previous_profile = sys.getprofile()
    sys.setprofile(capture_catalog)
    try:
        _target_test()
    finally:
        sys.setprofile(previous_profile)

    assert captured["catalog_cls"]().get_dests() is None
