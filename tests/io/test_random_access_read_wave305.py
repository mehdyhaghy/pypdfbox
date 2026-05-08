from __future__ import annotations

from pathlib import Path

from pypdfbox.io import RandomAccessReadBuffer, RandomAccessReadMemoryMapped


def test_is_eof_matches_read_for_buffer_view_past_parent_end() -> None:
    with RandomAccessReadBuffer(b"abc") as reader, reader.create_view(2, 4) as view:
        assert view.read() == ord("c")
        assert view.read() == view.EOF

        assert view.is_eof()
        assert view.get_position() == 1


def test_is_eof_matches_read_for_memory_mapped_view_past_parent_end(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sample.bin"
    path.write_bytes(b"abc")

    with RandomAccessReadMemoryMapped(path) as reader, reader.create_view(2, 4) as view:
        assert view.read() == ord("c")
        assert view.read() == view.EOF

        assert view.is_eof()
        assert view.get_position() == 1
