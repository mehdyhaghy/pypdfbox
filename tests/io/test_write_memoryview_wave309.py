from __future__ import annotations

from pypdfbox.io import RandomAccessWriteBuffer, ScratchFile


def test_random_access_write_buffer_offsets_cast_memoryview_by_bytes() -> None:
    writer = RandomAccessWriteBuffer()
    wide_view = memoryview(b"01234567").cast("H")

    writer.write_bytes(wide_view, offset=2, length=4)

    assert writer.to_bytes() == b"2345"


def test_scratch_file_buffer_offsets_cast_memoryview_by_bytes() -> None:
    wide_view = memoryview(b"abcdefgh").cast("H")
    with ScratchFile(page_size=4) as scratch:
        buf = scratch.create_buffer()

        buf.write_bytes(wide_view, offset=1, length=6)
        buf.seek(0)
        out = bytearray(6)

        assert buf.read_into(out) == 6
        assert bytes(out) == b"bcdefg"


def test_scratch_file_write_page_offsets_cast_memoryview_by_bytes() -> None:
    wide_view = memoryview(b"ABCDEFGH").cast("H")
    with ScratchFile(page_size=4) as scratch:
        page = scratch.get_new_page()

        scratch.write_page(page, wide_view, offset=2, length=4)
        out = bytearray(4)
        scratch.read_page(page, out)

        assert bytes(out) == b"CDEF"
