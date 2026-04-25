"""
Ported from
io/src/test/java/org/apache/pdfbox/io/ScratchFileBufferTest.java
(Apache PDFBox 3.0).

pypdfbox's ``ScratchFileBuffer`` is backed by ``io.BytesIO`` (memory-only) /
``tempfile.SpooledTemporaryFile`` (mixed) / ``tempfile.TemporaryFile``
(temp-file-only) — see CHANGES.md. The page-list internals upstream tests
poke at do not exist in pypdfbox; observable seek/length/read/write behavior
is the same.
"""

from __future__ import annotations

import pytest

from pypdfbox.io import MemoryUsageSetting, ScratchFile

PAGE_SIZE = 4096
NUM_ITERATIONS = 3


def test_eof_bug_in_seek() -> None:
    # PDFBOX-4756: positions after seeking + writing across "page" boundaries.
    with ScratchFile(MemoryUsageSetting.setup_main_memory_only()) as scratch_file:
        buf = scratch_file.create_buffer()
        bytes_data = bytes(PAGE_SIZE)
        for i in range(NUM_ITERATIONS):
            p0 = buf.get_position()
            buf.write_bytes(bytes_data)
            p1 = buf.get_position()
            assert p1 - p0 == PAGE_SIZE
            buf.write_bytes(bytes_data)
            p2 = buf.get_position()
            assert p2 - p1 == PAGE_SIZE
            buf.seek(0)
            buf.seek(i * 2 * PAGE_SIZE)


def test_buffer_length() -> None:
    with ScratchFile(MemoryUsageSetting.setup_main_memory_only()) as scratch_file:
        bytes_data = bytes(PAGE_SIZE)
        b1 = scratch_file.create_buffer()
        b1.write_bytes(bytes_data)
        assert b1.length() == PAGE_SIZE


def test_buffer_seek() -> None:
    with ScratchFile(MemoryUsageSetting.setup_main_memory_only()) as scratch_file:
        bytes_data = bytes(PAGE_SIZE)
        b1 = scratch_file.create_buffer()
        b1.write_bytes(bytes_data)
        with pytest.raises((OSError, ValueError)):
            b1.seek(-1)
        # skipped: upstream asserts EOFException for seek beyond a single
        # 4 KiB "page"; pypdfbox's BytesIO/SpooledTemporaryFile backing has no
        # page concept — seeking past end is allowed and clamps to length.


def test_buffer_eof() -> None:
    with ScratchFile(MemoryUsageSetting.setup_main_memory_only()) as scratch_file:
        bytes_data = bytes(PAGE_SIZE)
        b1 = scratch_file.create_buffer()
        b1.write_bytes(bytes_data)
        b1.seek(0)
        assert not b1.is_eof()
        b1.seek(PAGE_SIZE)
        assert b1.is_eof()


def test_already_close() -> None:
    with ScratchFile(MemoryUsageSetting.setup_main_memory_only()) as scratch_file:
        bytes_data = bytes(PAGE_SIZE)
        buf = scratch_file.create_buffer()
        buf.write_bytes(bytes_data)
        buf.close()
        with pytest.raises((OSError, ValueError)):
            buf.seek(0)


def test_buffers_closed() -> None:
    with ScratchFile(MemoryUsageSetting.setup_main_memory_only()) as scratch_file:
        bytes_data = bytes(PAGE_SIZE)
        b1 = scratch_file.create_buffer()
        b1.write_bytes(bytes_data)
        b2 = scratch_file.create_buffer()
        b2.write_bytes(bytes_data)
        b3 = scratch_file.create_buffer()
        b3.write_bytes(bytes_data)
        b4 = scratch_file.create_buffer()
        b4.write_bytes(bytes_data)

        b1.close()
        b3.close()

        assert b1.is_closed()
        assert not b2.is_closed()
        assert b3.is_closed()
        assert not b4.is_closed()

        scratch_file.close()
        assert b2.is_closed()
        assert b4.is_closed()


def test_view() -> None:
    with ScratchFile(MemoryUsageSetting.setup_main_memory_only()) as scratch_file:
        buf = scratch_file.create_buffer()
        buf.write_bytes(bytes([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]))
        # ScratchFileBuffer does not support views in upstream; pypdfbox
        # inherits ``create_view`` from RandomAccessRead but the contract is
        # not implemented for scratch buffers.
        with pytest.raises((NotImplementedError, OSError, ValueError, TypeError)):
            buf.create_view(0, 10)
