from __future__ import annotations

import builtins

import pytest

from . import test_otf_parser_wave947 as wave947


def test_wave1195_wave947_import_hook_delegates_non_fontbuilder_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def synthesize_with_unrelated_import() -> bytes:
        builtins.__import__("math")
        pytest.skip("FontBuilder not available")

    monkeypatch.setattr(
        wave947.otf_tests,
        "_synthesize_minimal_otf",
        synthesize_with_unrelated_import,
    )

    wave947.test_wave947_synthesize_minimal_otf_skips_when_fontbuilder_missing(
        monkeypatch,
    )
