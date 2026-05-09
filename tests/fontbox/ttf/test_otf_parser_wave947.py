from __future__ import annotations

import builtins
from typing import Any

import pytest

from . import test_otf_parser as otf_tests


def test_wave947_synthesize_minimal_otf_skips_when_fontbuilder_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def fake_import(
        name: str,
        globals_: dict[str, object] | None = None,
        locals_: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name == "fontTools.fontBuilder":
            raise ImportError("no FontBuilder")
        return original_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(pytest.skip.Exception, match="FontBuilder not available"):
        otf_tests._synthesize_minimal_otf()

