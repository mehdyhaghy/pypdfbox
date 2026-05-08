from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.pdmodel import PDDocument
from pypdfbox.tools import cli, imagetopdf


def _write_png(path: Path) -> Path:
    Image.new("RGB", (6, 4), (120, 30, 80)).save(path, format="PNG")
    return path


def test_wave322_helper_accepts_compact_uslegal_page_size(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "source.png")
    out = tmp_path / "out.pdf"

    imagetopdf.images_to_pdf([src], out, page_size="USLEGAL")

    with PDDocument.load(out) as doc:
        media_box = doc.get_page(0).get_media_box()
        assert media_box.get_width() == pytest.approx(612.0)
        assert media_box.get_height() == pytest.approx(1008.0)


def test_wave322_cli_accepts_compact_uslegal_page_size(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "source.png")
    out = tmp_path / "out.pdf"

    rc = cli.run_cli(
        ["imagetopdf", "-i", str(src), "-o", str(out), "-pageSize", "uslegal"]
    )

    assert rc == 0
    with PDDocument.load(out) as doc:
        media_box = doc.get_page(0).get_media_box()
        assert media_box.get_width() == pytest.approx(612.0)
        assert media_box.get_height() == pytest.approx(1008.0)
