"""Live Apache PDFBox parity for ``org.apache.pdfbox.tools.ImageToPDF``.

Drives Apache PDFBox 3.0.7's ``ImageToPDF`` (via the ``ImageToPdfProbe`` Java
probe, run through picocli so the genuine upstream ``call()`` executes) on a
fixed 64x64 RGB JPEG with the default configuration (Letter media box, no
resize, no orientation change). The probe reloads the result and emits a
canonical structural summary:

* ``pages`` — one page per input image (here: 1),
* ``mediabox`` — the page MediaBox (default = Letter, 612x792 pt; the image is
  *not* scaled to its pixel dimensions under the default config),
* ``xobject`` — whether an image XObject is present on the page (the image is
  drawn via a ``/Do`` on this XObject), and
* ``imgsize`` — the image XObject's pixel dimensions (64x64).

pypdfbox's :class:`pypdfbox.tools.image_to_pdf.ImageToPDF` runs on the same
image and must produce an identical summary, plus a ``qpdf --check``-clean file.
This pins the single-page build (MediaBox + embedded image XObject + page
count + reloadability) at byte/behaviour parity with upstream.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.tools.image_to_pdf import ImageToPDF
from tests.oracle.harness import requires_oracle, run_probe_text

# A small fixed RGB JPEG (64x64) shared with the DCTDecode fixtures.
_IMAGE = Path(__file__).resolve().parents[2] / "fixtures" / "dct" / "dct_rgb.jpg"


def _summary_from_pdf(pdf_path: Path) -> str:
    """Build the same canonical summary the Java probe emits."""
    lines: list[str] = []
    with PDDocument.load(pdf_path) as doc:
        lines.append(f"pages={doc.get_number_of_pages()}")

        page = doc.get_page(0)
        box = page.get_media_box()
        lines.append(
            "mediabox="
            f"{box.get_lower_left_x():.2f},"
            f"{box.get_lower_left_y():.2f},"
            f"{box.get_upper_right_x():.2f},"
            f"{box.get_upper_right_y():.2f}"
        )

        has_image = False
        img_size = "none"
        resources = page.get_resources()
        if resources is not None:
            for name in resources.get_x_object_names():
                xobj = resources.get_x_object(name)
                if isinstance(xobj, PDImageXObject):
                    has_image = True
                    img_size = f"{xobj.get_width()}x{xobj.get_height()}"
                    break
        lines.append(f"xobject={'true' if has_image else 'false'}")
        lines.append(f"imgsize={img_size}")
    return "\n".join(lines) + "\n"


def _pypdfbox_summary(image: Path, out_path: Path) -> str:
    tool = ImageToPDF()
    tool.infiles = [image]
    tool.outfile = out_path
    rc = tool.call()
    assert rc == 0, f"pypdfbox ImageToPDF.call() returned {rc}"
    return _summary_from_pdf(out_path)


@requires_oracle
def test_create_pdf_from_image_matches_pdfbox(tmp_path: Path) -> None:
    java_out = tmp_path / "java.pdf"
    java_summary = run_probe_text(
        "ImageToPdfProbe", str(_IMAGE), str(java_out)
    )

    py_summary = _pypdfbox_summary(_IMAGE, tmp_path / "py.pdf")

    assert py_summary == java_summary, (
        "ImageToPDF single-image build divergence:\n"
        f"  java: {java_summary!r}\n"
        f"  py:   {py_summary!r}"
    )


@requires_oracle
def test_create_pdf_from_image_is_qpdf_clean(tmp_path: Path) -> None:
    """The pypdfbox output must pass ``qpdf --check`` with no errors."""
    qpdf = shutil.which("qpdf")
    if qpdf is None:
        pytest.skip("qpdf not available")

    out = tmp_path / "py.pdf"
    _pypdfbox_summary(_IMAGE, out)

    result = subprocess.run(
        [qpdf, "--check", str(out)],
        check=False,
        capture_output=True,
        text=True,
    )
    # qpdf returns 0 (clean) or 3 (warnings only); 2 = errors.
    assert result.returncode in (0, 3), (
        f"qpdf --check reported errors:\n{result.stdout}\n{result.stderr}"
    )
    # The boilerplate footer contains the word "errors"; key on qpdf's
    # explicit clean-bill-of-health line instead.
    assert "No syntax or stream encoding errors found" in result.stdout, (
        result.stdout
    )
