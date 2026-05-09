from __future__ import annotations

from collections.abc import Callable
from typing import cast

from tests.fontbox.cff import test_cff_helper_tail_wave855 as wave855


def test_wave1217_fake_import_delegates_non_fonttools_imports() -> None:
    sentinel = object()
    calls: list[tuple[str, object, object, tuple[object, ...], int]] = []

    def real_import(
        name: str,
        globals_: object = None,
        locals_: object = None,
        fromlist: tuple[object, ...] = (),
        level: int = 0,
    ) -> object:
        calls.append((name, globals_, locals_, fromlist, level))
        return sentinel

    fake_import = cast(Callable[..., object], wave855._raise_fonttools_import(real_import))

    assert fake_import("math", {"g": 1}, {"l": 2}, ("sqrt",), 0) is sentinel
    assert calls == [("math", {"g": 1}, {"l": 2}, ("sqrt",), 0)]
