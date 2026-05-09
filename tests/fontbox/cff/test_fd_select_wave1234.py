from __future__ import annotations

from collections.abc import Callable
from types import FrameType
from typing import cast

import pytest

from tests.fontbox.cff import test_fd_select_wave1214 as wave1214

TraceFunc = Callable[[FrameType, str, object], object]


def test_wave1234_wave1214_trace_helper_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    installed_trace: TraceFunc | None = None

    def fake_settrace(trace_func: TraceFunc | None) -> None:
        nonlocal installed_trace
        if trace_func is not None and installed_trace is None:
            installed_trace = trace_func

    def fake_target() -> None:
        class _MalformedLength:
            def __getitem__(self, gid: int) -> int:
                assert gid == 0
                return 1

        class NonmatchingFrame:
            f_code = fake_settrace.__code__
            f_lineno = 0
            f_locals: dict[str, object] = {}

        class MatchingFrame:
            f_code = fake_target.__code__
            f_lineno = 53
            f_locals = {"_MalformedLength": _MalformedLength}

        assert installed_trace is not None
        assert installed_trace(cast(FrameType, NonmatchingFrame()), "line", None) is (
            installed_trace
        )
        assert installed_trace(cast(FrameType, MatchingFrame()), "line", None) is None

    monkeypatch.setattr(wave1214.sys, "settrace", fake_settrace)
    monkeypatch.setattr(
        wave1214.fd_select_mod,
        "test_wrapped_fdselect_malformed_len_falls_back_to_zero",
        fake_target,
    )

    wave1214.test_wave1214_malformed_length_getitem_body_is_reachable()
