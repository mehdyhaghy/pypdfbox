from __future__ import annotations

import builtins

import pytest

from tests.fontbox.ttf import test_open_type_font_wave883 as wave883


def test_wave1196_wave883_import_hook_delegates_non_fontbuilder_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def synthesize_with_unrelated_import() -> bytes:
        builtins.__import__("math")
        pytest.skip("font builder still unavailable")

    monkeypatch.setattr(
        wave883.open_type_mod,
        "_synth_otf_name_keyed",
        synthesize_with_unrelated_import,
    )

    wave883.test_wave883_synth_otf_skips_when_fontbuilder_is_missing(
        monkeypatch,
    )
