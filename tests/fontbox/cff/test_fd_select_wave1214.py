from __future__ import annotations

import sys
from collections.abc import Callable
from types import FrameType

from tests.fontbox.cff import test_fd_select_wave294 as fd_select_mod


def test_wave1214_malformed_length_getitem_body_is_reachable() -> None:
    captured: dict[str, type[object]] = {}
    target = fd_select_mod.test_wrapped_fdselect_malformed_len_falls_back_to_zero
    # Fire the trace only once the ``_MalformedLength`` class body has finished
    # executing (i.e. the local is bound). Keying off the function's own first
    # line + an offset makes this robust to edits elsewhere in the module that
    # shift absolute line numbers (the local is bound ~10 lines into the body).
    bind_line = target.__code__.co_firstlineno + 10

    def trace(frame: FrameType, event: str, arg: object) -> Callable[..., object] | None:
        del arg
        if (
            event == "line"
            and frame.f_code is target.__code__
            and frame.f_lineno >= bind_line
        ):
            malformed = frame.f_locals["_MalformedLength"]
            captured["class"] = malformed
            assert malformed().__getitem__(0) == 1
            return None
        return trace

    previous_trace = sys.gettrace()
    sys.settrace(trace)
    try:
        target()
    finally:
        sys.settrace(previous_trace)

    assert captured["class"]().__getitem__(0) == 1
