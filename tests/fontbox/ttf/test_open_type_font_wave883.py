from __future__ import annotations

import builtins
from collections.abc import Callable
from types import ModuleType
from typing import Any

import pytest

from tests.fontbox.ttf import test_open_type_font as open_type_mod


class _MissingFixture:
    def exists(self) -> bool:
        return False


def test_wave883_synth_otf_skips_when_fontbuilder_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def fake_import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> ModuleType:
        if name == "fontTools.fontBuilder" and fromlist == ("FontBuilder",):
            raise ImportError("no font builder")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(pytest.skip.Exception):
        open_type_mod._synth_otf_name_keyed()  # noqa: SLF001


@pytest.mark.parametrize(
    "test_func",
    [
        open_type_mod.test_is_supported_otf_false_when_no_cff,
        open_type_mod.test_get_cff_returns_none_when_no_cff_table,
        open_type_mod.test_has_layout_tables_true_when_gsub_present,
    ],
)
def test_wave883_fixture_dependent_tests_skip_when_ttf_fixture_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    test_func: Callable[[], None],
) -> None:
    monkeypatch.setattr(open_type_mod, "FIXTURE_TTF", _MissingFixture())

    with pytest.raises(pytest.skip.Exception):
        test_func()
