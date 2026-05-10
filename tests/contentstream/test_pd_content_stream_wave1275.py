"""Wave 1275 parity test for PDContentStream.get_b_box snake_case alias."""

from __future__ import annotations

from typing import Any

from pypdfbox.contentstream.pd_content_stream import PDContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


class _StubContentStream(PDContentStream):
    def __init__(self, bbox: PDRectangle) -> None:
        self._bbox = bbox

    def get_contents(self) -> Any:
        raise NotImplementedError

    def get_contents_for_random_access(self) -> Any:
        raise NotImplementedError

    def get_resources(self) -> Any:
        return None

    def get_bbox(self) -> PDRectangle:
        return self._bbox

    def get_matrix(self) -> Any:
        return None


def test_get_b_box_alias_returns_bbox() -> None:
    rect = PDRectangle(0.0, 0.0, 100.0, 200.0)
    stream = _StubContentStream(rect)
    assert stream.get_b_box() is rect
    assert stream.get_b_box() is stream.get_bbox()
