from __future__ import annotations

from collections.abc import Callable
from types import FrameType

from tests.fontbox import test_encoding_helpers_wave953


def test_wave1200_nonmatching_local_target_body_is_callable() -> None:
    captured: list[Callable[[], None]] = []
    test_func = (
        test_encoding_helpers_wave953
        .test_wave953_local_class_capture_tracer_ignores_nonmatching_frames
    )

    def tracer(frame: FrameType, event: str, arg: object) -> object:
        if frame.f_code is test_func.__code__ and event == "line":
            local_value = frame.f_locals.get("target")
            if callable(local_value) and not captured:
                captured.append(local_value)
        return tracer

    import sys

    old_trace = sys.gettrace()
    sys.settrace(tracer)
    try:
        test_func()
    finally:
        sys.settrace(old_trace)

    assert captured
    assert captured[0]() is None
