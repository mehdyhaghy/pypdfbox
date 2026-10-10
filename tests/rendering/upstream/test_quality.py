"""Port of pdfbox/src/test/java/org/apache/pdfbox/rendering/TestQuality.java

Upstream baseline: PDFBox 3.0.x. The single upstream test depends on the
``PDFBOX-4831.pdf`` fixture which is **not bundled in the PDFBox source
tree** — upstream's Maven build downloads it from the Apache JIRA issue
tracker as part of the ``target/pdfs`` test-data step. pypdfbox does not
ship copyleft-validator or Maven plumbing, so the fixture is not
available locally; the test is skipped with a clear reason. The shape of
the test is preserved so a future fixture bundling can light it up.

The assertion the upstream test makes ("PDF with a 300 dpi bitonal scan
must be bitonal when rendered at 300 dpi and identical to the scan in
the PDF", PDFBOX-4831) is covered for representative bitonal images in
``tests/rendering/test_pdf_renderer_image_color_wave360.py``.

The PDFBOX-5250 and PDFBOX-6077 tests (forward-ported from the unreleased
3.0.9) need JIRA-downloaded PDFs too and skip the same way; synthetic-PDF
equivalents live in
``tests/rendering/test_pattern_in_form_and_stencil_pattern.py``.
"""
from pathlib import Path

import pytest

_TARGET_PDF_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "rendering"


def test_pdfbox4831() -> None:
    """PDFBOX-4831: PDF with a 300 dpi bitonal scan must be bitonal when
    rendered at 300 dpi and identical to the scan in the PDF.
    """
    pdf_file = _TARGET_PDF_DIR / "PDFBOX-4831.pdf"
    if not pdf_file.exists():
        pytest.skip(
            "PDFBOX-4831.pdf is downloaded from JIRA at upstream test-data "
            "time; not bundled in pypdfbox"
        )
    # Test body retained for parity; entered only when the fixture is bundled.
    from pypdfbox import Loader
    from pypdfbox.cos import COSName
    from pypdfbox.pdmodel.graphics.image import PDImageXObject
    from pypdfbox.rendering import PDFRenderer

    with Loader.load_pdf(pdf_file) as doc:
        renderer = PDFRenderer(doc)
        rendered_image = renderer.render_image_with_dpi(0, 300)
        # bitonal check — image must use exactly 2 distinct colors
        unique_pixels = {tuple(rendered_image.getpixel((x, y)))
                        for x in range(rendered_image.width)
                        for y in range(rendered_image.height)}
        assert len(unique_pixels) == 2
        x_object_image = doc.get_page(0).get_resources().get_x_object(
            COSName.get_pdf_name("I0")
        )
        assert isinstance(x_object_image, PDImageXObject)
        extracted_image = x_object_image.get_image()
        assert extracted_image.size == rendered_image.size


def _load_jira_fixture(name: str) -> Path:
    pdf_file = _TARGET_PDF_DIR / name
    if not pdf_file.exists():
        pytest.skip(
            f"{name} is downloaded from JIRA at upstream test-data time; "
            "not bundled in pypdfbox (synthetic coverage in "
            "tests/rendering/test_pattern_in_form_and_stencil_pattern.py)"
        )
    return pdf_file


def _rgb(image, x: int, y: int) -> tuple[int, int, int]:
    return tuple(image.convert("RGB").getpixel((x, y)))[:3]


def test_pdfbox5250() -> None:
    """PDFBOX-5250: a mesh shading pattern used inside a transparency group
    that has its own non-trivial /Matrix must be positioned using that
    group's own initial matrix, not the parent's.
    """
    pdf_file = _load_jira_fixture("PDFBOX-5250-pattern-reduced3.pdf")
    from pypdfbox.pdmodel import PDDocument
    from pypdfbox.rendering import PDFRenderer

    with PDDocument.load(pdf_file) as doc:
        rendered_image = PDFRenderer(doc).render_image_with_dpi(0, 100)
        # a pixel within the shading-pattern-filled text; red-ish, not white
        red, green, _blue = _rgb(rendered_image, 190, 331)
        assert red > 150 and green < 150


def test_pdfbox6077() -> None:
    """PDFBOX-6077: a stencil mask filled with a pattern must not paint the
    gaps between the pattern's own tiles as opaque black.
    """
    pdf_file = _load_jira_fixture("PDFBOX-6077-example.pdf")
    from pypdfbox.pdmodel import PDDocument
    from pypdfbox.rendering import PDFRenderer

    with PDDocument.load(pdf_file) as doc:
        rendered_image = PDFRenderer(doc).render_image_with_dpi(0, 100)
        # a gap between the tiling pattern's own painted tiles stays white
        assert _rgb(rendered_image, 280, 23) == (255, 255, 255)


def test_pdfbox5842() -> None:
    """PDFBOX-6077: a soft mask applied to a pattern that is used as a
    stencil mask fill must still be visible.
    """
    pdf_file = _load_jira_fixture("PDFBOX-5842-reduced.pdf")
    from pypdfbox.pdmodel import PDDocument
    from pypdfbox.rendering import PDFRenderer

    with PDDocument.load(pdf_file) as doc:
        rendered_image = PDFRenderer(doc).render_image_with_dpi(0, 100)
        # a pixel within the soft-masked pattern's map marker icon
        assert _rgb(rendered_image, 267, 1329) != (255, 255, 255)


def test_pdfbox5403() -> None:
    """PDFBOX-5403 / PDFBOX-6077: a stencil mask filled with a pattern
    repeated many times must not show hairline tile seams as visible gaps.
    """
    pdf_file = _load_jira_fixture("PDFBOX-5403-bad-rendering.pdf")
    from pypdfbox.pdmodel import PDDocument
    from pypdfbox.rendering import PDFRenderer

    with PDDocument.load(pdf_file) as doc:
        rendered_image = PDFRenderer(doc).render_image_with_dpi(2, 100)
        # a pixel within a line of text rendered via a pattern-filled stencil
        red, _green, _blue = _rgb(rendered_image, 159, 115)
        assert red < 100
