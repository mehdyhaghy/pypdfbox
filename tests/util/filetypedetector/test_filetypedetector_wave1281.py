"""Hand-written tests for the ``pypdfbox.util.filetypedetector`` cluster."""

from __future__ import annotations

import io

from pypdfbox.util.filetypedetector import ByteTrie, FileType, FileTypeDetector


def test_byte_trie_find_and_add() -> None:
    trie: ByteTrie[str] = ByteTrie()
    trie.set_default_value("UNKNOWN")
    trie.add_path("PNG", b"\x89PNG")
    trie.add_path("JPEG", b"\xff\xd8")
    assert trie.find(b"\x89PNG\r\n") == "PNG"
    assert trie.find(b"\xff\xd8\xff\xe0") == "JPEG"
    assert trie.find(b"random") == "UNKNOWN"
    assert trie.get_max_depth() >= 4


def test_byte_trie_rejects_duplicate_value() -> None:
    trie: ByteTrie[str] = ByteTrie()
    trie.add_path("A", b"x")
    import pytest

    with pytest.raises(RuntimeError):
        trie.add_path("B", b"x")


def test_file_type_detector_png() -> None:
    png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 16
    assert FileTypeDetector.detect_file_type(png) is FileType.PNG


def test_file_type_detector_jpeg() -> None:
    jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 32
    assert FileTypeDetector.detect_file_type(jpeg) is FileType.JPEG


def test_file_type_detector_unknown() -> None:
    assert FileTypeDetector.detect_file_type(b"random data") is FileType.UNKNOWN


def test_file_type_detector_from_stream() -> None:
    png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 16
    stream = io.BytesIO(png)
    assert FileTypeDetector.detect_file_type(stream) is FileType.PNG
    # Stream position is preserved.
    assert stream.tell() == 0
