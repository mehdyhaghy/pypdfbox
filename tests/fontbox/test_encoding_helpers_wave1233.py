from __future__ import annotations

import sys
from collections.abc import Callable
from types import FrameType
from typing import cast

import pytest

from tests.fontbox import test_encoding_helpers_wave1201, test_encoding_helpers_wave1211


def test_wave1233_wave1211_local_capture_records_stop_and_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_settrace = sys.settrace
    captured_local_tracers: list[Callable[[FrameType, str, object], object]] = []

    def fake_settrace(
        tracer: Callable[[FrameType, str, object], object] | None,
    ) -> None:
        tracer_code = getattr(tracer, "__code__", None)
        if (
            callable(tracer)
            and tracer_code
            and tracer_code.co_filename.endswith("test_encoding_helpers_wave1211.py")
        ):
            class StopCapture(Exception):
                pass

            def captured_tracer(frame: FrameType, event: str, arg: object) -> object:
                if event == "line" and callable(frame.f_locals.get("tracer")):
                    raise StopCapture
                return captured_tracer

            def target() -> None:
                return None

            class Wave1201Frame:
                f_code = (
                    test_encoding_helpers_wave1201
                    .test_wave1201_wave1200_tracer_records_matching_target.__code__
                )
                f_locals = {
                    "capture_tracer": captured_tracer,
                    "StopCapture": StopCapture,
                    "target": target,
                }

            assert tracer(cast(FrameType, Wave1201Frame()), "line", None) is tracer
            captured_local_tracers.append(tracer)
            return

        real_settrace(tracer)

    monkeypatch.setattr(sys, "settrace", fake_settrace)

    test_encoding_helpers_wave1211.test_wave1211_wave1201_capture_tracer_branches_and_target_body()

    assert captured_local_tracers
