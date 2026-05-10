from __future__ import annotations

from pathlib import Path

from pypdfbox.io import RandomAccessReadBuffer, RandomAccessReadMemoryMapped


def test_is_eof_matches_read_for_buffer_view_past_parent_end() -> None:
    # Upstream PDFBox semantics: a view whose logical length runs past the
    # parent's real end will get -1 from read() once the parent runs dry,
    # but is_eof() only flips when currentPosition reaches streamLength.
    with RandomAccessReadBuffer(b"abc") as reader, reader.create_view(2, 4) as view:
        assert view.read() == ord("c")
        assert view.read() == view.EOF

        assert not view.is_eof()
        assert view.get_position() == 1


def test_is_eof_matches_read_for_memory_mapped_view_past_parent_end(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sample.bin"
    path.write_bytes(b"abc")

    with RandomAccessReadMemoryMapped(path) as reader, reader.create_view(2, 4) as view:
        assert view.read() == ord("c")
        assert view.read() == view.EOF

        assert not view.is_eof()
        assert view.get_position() == 1
