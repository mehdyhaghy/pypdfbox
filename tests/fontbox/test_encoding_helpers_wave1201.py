from __future__ import annotations

import sys
from collections.abc import Callable
from types import FrameType
from typing import cast

import pytest

from tests.fontbox import test_encoding_helpers_wave953, test_encoding_helpers_wave1200


def test_wave1201_wave1200_tracer_records_matching_target() -> None:
    test_func = (
        test_encoding_helpers_wave953
        .test_wave953_local_class_capture_tracer_ignores_nonmatching_frames
    )
    inner_tracers: list[Callable[[FrameType, str, object], object]] = []

    class StopCapture(Exception):
        pass

    def capture_tracer(frame: FrameType, event: str, arg: object) -> object:
        if (
            frame.f_code
            is test_encoding_helpers_wave1200
            .test_wave1200_nonmatching_local_target_body_is_callable.__code__
            and event == "line"
            and callable(frame.f_locals.get("tracer"))
        ):
            inner_tracers.append(frame.f_locals["tracer"])
            raise StopCapture
        return capture_tracer

    old_trace = sys.gettrace()
    sys.settrace(capture_tracer)
    try:
        with pytest.raises(StopCapture):
            (
                test_encoding_helpers_wave1200
                .test_wave1200_nonmatching_local_target_body_is_callable()
            )
    finally:
        sys.settrace(old_trace)

    recorded: list[Callable[[], None]] = []

    def target() -> None:
        recorded.append(target)

    class MatchingFrame:
        f_code = test_func.__code__
        f_locals = {"target": target}

    assert inner_tracers
    assert inner_tracers[0](cast(FrameType, MatchingFrame()), "line", None) is (
        inner_tracers[0]
    )
    closure = dict(
        zip(
            inner_tracers[0].__code__.co_freevars,
            inner_tracers[0].__closure__ or (),
            strict=True,
        ),
    )
    assert closure["captured"].cell_contents == [target]
