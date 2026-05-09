from __future__ import annotations

from pypdfbox.pdmodel import PDRectangle, PDResources
from tests.contentstream.test_pd_content_stream import (
    _FakeStream,
    _IncompleteContentStream,
)


def test_fake_stream_get_matrix_placeholder_returns_none() -> None:
    stream = _FakeStream(b"", PDResources(), PDRectangle())

    assert stream.get_matrix() is None


def test_incomplete_content_stream_get_contents_body() -> None:
    assert _IncompleteContentStream.get_contents(None).read() == b""  # type: ignore[arg-type]
