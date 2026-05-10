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


# ---------------------------------------------- extended page-size catalog


@pytest.mark.parametrize(
    ("page_size", "want_w", "want_h"),
    [
        ("Executive", 522.0, 756.0),
        ("Tabloid", 792.0, 1224.0),
        ("Ledger", 792.0, 1224.0),
        ("US-Legal", 612.0, 1008.0),
        ("us_legal", 612.0, 1008.0),
        ("A3", 842.0, 1191.0),
        ("B5", 499.0, 709.0),
    ],
)
def test_images_to_pdf_extended_page_sizes(
    tmp_path: Path, page_size: str, want_w: float, want_h: float,
) -> None:
    src = _write_png(tmp_path / "x.png")
    out = tmp_path / "out.pdf"

    imagetopdf.images_to_pdf([src], out, page_size=page_size)

    with PDDocument.load(out) as pd:
        mb = pd.get_page(0).get_media_box()
        assert mb.get_width() == pytest.approx(want_w)
        assert mb.get_height() == pytest.approx(want_h)


def test_images_to_pdf_unknown_page_size_falls_back_to_letter(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "x.png")
    out = tmp_path / "out.pdf"

    imagetopdf.images_to_pdf([src], out, page_size="bogus-name")

    with PDDocument.load(out) as pd:
        mb = pd.get_page(0).get_media_box()
        assert mb.get_width() == pytest.approx(612.0)
        assert mb.get_height() == pytest.approx(792.0)


# --------------------------------------------------------- margin handling


def test_images_to_pdf_margin_no_resize_offsets_image(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "x.png", size=(4, 4))
    out = tmp_path / "out.pdf"

    imagetopdf.images_to_pdf(
        [src], out, page_size="Letter", margin_pt=36.0,
    )

    with PDDocument.load(out) as pd:
        page = pd.get_page(0)
        # Page size unchanged: margin is white-space inside the page box.
        mb = page.get_media_box()
        assert mb.get_width() == pytest.approx(612.0)
        assert mb.get_height() == pytest.approx(792.0)
        # Image XObject is drawn at intrinsic 4x4 pt at the lower-left of
        # the printable area, i.e. (margin, margin) = (36, 36).
        body = page.get_contents()
        assert b"4 0 0 4 36 36 cm" in body


def test_images_to_pdf_margin_with_resize_fits_aspect_ratio(tmp_path: Path) -> None:
    # 200x100 image, Letter page (612x792), margin 36 -> printable 540x720.
    # Aspect-fit gives min(540/200, 720/100) = 2.7 -> 540x270.
    src = _write_png(tmp_path / "wide.png", size=(200, 100))
    out = tmp_path / "out.pdf"

    imagetopdf.images_to_pdf(
        [src], out, page_size="Letter", resize=True, margin_pt=36.0,
    )

    with PDDocument.load(out) as pd:
        page = pd.get_page(0)
        body = page.get_contents()
        # Drawn at 540x270, centered horizontally (offset 36 + 0 = 36)
        # and vertically (36 + (720-270)/2 = 36 + 225 = 261).
        assert b"540 0 0 270 36 261 cm" in body


def test_images_to_pdf_margin_auto_page_size_grows_page(tmp_path: Path) -> None:
    # auto: page = image-size + 2*margin on each axis.
    src = _write_png(tmp_path / "x.png", size=(100, 60))
    out = tmp_path / "out.pdf"

    imagetopdf.images_to_pdf(
        [src], out, page_size="auto", margin_pt=20.0,
    )

    with PDDocument.load(out) as pd:
        mb = pd.get_page(0).get_media_box()
        assert mb.get_width() == pytest.approx(140.0)
        assert mb.get_height() == pytest.approx(100.0)


# ----------------------------------------------------- CLI surface (new flags)


def test_cli_long_form_page_size(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "x.png")
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(
        ["imagetopdf", "-i", str(src), "-o", str(out), "--page-size", "Executive"]
    )
    assert rc == 0
    with PDDocument.load(out) as pd:
        mb = pd.get_page(0).get_media_box()
        assert mb.get_width() == pytest.approx(522.0)
        assert mb.get_height() == pytest.approx(756.0)


