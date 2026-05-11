from __future__ import annotations

from pypdfbox.pdmodel.common import LabelHandler


class _CountingHandler:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    def new_label(self, page_index: int, label: str) -> None:
        self.calls.append((page_index, label))


def test_protocol_matches_method_shape() -> None:
    assert isinstance(_CountingHandler(), LabelHandler)


def test_protocol_rejects_no_method() -> None:
    class _NoMethod:
        pass

    assert not isinstance(_NoMethod(), LabelHandler)


def test_invocation_records_calls() -> None:
    handler = _CountingHandler()
    handler.new_label(0, "i")
    handler.new_label(1, "ii")
    assert handler.calls == [(0, "i"), (1, "ii")]
