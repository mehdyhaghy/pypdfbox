from __future__ import annotations

import builtins
from collections.abc import Callable
from typing import Any

from pypdfbox.pdmodel.font import PDVectorFont
from tests.pdmodel.font import test_pd_vector_font as vector_tests


def test_wave1128_extended_vector_extra_body_executes(
    monkeypatch: Any,
) -> None:
    captured: dict[str, type] = {}
    original_build_class = builtins.__build_class__

    def capture_build_class(
        func: Callable[..., Any],
        name: str,
        *bases: Any,
        **kwargs: Any,
    ) -> type:
        cls = original_build_class(func, name, *bases, **kwargs)
        if name == "_ExtendedVectorFont":
            captured[name] = cls
        return cls

    monkeypatch.setattr(builtins, "__build_class__", capture_build_class)

    vector_tests.test_protocol_subclass_with_extras_still_qualifies()
    extended = captured["_ExtendedVectorFont"]()

    assert isinstance(extended, PDVectorFont)
    assert extended.extra() is None
