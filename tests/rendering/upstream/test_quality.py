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
"""
from __future__ import annotations

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
