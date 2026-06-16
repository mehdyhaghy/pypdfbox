"""Wave 1537 — live-oracle parity for the inline-image OPERATOR-PROCESSOR
draw dispatch (the ``BI`` / ``ID`` / ``EI`` engine path).

Where ``InlineImageFuzzProbe`` / ``InlineImageDictProbe`` /
``InlineImageKeyResolveProbe`` exercise the *parser* tokenisation + the parsed
parameter-dict key resolution, this module drives the *graphics-engine* draw
dispatch: how ``BeginInlineImage`` (upstream ``operator.graphics``) builds a
:class:`PDInlineImage` from the parser-collated ``BI`` operator and forwards it
to ``PDFGraphicsStreamEngine.drawImage`` — including upstream's three
short-circuit guards:

1. ``data is None`` / empty → no image built, no draw,
2. ``image.is_empty()`` after decode → no draw,
3. non-stencil image while colour operators are suppressed → no draw.

Each case wraps the content stream in a real ``PDPage`` and runs
``engine.process_page(page)`` so the ``BI`` operator executes inside the genuine
``process_stream_operators`` context (colour-operator flag set true), exactly as
a renderer drives it.

Probe: ``oracle/probes/InlineImageOperatorFuzzProbe.java`` (the Java probe holds
the identical ``CASES`` map and projects the same ``draws=`` / ``img …`` lines).

Wave-1537 real-bug fix this pins: pypdfbox's base-engine ``_dispatch_inline_image``
used to build a :class:`PDInlineImage` and call ``show_inline_image`` even for a
zero-length payload (``zero_byte_data`` → ``draws=1``), diverging from upstream
which short-circuits (``draws=0``). The guards now mirror upstream
``BeginInlineImage.process``.
"""

from __future__ import annotations

import io
from typing import Any

import pytest

from pypdfbox.contentstream.pdf_graphics_stream_engine import (
    PDFGraphicsStreamEngine,
)
from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

# A tiny 2x2 RGB raster payload (2*2*3 = 12 bytes) for the uncompressed case.
_RGB12 = "abcdefghijkl"

# Named fuzz cases — identical content-stream text to the Java probe's CASES.
CASES: dict[str, str] = {
    "rgb_2x2": "BI /W 2 /H 2 /BPC 8 /CS /RGB ID " + _RGB12 + " EI",
    "gray_2x2": "BI /W 2 /H 2 /BPC 8 /CS /G ID abcd EI",
    "long_keys": (
        "BI /Width 2 /Height 2 /BitsPerComponent 8 /ColorSpace /DeviceRGB ID "
        + _RGB12
        + " EI"
    ),
    "stencil": "BI /W 2 /H 2 /IM true ID ab EI",
    "no_width": "BI /H 2 /BPC 8 /CS /G ID abcd EI",
    "no_height": "BI /W 2 /BPC 8 /CS /G ID abcd EI",
    "no_bpc": "BI /W 2 /H 2 /CS /G ID abcd EI",
    "no_cs": "BI /W 2 /H 2 /BPC 8 ID abcd EI",
    "empty_dict": "BI ID abcd EI",
    "empty_data": "BI /W 2 /H 2 /BPC 8 /CS /G ID  EI",
    "zero_byte_data": "BI /W 1 /H 1 /BPC 8 /CS /G ID\nEI",
    "zero_dim": "BI /W 0 /H 0 /BPC 8 /CS /G ID abcd EI",
    "unknown_cs": "BI /W 2 /H 2 /BPC 8 /CS /Bogus ID abcd EI",
    "cmyk": "BI /W 1 /H 1 /BPC 8 /CS /CMYK ID abcd EI",
    "indexed": "BI /W 2 /H 2 /BPC 8 /CS [/I /RGB 1 <000000ffffff>] ID abcd EI",
    "ei_no_bi": "EI",
    "two_images": (
        "BI /W 1 /H 1 /BPC 8 /CS /G ID a EI "
        "BI /W 1 /H 1 /BPC 8 /CS /RGB ID abc EI"
    ),
}


class _RecordingGraphicsEngine(PDFGraphicsStreamEngine):
    """Minimal ``PDFGraphicsStreamEngine`` that records every ``draw_image``
    call — the Python analogue of the Java probe's ``RecordingEngine``."""

    def __init__(self, page: PDPage) -> None:
        super().__init__(page)
        self.images: list[Any] = []

    def draw_image(self, pd_image: Any) -> None:
        self.images.append(pd_image)

    def append_rectangle(self, p0: Any, p1: Any, p2: Any, p3: Any) -> None:
        return

    def clip(self, winding_rule: int) -> None:
        return

    def move_to(self, x: float, y: float) -> None:
        return

    def line_to(self, x: float, y: float) -> None:
        return

    def curve_to(self, *args: float) -> None:
        return

    def get_current_point(self) -> tuple[float, float]:
        return (0.0, 0.0)

    def close_path(self) -> None:
        return

    def end_path(self) -> None:
        return

    def stroke_path(self) -> None:
        return

    def fill_path(self, winding_rule: int) -> None:
        return

    def fill_and_stroke_path(self, winding_rule: int) -> None:
        return

    def shading_fill(self, shading_name: COSName) -> None:
        return


def _cs_name(image: Any) -> str:
    try:
        return image.get_color_space().get_name()
    except Exception:  # noqa: BLE001 — colour-space resolution may raise
        return "throw"


def _project(content: str) -> str:
    """Drive a content stream through a recording graphics engine and emit the
    canonical ``draws= / img …`` projection the Java probe produces."""
    threw = False
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        stream = PDStream(doc, io.BytesIO(content.encode("latin-1")))
        page.set_contents(stream)
        engine = _RecordingGraphicsEngine(page)
        try:
            engine.process_page(page)
        except Exception:  # noqa: BLE001 — throw-vs-not is the projected fact
            threw = True
    finally:
        doc.close()

    lines = [f"draws={len(engine.images)} err={'throw' if threw else 'none'}"]
    for image in engine.images:
        lines.append(
            f"img w={image.get_width()} h={image.get_height()} "
            f"bpc={image.get_bits_per_component()} "
            f"stencil={str(image.is_stencil()).lower()} "
            f"cs={_cs_name(image)} "
            f"empty={str(image.is_empty()).lower()}"
        )
    return "\n".join(lines) + "\n"


@requires_oracle
@pytest.mark.parametrize("case", list(CASES), ids=list(CASES))
def test_inline_image_operator_matches_oracle(case: str) -> None:
    """pypdfbox graphics-engine BI-dispatch projection == live PDFBox."""
    java = run_probe_text("InlineImageOperatorFuzzProbe", case)
    py = _project(CASES[case])
    assert py.strip() == java.strip()


def test_zero_byte_payload_skips_draw() -> None:
    """Regression for the wave-1537 fix: a zero-length inline-image payload
    builds no image and fires no draw hook — upstream
    ``BeginInlineImage.process`` short-circuit (oracle: ``draws=0``)."""
    assert _project(CASES["zero_byte_data"]).strip() == "draws=0 err=none"


def test_stencil_draws_regardless_of_colour_flag() -> None:
    """A stencil (``/IM true``) inline image always draws — it bypasses the
    non-stencil colour-suppression guard."""
    out = _project(CASES["stencil"])
    assert out.startswith("draws=1 err=none")
    assert "stencil=true" in out
