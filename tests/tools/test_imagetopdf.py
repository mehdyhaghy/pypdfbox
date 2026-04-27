"""Tests for ``pypdfbox imagetopdf`` and the ``images_to_pdf`` helper."""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDRectangle
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.tools import cli, imagetopdf


# ----------------------------------------------------------------- helpers


def _write_png(path: Path, *, size: tuple[int, int] = (4, 4),
               color: tuple[int, int, int] = (255, 0, 0)) -> Path:
    """Write a tiny solid-color RGB PNG."""
    Image.new("RGB", size, color).save(path, format="PNG")
    return path


def _write_jpeg(path: Path, *, size: tuple[int, int] = (8, 8),
                color: tuple[int, int, int] = (0, 128, 255)) -> Path:
    Image.new("RGB", size, color).save(path, format="JPEG")
    return path


def _first_image_xobject(doc: PDDocument) -> PDImageXObject:
    page = doc.get_page(0)
    res = page.get_resources()
    names = list(res.get_xobject_names())
    assert names, "page has no /XObject entries"
    xobject = res.get_x_object(names[0])
    assert isinstance(xobject, PDImageXObject)
    return xobject


# ---------------------------------------------------------- helper API


def test_images_to_pdf_round_trip_single_png(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "red.png", size=(4, 4), color=(255, 0, 0))
    out = tmp_path / "out.pdf"

    imagetopdf.images_to_pdf([src], out)

    assert out.is_file()
    with PDDocument.load(out) as pd:
        assert pd.get_number_of_pages() == 1
        image = _first_image_xobject(pd)
        cos = image.get_cos_object()
        assert cos.get_name(COSName.SUBTYPE) == "Image"  # type: ignore[attr-defined]
        assert image.get_width() == 4
        assert image.get_height() == 4
        assert image.get_bits_per_component() == 8


def test_images_to_pdf_jpeg_uses_dct_decode(tmp_path: Path) -> None:
    src = _write_jpeg(tmp_path / "blue.jpg", size=(8, 8))
    out = tmp_path / "out.pdf"

    imagetopdf.images_to_pdf([src], out)

    with PDDocument.load(out) as pd:
        image = _first_image_xobject(pd)
        # JPEG bytes embed verbatim behind /DCTDecode.
        filters = [n.name for n in image.get_cos_object().get_filter_list()]
        assert filters == ["DCTDecode"]
        assert image.get_width() == 8
        assert image.get_height() == 8


def test_images_to_pdf_png_uses_flate_decode(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "green.png", size=(2, 2), color=(0, 255, 0))
    out = tmp_path / "out.pdf"

    imagetopdf.images_to_pdf([src], out)

    with PDDocument.load(out) as pd:
        image = _first_image_xobject(pd)
        filters = [n.name for n in image.get_cos_object().get_filter_list()]
        assert filters == ["FlateDecode"]


def test_images_to_pdf_multipage(tmp_path: Path) -> None:
    a = _write_png(tmp_path / "a.png", size=(3, 3), color=(255, 0, 0))
    b = _write_png(tmp_path / "b.png", size=(3, 3), color=(0, 0, 255))
    out = tmp_path / "out.pdf"

    imagetopdf.images_to_pdf([a, b], out)

    with PDDocument.load(out) as pd:
        assert pd.get_number_of_pages() == 2


def test_images_to_pdf_default_letter_media_box(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "red.png", size=(4, 4), color=(255, 0, 0))
    out = tmp_path / "out.pdf"

    imagetopdf.images_to_pdf([src], out, page_size="Letter")

    with PDDocument.load(out) as pd:
        page = pd.get_page(0)
        mb = page.get_media_box()
        # Letter = 612 x 792 in PDF user-space points.
        assert mb.get_width() == pytest.approx(612.0)
        assert mb.get_height() == pytest.approx(792.0)


def test_images_to_pdf_a4_media_box(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "x.png")
    out = tmp_path / "out.pdf"

    imagetopdf.images_to_pdf([src], out, page_size="A4")

    with PDDocument.load(out) as pd:
        mb = pd.get_page(0).get_media_box()
        assert mb.get_width() == pytest.approx(595.0)
        assert mb.get_height() == pytest.approx(842.0)


