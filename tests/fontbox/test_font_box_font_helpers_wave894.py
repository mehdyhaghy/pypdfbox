from __future__ import annotations

import sys
from collections.abc import Callable
from types import FrameType

from tests.fontbox import test_font_box_font


def _capture_local_class(test_func: Callable[[], None], name: str) -> type:
    captured: list[type] = []

    def tracer(frame: FrameType, event: str, arg: object) -> object:
        if frame.f_code is test_func.__code__ and event == "line":
            local_value = frame.f_locals.get(name)
            if isinstance(local_value, type):
                captured.append(local_value)
        return tracer

    old_trace = sys.gettrace()
    sys.settrace(tracer)
    try:
        test_func()
    finally:
        sys.settrace(old_trace)

    assert captured
    return captured[-1]


def test_wave894_incomplete_font_stub_methods() -> None:
    incomplete = _capture_local_class(
        test_font_box_font.test_font_box_font_rejects_missing_methods,
        "Incomplete",
    )
    font = incomplete()

    assert font.get_name() == "x"
    assert font.get_width("A") == 0.0


def test_wave894_encoded_dummy_stub_returns_encoding() -> None:
    assert test_font_box_font._EncodedDummy().get_encoding() == {65: "A"}


def test_wave894_no_encoding_stub_method() -> None:
    no_encoding = _capture_local_class(
        test_font_box_font.test_encoded_font_rejects_missing_method,
        "NoEncoding",
    )

    assert no_encoding().get_name() == "x"
