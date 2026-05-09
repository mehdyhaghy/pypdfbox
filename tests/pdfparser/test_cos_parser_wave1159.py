from __future__ import annotations

import builtins
from collections.abc import Callable
from typing import Any

from pypdfbox.io import RandomAccessReadBuffer
from tests.pdfparser import test_cos_parser_wave683 as wave683


def test_wave1159_bad_reference_keyword_helper_falls_back_for_other_keywords(
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
        if name == "ParserWithBadReferenceKeyword":
            captured[name] = cls
        return cls

    monkeypatch.setattr(builtins, "__build_class__", capture_build_class)

    wave683.test_wave683_indirect_reference_lookahead_rewinds_on_bad_r_keyword()
    parser = captured["ParserWithBadReferenceKeyword"](
        RandomAccessReadBuffer(b"Name ")
    )

    assert parser.read_keyword() == b"Name"