def test_images_to_pdf_auto_page_size_matches_image(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "x.png", size=(120, 80))
    out = tmp_path / "out.pdf"

    imagetopdf.images_to_pdf([src], out, page_size="auto")

    with PDDocument.load(out) as pd:
        mb = pd.get_page(0).get_media_box()
        assert mb.get_width() == pytest.approx(120.0)
        assert mb.get_height() == pytest.approx(80.0)


def test_images_to_pdf_landscape_swaps_dimensions(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "x.png")
    out = tmp_path / "out.pdf"

    imagetopdf.images_to_pdf(
        [src], out, page_size="Letter", orientation="landscape"
    )

    with PDDocument.load(out) as pd:
        mb = pd.get_page(0).get_media_box()
        # Letter rotated 90°: width swaps with height.
        assert mb.get_width() == pytest.approx(792.0)
        assert mb.get_height() == pytest.approx(612.0)


def test_images_to_pdf_auto_orientation_picks_landscape_for_wide_image(
    tmp_path: Path,
) -> None:
    wide = _write_png(tmp_path / "wide.png", size=(20, 10))
    out = tmp_path / "out.pdf"

    imagetopdf.images_to_pdf(
        [wide], out, page_size="Letter", orientation="auto"
    )

    with PDDocument.load(out) as pd:
        mb = pd.get_page(0).get_media_box()
        assert mb.get_width() > mb.get_height()


def test_images_to_pdf_auto_orientation_keeps_portrait_for_tall_image(
    tmp_path: Path,
) -> None:
    tall = _write_png(tmp_path / "tall.png", size=(10, 20))
    out = tmp_path / "out.pdf"

    imagetopdf.images_to_pdf(
        [tall], out, page_size="Letter", orientation="auto"
    )

    with PDDocument.load(out) as pd:
        mb = pd.get_page(0).get_media_box()
        # Tall image keeps Letter portrait orientation.
        assert mb.get_width() == pytest.approx(612.0)
        assert mb.get_height() == pytest.approx(792.0)


# ---------------------------------------------------------- CLI surface


def test_cli_basic(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "x.png")
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(["imagetopdf", "-i", str(src), "-o", str(out)])
    assert rc == 0
    assert out.is_file()
    with PDDocument.load(out) as pd:
        assert pd.get_number_of_pages() == 1


def test_cli_multiple_inputs(tmp_path: Path) -> None:
    a = _write_png(tmp_path / "a.png")
    b = _write_png(tmp_path / "b.png")
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(
        ["imagetopdf", "-i", str(a), str(b), "-o", str(out), "-pageSize", "A4"]
    )
    assert rc == 0
    with PDDocument.load(out) as pd:
        assert pd.get_number_of_pages() == 2
        mb = pd.get_page(0).get_media_box()
        assert mb.get_width() == pytest.approx(PDRectangle.A4.get_width())  # type: ignore[attr-defined]


def test_cli_resize_stretches_image_to_full_page(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "x.png", size=(4, 4))
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(
        ["imagetopdf", "-i", str(src), "-o", str(out),
         "-pageSize", "Letter", "-resize"]
    )
    assert rc == 0
    with PDDocument.load(out) as pd:
        page = pd.get_page(0)
        body = page.get_contents()
        # Resize emits a CTM scaled to the full media box (Letter = 612x792)
        # rather than the intrinsic 4x4 pixel size.
        assert b"612 0 0 792" in body


def test_cli_landscape_alias(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "x.png")
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(
        ["imagetopdf", "-i", str(src), "-o", str(out),
         "-pageSize", "Letter", "-landscape"]
    )
    assert rc == 0
    with PDDocument.load(out) as pd:
        mb = pd.get_page(0).get_media_box()
        assert mb.get_width() > mb.get_height()


def test_cli_missing_input_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(
        ["imagetopdf", "-i", str(tmp_path / "ghost.png"), "-o", str(out)]
    )
    assert rc == 4
    assert "not a file" in capsys.readouterr().out
    assert not out.exists()
