"""Coverage backfill for :class:`pypdfbox.util.filetypedetector.file_type_detector.FileTypeDetector`.

Targets the peek-based + read+seek code paths, unbuffered ``_wrap``, and
the empty-stream OSError raises.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.util.filetypedetector.file_type import FileType
from pypdfbox.util.filetypedetector.file_type_detector import FileTypeDetector


# --- Bytes / bytearray inputs ----------------------------------------------


def test_detect_from_bytes_returns_jpeg() -> None:
    assert FileTypeDetector.detect_file_type(b"\xff\xd8somethingelse") is FileType.JPEG


def test_detect_from_bytearray_returns_png() -> None:
    png_sig = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    assert FileTypeDetector.detect_file_type(bytearray(png_sig)) is FileType.PNG


def test_detect_from_bytes_unknown_returns_unknown() -> None:
    assert FileTypeDetector.detect_file_type(b"NOTANIMAGE") is FileType.UNKNOWN


# --- BufferedReader peek path ---------------------------------------------


def test_detect_from_buffered_reader_via_peek() -> None:
    raw = io.BytesIO(b"\xff\xd8\xff\xe0JFIF\x00")
    buffered = io.BufferedReader(raw)  # type: ignore[arg-type]
    assert FileTypeDetector.detect_file_type(buffered) is FileType.JPEG


def test_detect_from_buffered_reader_empty_raises_oserror() -> None:
    raw = io.BytesIO(b"")
    buffered = io.BufferedReader(raw)  # type: ignore[arg-type]
    with pytest.raises(OSError, match="Stream ended"):
        FileTypeDetector.detect_file_type(buffered)


# --- BytesIO (tell+seek) path ---------------------------------------------


def test_detect_from_bytesio_preserves_position() -> None:
    bio = io.BytesIO(b"\xff\xd8\xff\xe0JFIF\x00")
    pos_before = bio.tell()
    detected = FileTypeDetector.detect_file_type(bio)
    assert detected is FileType.JPEG
    # Position must be preserved.
    assert bio.tell() == pos_before


def test_detect_from_bytesio_empty_raises_oserror() -> None:
    bio = io.BytesIO(b"")
    with pytest.raises(OSError, match="Stream ended"):
        FileTypeDetector.detect_file_type(bio)


def test_detect_from_bytesio_unknown_signature() -> None:
    bio = io.BytesIO(b"BOGUSDATA12345")
    assert FileTypeDetector.detect_file_type(bio) is FileType.UNKNOWN


# --- Streams without tell/seek/peek raise -----------------------------------


class _MarkLessStream:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._idx = 0

    def read(self, n: int) -> bytes:
        out = self._data[self._idx : self._idx + n]
        self._idx += len(out)
        return out


def test_detect_from_stream_without_mark_raises() -> None:
    s = _MarkLessStream(b"\xff\xd8somecontent")
    with pytest.raises(OSError, match="mark/reset"):
        FileTypeDetector.detect_file_type(s)  # type: ignore[arg-type]


# --- Multiple signatures (TIFF / GIF / BMP / PCX / RIFF / RAF) -------------


@pytest.mark.parametrize(
    "data,expected",
    [
        (b"II\x2a\x00\x08\x00\x00\x00", FileType.TIFF),
        (b"MM\x00\x2a\x00\x08\x00\x00", FileType.TIFF),
        (b"GIF87a..", FileType.GIF),
        (b"GIF89a..", FileType.GIF),
        (b"BM..", FileType.BMP),
        (b"\x00\x00\x01\x00\x01\x00", FileType.ICO),
        (b"\x0a\x00\x01..", FileType.PCX),
        (b"RIFF....WAVE", FileType.RIFF),
        (b"FUJIFILMCCD-RAW0102", FileType.RAF),
        (b"8BPS\x00\x01", FileType.PSD),
    ],
)
def test_detect_known_signatures(data: bytes, expected: FileType) -> None:
    assert FileTypeDetector.detect_file_type(data) is expected


# --- _wrap helper --------------------------------------------------------


def test_wrap_passes_through_existing_buffered_reader() -> None:
    raw = io.BytesIO(b"data")
    buffered = io.BufferedReader(raw)  # type: ignore[arg-type]
    wrapped = FileTypeDetector._wrap(buffered)
    assert wrapped is buffered


def test_wrap_wraps_raw_stream() -> None:
    raw = io.BytesIO(b"data")
    # BytesIO is itself a buffered stream; ``_wrap`` will only re-wrap if it
    # isn't already a BufferedReader instance.
    wrapped = FileTypeDetector._wrap(raw)  # type: ignore[arg-type]
    assert isinstance(wrapped, io.BufferedReader)


# --- Utility-class guard --------------------------------------------------


def test_constructor_raises_type_error() -> None:
    with pytest.raises(TypeError, match="utility class"):
        FileTypeDetector()
