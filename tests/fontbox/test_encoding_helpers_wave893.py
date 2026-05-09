from __future__ import annotations

import sys
from collections.abc import Callable
from types import FrameType

from tests.fontbox.encoding import test_encoding


class _LocalClassCapture:
    def __init__(self, test_func: Callable[[], None], name: str) -> None:
        self.test_func = test_func
        self.name = name
        self.captured: list[type] = []

    def tracer(self, frame: FrameType, event: str, arg: object) -> object:
        if frame.f_code is self.test_func.__code__ and event == "line":
            local_value = frame.f_locals.get(self.name)
            if isinstance(local_value, type):
                self.captured.append(local_value)
        return self.tracer


def _capture_local_class(test_func: Callable[[], None], name: str) -> type:
    capture = _LocalClassCapture(test_func, name)

    old_trace = sys.gettrace()
    sys.settrace(capture.tracer)
    try:
        test_func()
    finally:
        sys.settrace(old_trace)

    assert capture.captured
    return capture.captured[-1]


def test_wave893_top_level_dummy_encoding_names() -> None:
    assert test_encoding._DummyEncoding().get_encoding_name() == "Dummy"
    assert test_encoding._DummyEncodingDup().get_encoding_name() == "DummyDup"


def test_wave893_local_overwrite_stub_encoding_name() -> None:
    local_encoding = _capture_local_class(
        test_encoding.test_overwrite_replaces_reverse_mapping,
        "E",
    )

    assert local_encoding().get_encoding_name() == "E"


def test_wave893_local_alias_stub_encoding_name() -> None:
    local_encoding = _capture_local_class(
        test_encoding.test_add_character_encoding_alias_matches_add,
        "E",
    )

    assert local_encoding().get_encoding_name() == "E"