def test_cli_portrait_alias_keeps_portrait_orientation(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "x.png")
    out = tmp_path / "out.pdf"
    # --portrait alone is the explicit-default form.
    rc = cli.run_cli(
        ["imagetopdf", "-i", str(src), "-o", str(out),
         "-pageSize", "Letter", "--portrait"]
    )
    assert rc == 0
    with PDDocument.load(out) as pd:
        mb = pd.get_page(0).get_media_box()
        # Portrait Letter.
        assert mb.get_width() == pytest.approx(612.0)
        assert mb.get_height() == pytest.approx(792.0)


def test_cli_auto_orientation_beats_landscape(tmp_path: Path) -> None:
    """Documented precedence: --auto-orientation overrides --landscape
    (mirrors upstream where -autoOrientation supersedes -landscape)."""
    tall = _write_png(tmp_path / "tall.png", size=(10, 20))
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(
        ["imagetopdf", "-i", str(tall), "-o", str(out),
         "-pageSize", "Letter", "--landscape", "--auto-orientation"]
    )
    assert rc == 0
    with PDDocument.load(out) as pd:
        mb = pd.get_page(0).get_media_box()
        # Tall image + auto -> portrait (overrides --landscape).
        assert mb.get_width() == pytest.approx(612.0)
        assert mb.get_height() == pytest.approx(792.0)


def test_cli_auto_orientation_long_form(tmp_path: Path) -> None:
    wide = _write_png(tmp_path / "wide.png", size=(20, 10))
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(
        ["imagetopdf", "-i", str(wide), "-o", str(out),
         "-pageSize", "Letter", "--auto-orientation"]
    )
    assert rc == 0
    with PDDocument.load(out) as pd:
        mb = pd.get_page(0).get_media_box()
        assert mb.get_width() > mb.get_height()


def test_cli_margin_pt(tmp_path: Path) -> None:
    src = _write_png(tmp_path / "x.png", size=(4, 4))
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(
        ["imagetopdf", "-i", str(src), "-o", str(out),
         "-pageSize", "Letter", "--margin-pt", "72"]
    )
    assert rc == 0
    with PDDocument.load(out) as pd:
        page = pd.get_page(0)
        body = page.get_contents()
        # 1-inch margin: image positioned at (72, 72).
        assert b"4 0 0 4 72 72 cm" in body


def test_cli_negative_margin_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = _write_png(tmp_path / "x.png")
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(
        ["imagetopdf", "-i", str(src), "-o", str(out), "--margin-pt", "-5"]
    )
    assert rc == 4
    assert "must be >= 0" in capsys.readouterr().out
    assert not out.exists()


def test_cli_help_smoke(capsys: pytest.CaptureFixture[str]) -> None:
    """The subcommand --help should render without raising."""
    with pytest.raises(SystemExit) as excinfo:
        cli.run_cli(["imagetopdf", "--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    # Sanity-check that the new flags appear in the help text.
    assert "--margin-pt" in out
    assert "--auto-orientation" in out
    assert "--page-size" in out


def test_cli_multipage_with_extended_page_size(tmp_path: Path) -> None:
    """End-to-end: three inputs + Tabloid page size + margin → 3 pages."""
    paths = [
        _write_png(tmp_path / "a.png", color=(255, 0, 0)),
        _write_jpeg(tmp_path / "b.jpg"),
        _write_png(tmp_path / "c.png", color=(0, 0, 255)),
    ]
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(
        ["imagetopdf",
         "-i", *(str(p) for p in paths),
         "-o", str(out),
         "--page-size", "Tabloid",
         "--margin-pt", "18"]
    )
    assert rc == 0
    with PDDocument.load(out) as pd:
        assert pd.get_number_of_pages() == 3
        for i in range(3):
            mb = pd.get_page(i).get_media_box()
            assert mb.get_width() == pytest.approx(792.0)
            assert mb.get_height() == pytest.approx(1224.0)
