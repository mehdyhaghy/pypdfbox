"""Coverage cleanup for ``tests.multipdf.test_overlay`` helpers."""

from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDPage
from tests.multipdf.test_overlay import _flatten_contents


def test_flatten_contents_accepts_single_stream() -> None:
    page = PDPage()
    stream = COSStream()
    stream.set_raw_data(b"q Q\n")
    page.set_contents(stream)

    assert _flatten_contents(page) == [stream]
