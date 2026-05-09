from __future__ import annotations

import sys
from collections.abc import Callable
from types import FrameType
from typing import cast

from tests.fontbox import test_encoding_helpers_wave1201, test_encoding_helpers_wave1211


def test_wave1232_wave1211_local_capture_records_first_matching_tracer() -> None:
    captured_local_captures: list[Callable[[FrameType, str, object], object]] = []
    target_code = (
        test_encoding_helpers_wave1211
        .test_wave1211_wave1201_capture_tracer_branches_and_target_body.__code__
    )

    def capture_wave1211_local_capture(
        frame: FrameType,
        event: str,
        arg: object,
    ) -> object:
        if frame.f_code is target_code:
            local_capture = frame.f_locals.get("local_capture")
            if callable(local_capture) and not captured_local_captures:
                captured_local_captures.append(local_capture)
        return capture_wave1211_local_capture

    old_trace = sys.gettrace()
    sys.settrace(capture_wave1211_local_capture)
    try:
        (
            test_encoding_helpers_wave1211
            .test_wave1211_wave1201_capture_tracer_branches_and_target_body()
        )
    finally:
        sys.settrace(old_trace)

    captured_tracers: list[Callable[[FrameType, str, object], object]] = []

    def sentinel_tracer(frame: FrameType, event: str, arg: object) -> object:
        return sentinel_tracer

    class MatchingWave1201Frame:
        f_code = (
            test_encoding_helpers_wave1201
            .test_wave1201_wave1200_tracer_records_matching_target.__code__
        )
        f_locals = {"capture_tracer": sentinel_tracer}

    assert captured_local_captures
    local_capture = captured_local_captures[0]
    closure = dict(
        zip(
            local_capture.__code__.co_freevars,
            local_capture.__closure__ or (),
            strict=True,
        ),
    )
    captured_tracers = closure["captured_tracers"].cell_contents
    captured_tracers.clear()

    assert local_capture(cast(FrameType, MatchingWave1201Frame()), "line", None) is (
        local_capture
    )
    assert captured_tracers == [sentinel_tracer]
