from __future__ import annotations

import sys

from tests.fontbox import test_encoding_helpers_wave893


def test_wave953_local_class_capture_tracer_records_matching_frame() -> None:
    def target() -> tuple[
        test_encoding_helpers_wave893._LocalClassCapture,
        object,
        type,
    ]:
        class LocalEncoding:
            pass

        capture = test_encoding_helpers_wave893._LocalClassCapture(
            target,
            "LocalEncoding",
        )
        callback = capture.tracer(sys._getframe(), "line", None)
        return capture, callback, LocalEncoding

    capture, callback, local_encoding = target()

    assert capture.captured == [local_encoding]
    assert callable(callback)


def test_wave953_local_class_capture_tracer_ignores_nonmatching_frames() -> None:
    def target() -> None:
        return None

    capture = test_encoding_helpers_wave893._LocalClassCapture(target, "Missing")
    callback = capture.tracer(sys._getframe(), "line", None)

    assert capture.captured == []
    assert callable(callback)
