"""Coverage-boost tests for ``PDAppearanceStream`` (wave 1332).

Targets the three previously uncovered branches:

* :meth:`PDAppearanceStream.get_pd_stream` — the typed-wrapper accessor;
* the empty-body branch of :meth:`get_contents` (returns an empty
  ``BytesIO`` instead of asking ``COSStream.create_input_stream`` for a
  view it cannot produce);
* the empty-body branch of :meth:`get_contents_for_random_access`
  (returns an empty ``RandomAccessReadBuffer``).
"""

from __future__ import annotations

from io import BytesIO

from pypdfbox.cos import COSStream
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)


def test_get_pd_stream_returns_pd_stream_wrapper_from_cos_stream_ctor() -> None:
    stream = COSStream()
    pap = PDAppearanceStream(stream)

    wrapper = pap.get_pd_stream()

    assert isinstance(wrapper, PDStream)
    # The wrapper must point at the same underlying COSStream we passed in.
    assert wrapper.get_cos_object() is stream


def test_get_pd_stream_round_trips_existing_pd_stream_wrapper() -> None:
    stream = COSStream()
    wrapper_in = PDStream(stream)

    pap = PDAppearanceStream(wrapper_in)

    wrapper_out = pap.get_pd_stream()
    assert isinstance(wrapper_out, PDStream)
    assert wrapper_out.get_cos_object() is stream


def test_get_contents_returns_empty_bytes_io_when_stream_body_is_empty() -> None:
    # Fresh COSStream has no data — ``create_input_stream`` would raise,
    # so the appearance-stream override must hand back an empty BytesIO.
    stream = COSStream()
    assert not stream.has_data()

    pap = PDAppearanceStream(stream)

    contents = pap.get_contents()
    try:
        assert isinstance(contents, BytesIO)
        assert contents.read() == b""
    finally:
        contents.close()


def test_get_contents_for_random_access_returns_empty_buffer_when_body_empty() -> None:
    stream = COSStream()
    assert not stream.has_data()

    pap = PDAppearanceStream(stream)

    view = pap.get_contents_for_random_access()
    try:
        assert isinstance(view, RandomAccessReadBuffer)
        assert view.length() == 0
        # Java-style read() returns -1 at EOF, which is immediate for an
        # empty buffer.
        assert view.read() == -1
    finally:
        view.close()
