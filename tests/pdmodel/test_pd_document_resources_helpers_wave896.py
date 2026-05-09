from __future__ import annotations

import io

from pypdfbox.pdmodel import PDDocument


def test_wave896_write_bytes_to_file_like_target() -> None:
    sink = io.BytesIO()

    PDDocument._write_bytes_to_target(b"file-like", sink)  # noqa: SLF001

    assert sink.getvalue() == b"file-like"


def test_wave896_write_bytes_to_path_target(tmp_path) -> None:  # noqa: ANN001
    target = tmp_path / "signed-output.pdf"

    PDDocument._write_bytes_to_target(b"path-target", target)  # noqa: SLF001

    assert target.read_bytes() == b"path-target"


def test_wave896_extract_bracketed_returns_disjoint_signed_ranges() -> None:
    data = bytearray(b"abcdSIGNefgh")

    assert PDDocument._extract_bracketed(data, [0, 4, 8, 4]) == b"abcdefgh"  # noqa: SLF001
