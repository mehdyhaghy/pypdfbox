"""Sniff a file's type from its leading magic bytes.

Mirrors ``org.apache.pdfbox.util.filetypedetector.FileTypeDetector``.
"""

from __future__ import annotations

import io
from typing import BinaryIO

from pypdfbox.util.filetypedetector.byte_trie import ByteTrie
from pypdfbox.util.filetypedetector.file_type import FileType


def _build_root() -> ByteTrie[FileType]:
    root: ByteTrie[FileType] = ByteTrie()
    root.set_default_value(FileType.UNKNOWN)

    ii_bytes = b"II"
    mm_bytes = b"MM"

    root.add_path(FileType.JPEG, b"\xff\xd8")
    root.add_path(FileType.TIFF, ii_bytes, b"\x2a\x00")
    root.add_path(FileType.TIFF, mm_bytes, b"\x00\x2a")
    root.add_path(FileType.PSD, b"8BPS")
    root.add_path(
        FileType.PNG,
        b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a\x00\x00\x00\x0d\x49\x48\x44\x52",
    )
    root.add_path(FileType.BMP, b"BM")
    root.add_path(FileType.GIF, b"GIF87a")
    root.add_path(FileType.GIF, b"GIF89a")
    root.add_path(FileType.ICO, b"\x00\x00\x01\x00")
    root.add_path(FileType.PCX, b"\x0a\x00\x01")
    root.add_path(FileType.PCX, b"\x0a\x02\x01")
    root.add_path(FileType.PCX, b"\x0a\x03\x01")
    root.add_path(FileType.PCX, b"\x0a\x05\x01")
    root.add_path(FileType.RIFF, b"RIFF")

    root.add_path(FileType.CRW, ii_bytes, b"\x1a\x00\x00\x00", b"HEAPCCDR")
    root.add_path(FileType.CR2, ii_bytes, b"\x2a\x00\x10\x00\x00\x00\x43\x52")
    root.add_path(FileType.NEF, mm_bytes, b"\x00\x2a\x00\x00\x00\x80\x00")
    root.add_path(FileType.ORF, b"IIRO", b"\x08\x00")
    root.add_path(FileType.ORF, b"IIRS", b"\x08\x00")
    root.add_path(FileType.RAF, b"FUJIFILMCCD-RAW")
    root.add_path(FileType.RW2, ii_bytes, b"\x55\x00")
    return root


class FileTypeDetector:
    """Static-only file type sniffer."""

    _root = _build_root()

    def __init__(self) -> None:  # pragma: no cover
        raise TypeError("FileTypeDetector is a utility class")

    @classmethod
    def detect_file_type(cls, source: BinaryIO | bytes | bytearray) -> FileType:
        """Detect type of ``source`` (peek-able stream or raw bytes).

        Streams without a mark/reset (i.e. ``BufferedReader.markSupported``
        semantics) must be wrapped in ``io.BufferedReader``. We accept any
        ``BinaryIO`` and use ``peek`` / ``tell+seek`` so callers don't have
        to mark.
        """
        if isinstance(source, (bytes, bytearray)):
            return cls._root.find(bytes(source)) or FileType.UNKNOWN

        max_byte_count = cls._root.get_max_depth()
        # Try peek first (BufferedReader-style); fall back to read+seek.
        if hasattr(source, "peek"):
            data = source.peek(max_byte_count)[:max_byte_count]  # type: ignore[union-attr]
            if not data:
                raise OSError(
                    "Stream ended before file's magic number could be determined."
                )
            return cls._root.find(data) or FileType.UNKNOWN
        if hasattr(source, "tell") and hasattr(source, "seek"):
            pos = source.tell()
            data = source.read(max_byte_count)
            if not data:
                raise OSError(
                    "Stream ended before file's magic number could be determined."
                )
            source.seek(pos)
            return cls._root.find(data) or FileType.UNKNOWN
        raise OSError("Stream must support mark/reset")

    @classmethod
    def _wrap(cls, raw: BinaryIO) -> io.BufferedReader:
        """Wrap an unbuffered binary stream for peek support."""
        if isinstance(raw, io.BufferedReader):
            return raw
        return io.BufferedReader(raw)  # type: ignore[arg-type]


__all__ = ["FileTypeDetector"]
