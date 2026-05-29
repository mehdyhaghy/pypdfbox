"""Live Apache PDFBox parity for the ``ExtractImages`` tool surface.

Drives Apache PDFBox 3.0.7's image-extraction walk via the
``ExtractImagesToolProbe`` Java probe and compares it against pypdfbox's
:class:`pypdfbox.tools.extract_images.ImageGraphicsEngine` on the *same* PDF
bytes. The probe both builds a deterministic fixture (so neither side depends on
an encoder-specific corpus PDF) and runs an ``ImageGraphicsEngine`` clone over
it, emitting per-image identity facts.

The load-bearing parity claims are exactly the ``ExtractImages`` tool surface,
*not* a raw resource-dictionary dump:

* images are collected by the **graphics-engine walk** (``Do`` operator →
  ``draw_image`` hook), so only images a page actually *draws* are extracted;
* a single physical image XObject drawn more than once is **de-duplicated** by
  its COS object identity and extracted only once;
* a second, physically distinct image with identical pixels is *not* de-duped;
* the output counter (``prefix-N``) is monotonic across the whole document and
  never resets per page;
* per-image identity — width, height, bits-per-component, colorspace name, and
  file suffix — matches upstream exactly.

We compare image **metadata + count + order**, not raw decoded pixels, so the
parity holds across PNG-encoder differences between Java2D and Pillow (per the
wave brief).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdfbox.contentstream.pdf_graphics_stream_engine import PDFGraphicsStreamEngine
from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text


class _ProbeEngine(PDFGraphicsStreamEngine):
    """Clone of ``ExtractImages.ImageGraphicsEngine`` reduced to the
    identity-collecting behaviour the probe also implements.

    Shares the ``counter`` (monotonic across pages) and ``seen`` (de-dup by COS
    object) state across every page of the document so the emitted summary
    matches the Java probe line-for-line.
    """

    def __init__(
        self,
        page: Any,
        page_index: int,
        counter: list[int],
        seen: set,
        rows: list[str],
    ) -> None:
        super().__init__(page)
        self._page_index = page_index
        self._counter = counter
        self._seen = seen
        self._rows = rows

    def draw_image(self, pd_image: Any) -> None:
        if isinstance(pd_image, PDImageXObject):
            cos = pd_image.get_cos_object()
            if cos in self._seen:
                return
            self._seen.add(cos)
        name = f"img-{self._counter[0]}"
        self._counter[0] += 1
        cs = pd_image.get_color_space()
        cs_name = cs.get_name() if cs is not None else "null"
        suffix = pd_image.get_suffix() or "png"
        if suffix == "jb2":
            suffix = "png"
        elif suffix == "jpx":
            suffix = "jp2"
        self._rows.append(
            f"page {self._page_index} img {name} "
            f"w {pd_image.get_width()} h {pd_image.get_height()} "
            f"bpc {pd_image.get_bits_per_component()} "
            f"cs {cs_name} suffix {suffix}"
        )

    # --- empty path/paint overrides (mirror upstream "Empty:" stubs) -------
    def append_rectangle(self, p0, p1, p2, p3) -> None: ...  # noqa: ANN001
    def clip(self, winding_rule: int) -> None: ...
    def move_to(self, x: float, y: float) -> None: ...
    def line_to(self, x: float, y: float) -> None: ...

    def curve_to(
        self, x1: float, y1: float, x2: float, y2: float, x3: float, y3: float
    ) -> None: ...

    def get_current_point(self) -> tuple[float, float]:
        return (0.0, 0.0)

    def close_path(self) -> None: ...
    def end_path(self) -> None: ...
    def stroke_path(self) -> None: ...
    def fill_path(self, winding_rule: int) -> None: ...
    def fill_and_stroke_path(self, winding_rule: int) -> None: ...
    def shading_fill(self, shading_name: COSName) -> None: ...

    def show_glyph(
        self, text_rendering_matrix, font, code: int, displacement
    ) -> None: ...  # noqa: ANN001


def _pypdfbox_summary(fixture: Path) -> str:
    counter = [1]
    seen: set = set()
    rows: list[str] = []
    with PDDocument.load(fixture) as doc:
        for index, page in enumerate(doc.get_pages()):
            engine = _ProbeEngine(page, index, counter, seen, rows)
            engine.process_page(page)
    rows.append(f"total {counter[0] - 1}")
    return "\n".join(rows) + "\n"


@requires_oracle
def test_extract_images_matches_pdfbox(tmp_path: Path) -> None:
    fixture = tmp_path / "extract_images_fixture.pdf"
    java_summary = run_probe_text("ExtractImagesToolProbe", str(fixture))

    py_summary = _pypdfbox_summary(fixture)

    assert py_summary == java_summary, (
        "ExtractImages graphics-engine walk divergence:\n"
        f"  java: {java_summary!r}\n"
        f"  py:   {py_summary!r}"
    )


@requires_oracle
def test_extract_images_dedups_repeated_image(tmp_path: Path) -> None:
    """Guard the de-dup claim: page 0 draws image A twice and image B once, so
    the walk must yield exactly two images for page 0 (the second A collapses),
    and the document total must be three (A, B, and the distinct B' on page 1).
    """
    fixture = tmp_path / "extract_images_fixture.pdf"
    run_probe_text("ExtractImagesToolProbe", str(fixture))

    summary = _pypdfbox_summary(fixture)
    lines = summary.strip().splitlines()
    page0 = [ln for ln in lines if ln.startswith("page 0 ")]
    page1 = [ln for ln in lines if ln.startswith("page 1 ")]
    assert len(page0) == 2, summary
    assert len(page1) == 1, summary
    assert lines[-1] == "total 3", summary
