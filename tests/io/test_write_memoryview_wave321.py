from __future__ import annotations

from pypdfbox.io import RandomAccessWriteBuffer, ScratchFile


def test_random_access_write_buffer_wave321_writes_strided_memoryview() -> None:
    writer = RandomAccessWriteBuffer()
    strided = memoryview(bytearray(b"abcdefghi"))[::2]

    writer.write_bytes(strided, offset=1, length=3)

    assert writer.to_bytes() == b"ceg"


def test_scratch_file_buffer_wave321_writes_strided_memoryview() -> None:
    strided = memoryview(bytearray(b"abcdefghi"))[::2]
    with ScratchFile(page_size=4) as scratch:
        buf = scratch.create_buffer()

        buf.write_bytes(strided, offset=1, length=3)
        buf.seek(0)
        out = bytearray(3)

        assert buf.read_into(out) == 3
        assert bytes(out) == b"ceg"
