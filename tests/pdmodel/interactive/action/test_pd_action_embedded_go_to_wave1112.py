from __future__ import annotations

from typing import Any

import pytest

from tests.pdmodel.interactive.action import (
    test_pd_action_embedded_go_to_wave1110 as wave1110,
)


def test_wave1112_wave1110_profile_callback_captures_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Catalog:
        def get_dests(self) -> None:
            return None

    class Frame:
        f_code = wave1110._target_test.__code__
        f_locals = {"Catalog": Catalog}

    def setprofile(profile: Any) -> None:
        if profile is not None:
            profile(Frame(), "return", None)

    monkeypatch.setattr(wave1110.sys, "setprofile", setprofile)

    wave1110.test_wave1110_invokes_wave539_catalog_get_dests_none_helper()
