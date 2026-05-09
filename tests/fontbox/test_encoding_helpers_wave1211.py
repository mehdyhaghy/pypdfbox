from __future__ import annotations

import sys
from collections.abc import Callable
from types import FrameType
from typing import cast

import pytest

from tests.fontbox import test_encoding_helpers_wave1200, test_encoding_helpers_wave1201


def test_wave1211_wave1201_capture_tracer_branches_and_target_body() -> None:
    captured_tracers: list[Callable[[FrameType, str, object], object]] = []
    captured_targets: list[Callable[[], None]] = []
    stop_capture_types: list[type[BaseException]] = []

    def local_capture(frame: FrameType, event: str, arg: object) -> object:
        target_code = (
            test_encoding_helpers_wave1201
            .test_wave1201_wave1200_tracer_records_matching_target.__code__
        )
        if frame.f_code is target_code:
            local_tracer = frame.f_locals.get("capture_tracer")
            if callable(local_tracer) and not captured_tracers:
                captured_tracers.append(local_tracer)

            local_stop = frame.f_locals.get("StopCapture")
            if isinstance(local_stop, type) and issubclass(local_stop, BaseException):
                stop_capture_types.append(local_stop)

            local_target = frame.f_locals.get("target")
            if callable(local_target) and not captured_targets:
                captured_targets.append(local_target)
        return local_capture

    old_trace = sys.gettrace()
    sys.settrace(local_capture)
    try:
        test_encoding_helpers_wave1201.test_wave1201_wave1200_tracer_records_matching_target()
    finally:
        sys.settrace(old_trace)

    assert captured_tracers
    assert stop_capture_types
    assert captured_targets

    class MatchingWave1200Frame:
        f_code = (
            test_encoding_helpers_wave1200
            .test_wave1200_nonmatching_local_target_body_is_callable.__code__
        )
        f_locals = {"tracer": captured_tracers[0]}

    with pytest.raises(stop_capture_types[0]):
        captured_tracers[0](cast(FrameType, MatchingWave1200Frame()), "line", None)

    class NonmatchingFrame:
        f_code = test_wave1211_wave1201_capture_tracer_branches_and_target_body.__code__
        f_locals: dict[str, object] = {}

    assert captured_tracers[0](cast(FrameType, NonmatchingFrame()), "line", None) is (
        captured_tracers[0]
    )
    captured_targets[0]()
