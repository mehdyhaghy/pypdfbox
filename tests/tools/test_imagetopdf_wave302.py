from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.pdmodel import PDDocument
from pypdfbox.tools import cli, imagetopdf


def _write_png(path: Path, *, size: tuple[int, int] = (20, 10)) -> Path:
    Image.new("RGB", size, (25, 90, 160)).save(path, format="PNG")
    return path


def test_wave302_cli_orientation_accepts_mixed_case(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "wide.png")
    out = tmp_path / "out.pdf"

    rc = cli.run_cli(
        [
            "imagetopdf",
            "-i",
            str(src),
            "-o",
            str(out),
            "-pageSize",
            "Letter",
            "-orientation",
            "LANDSCAPE",
        ]
    )

    assert rc == 0
    with PDDocument.load(out) as doc:
        media_box = doc.get_page(0).get_media_box()
        assert media_box.get_width() > media_box.get_height()


def test_wave302_helper_orientation_accepts_mixed_case(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "wide.png")
    out = tmp_path / "out.pdf"

    imagetopdf.images_to_pdf([src], out, page_size="Letter", orientation="Auto")

    with PDDocument.load(out) as doc:
        media_box = doc.get_page(0).get_media_box()
        assert media_box.get_width() > media_box.get_height()


def test_wave302_helper_rejects_unknown_orientation(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "wide.png")

    with pytest.raises(ValueError, match="orientation must be one of"):
        imagetopdf.images_to_pdf(
            [src],
            tmp_path / "out.pdf",
            orientation="diagonal",
        )
