from __future__ import annotations

import io
from typing import IO, Any

import pytest

from pypdfbox.contentstream import PDContentStream
from pypdfbox.io.random_access_read import RandomAccessRead
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdmodel import PDRectangle, PDResources


class _FakeStream(PDContentStream):
    def __init__(self, data: bytes, resources: PDResources, bbox: PDRectangle) -> None:
        self._data = data
        self._resources = resources
        self._bbox = bbox

    def get_contents(self) -> IO[bytes]:
        return io.BytesIO(self._data)

    def get_contents_for_random_access(self) -> RandomAccessRead:
        return RandomAccessReadBuffer(self._data)

    def get_resources(self) -> PDResources | None:
        return self._resources

    def get_bbox(self) -> PDRectangle:
        return self._bbox

    def get_matrix(self) -> Any:
        # cluster #1: COSArray placeholder until Matrix lands.
        return None


def test_subclass_satisfies_interface() -> None:
    res = PDResources()
    bbox = PDRectangle(0.0, 0.0, 612.0, 792.0)
    stream = _FakeStream(b"BT (hi) Tj ET", res, bbox)
    assert stream.get_contents().read() == b"BT (hi) Tj ET"
    assert stream.get_resources() is res
    assert stream.get_bbox() is bbox


def test_get_contents_for_stream_parsing_default_delegates() -> None:
    stream = _FakeStream(b"q Q", PDResources(), PDRectangle())
    raw = stream.get_contents_for_stream_parsing()
    assert isinstance(raw, RandomAccessRead)
    assert raw.length() == 3


def test_cannot_instantiate_abstract_directly() -> None:
    with pytest.raises(TypeError):
        PDContentStream()  # type: ignore[abstract]


def test_subclass_missing_method_cannot_instantiate() -> None:
    class _Incomplete(PDContentStream):
        def get_contents(self) -> IO[bytes]:
            return io.BytesIO(b"")

    with pytest.raises(TypeError):
        _Incomplete()  # type: ignore[abstract]
