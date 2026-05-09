from __future__ import annotations

import sys

from tests.fontbox import test_font_box_font_helpers_wave894


def test_wave954_local_class_capture_tracer_records_matching_frame() -> None:
    def target() -> tuple[
        test_font_box_font_helpers_wave894._LocalClassCapture,
        object,
        type,
    ]:
        class LocalFont:
            pass

        capture = test_font_box_font_helpers_wave894._LocalClassCapture(
            target,
            "LocalFont",
        )
        callback = capture.tracer(sys._getframe(), "line", None)
        return capture, callback, LocalFont

    capture, callback, local_font = target()

    assert capture.captured == [local_font]
    assert callable(callback)


def test_wave954_local_class_capture_tracer_ignores_nonmatching_events() -> None:
    def target() -> tuple[
        test_font_box_font_helpers_wave894._LocalClassCapture,
        object,
    ]:
        class LocalFont:
            pass

        capture = test_font_box_font_helpers_wave894._LocalClassCapture(
            target,
            "LocalFont",
        )
        callback = capture.tracer(sys._getframe(), "call", None)
        return capture, callback

    capture, callback = target()

    assert capture.captured == []
    assert callable(callback)
