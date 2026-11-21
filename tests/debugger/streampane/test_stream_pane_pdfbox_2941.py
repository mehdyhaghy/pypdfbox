"""PDFBOX-2941 (3.0 branch + trunk 43d03b63): the stream pane closes every
stream it opens, and the "nice" view keeps the bytes it read so the plain
text fallback still shows the data when content-stream parsing fails.

These tests drive ``DocumentCreator`` and ``StreamPane._build_segments``
without a Tk root, so they run headless on every platform.
"""

import io
from typing import Any

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.debugger.streampane import stream_pane as sp_mod
from pypdfbox.debugger.streampane.stream import Stream
from pypdfbox.debugger.streampane.stream_pane import DocumentCreator, StreamPane

_DATA = b"BT /F1 12 Tf (Hello) Tj ET\r\n"


class _TrackingStream(Stream):
    """``Stream`` whose ``get_stream`` hands out tracked ``BytesIO``s."""

    def __init__(self, data: bytes, xml: bool = False) -> None:
        cos = COSStream()
        cos.set_data(data)
        super().__init__(cos, is_thumb=False)
        self._data = data
        self._xml = xml
        self.opened: list[io.BytesIO] = []

    def get_stream(self, key: str) -> Any:
        buf = io.BytesIO(self._data)
        self.opened.append(buf)
        return buf

    def is_xml_metadata(self) -> bool:
        return self._xml


class _View:
    def show_stream_text(self, *_args: Any, **_kwargs: Any) -> None:
        pass


@pytest.mark.parametrize(
    ("nice", "xml"),
    [(False, False), (True, False), (True, True)],
    ids=["raw", "nice_content", "nice_xml"],
)
def test_document_creator_closes_stream(nice: bool, xml: bool) -> None:
    payload = b"<a><b/></a>" if xml else _DATA
    stream = _TrackingStream(payload, xml=xml)
    DocumentCreator(_View(), stream, Stream.DECODED, nice=nice).execute()
    assert stream.opened
    assert all(buf.closed for buf in stream.opened)


def test_document_creator_none_stream_is_empty() -> None:
    stream = _TrackingStream(_DATA)
    stream.get_stream = lambda _key: None  # type: ignore[method-assign]
    assert DocumentCreator(_View(), stream, Stream.DECODED, nice=True).execute() == []


def test_nice_view_fallback_keeps_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the content-stream parse fails, the plain-text fallback gets the
    same bytes (trunk 43d03b63), with CR LF normalized to LF."""

    def _fail(_data: bytes) -> Any:
        raise OSError("not a content stream")

    monkeypatch.setattr(sp_mod.PDFStreamParser, "from_bytes", _fail)
    stream = _TrackingStream(_DATA)
    segments = DocumentCreator(_View(), stream, Stream.DECODED, nice=True).execute()
    assert segments == [("BT /F1 12 Tf (Hello) Tj ET\n", None)]
    # Read once, so a single stream is opened (and closed).
    assert len(stream.opened) == 1
    assert stream.opened[0].closed


def test_pane_build_segments_fallback_and_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail(_data: bytes) -> Any:
        raise OSError("not a content stream")

    monkeypatch.setattr(sp_mod.PDFStreamParser, "from_bytes", _fail)
    pane = StreamPane.__new__(StreamPane)
    stream = _TrackingStream(_DATA)
    pane._stream = stream
    assert pane._build_segments(Stream.DECODED, nice=True) == [
        ("BT /F1 12 Tf (Hello) Tj ET\n", None)
    ]
    assert pane._build_segments(Stream.DECODED, nice=False) == [
        ("BT /F1 12 Tf (Hello) Tj ET\n", None)
    ]
    assert len(stream.opened) == 2
    assert all(buf.closed for buf in stream.opened)
