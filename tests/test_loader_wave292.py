from __future__ import annotations

import io

import pytest

from pypdfbox import Loader


class _TrackingBytesIO(io.BytesIO):
    pass


class _TrackingTextIO(io.StringIO):
    pass


def test_load_pdf_closes_stream_source_after_buffering_on_parse_failure() -> None:
    source = _TrackingBytesIO(b"not a pdf")

    with pytest.raises(OSError):
        Loader.load_pdf(source)

    assert source.closed


def test_load_pdf_closes_stream_source_when_buffering_rejects_text() -> None:
    source = _TrackingTextIO("%PDF-1.7\n")

    with pytest.raises(TypeError, match="source stream must yield bytes"):
        Loader.load_pdf(source)  # type: ignore[arg-type]

    assert source.closed
