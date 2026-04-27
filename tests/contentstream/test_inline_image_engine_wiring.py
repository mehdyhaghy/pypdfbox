"""Engine-level wiring of the BI / ID / EI inline-image operator triplet.

Asserts that ``PDFStreamEngine`` (and the graphics-engine subclass)
construct a :class:`PDInlineImage` from the parser-collated ``BI``
operator and forward it to the :meth:`show_inline_image` hook, with
``PDFGraphicsStreamEngine`` defaulting to ``draw_image`` so subclasses
need only model one paint path.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.contentstream.pdf_graphics_stream_engine import (
    PDFGraphicsStreamEngine,
)
from pypdfbox.contentstream.pdf_stream_engine import PDFStreamEngine
from pypdfbox.cos import COSBase, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage


# 2x2 grayscale raster — 4 bytes (one per pixel) in DeviceGray @ 8 bpc.
_RASTER_2x2_GRAY: bytes = bytes([0x10, 0x20, 0x30, 0x40])

# Content stream: BI dictionary followed by ID + raw bytes + EI.
# Per PDF 32000-1 §8.9.7 we use the abbreviated keys (W/H/CS/BPC). The
# trailing ``\n`` before ``EI`` is the mandated separator; the parser
# treats it as part of the image payload (mirrors upstream PDFBox's
# ``hasNoFollowingBinData`` boundary detection — a single whitespace
# byte before ``EI`` is kept in the data slot).
_INLINE_STREAM = (
    b"BI\n"
    b"/W 2 /H 2 /CS /G /BPC 8\n"
    b"ID\n"
    + _RASTER_2x2_GRAY
    + b"\nEI\n"
)
# The parser appends the leading separator (``\n``) into the data —
# this is the on-the-wire payload the engine forwards to PDInlineImage.
_DATA_AS_PARSED: bytes = _RASTER_2x2_GRAY + b"\n"


class _RecordingEngine(PDFStreamEngine):
    """Engine that records every ``show_inline_image`` invocation."""

    def __init__(self) -> None:
        super().__init__()
        self.inline_images: list[PDInlineImage] = []

    def show_inline_image(self, inline_image: PDInlineImage) -> None:
        self.inline_images.append(inline_image)


class _RecordingGraphicsEngine(PDFGraphicsStreamEngine):
    """Graphics-engine subclass that records every ``draw_image``
    invocation. The base ``show_inline_image`` should delegate here."""

    def __init__(self) -> None:
        super().__init__(page=None)
        self.drawn: list[Any] = []

    # Path / paint hooks — not exercised here; provide no-ops so the
    # abstract method NotImplementedError never fires for the BI route.
    def append_rectangle(self, p0, p1, p2, p3) -> None:  # noqa: ANN001, D401
        return

    def draw_image(self, pd_image: Any) -> None:
        self.drawn.append(pd_image)

    def clip(self, winding_rule: int) -> None:
        return

    def move_to(self, x: float, y: float) -> None:
        return

    def line_to(self, x: float, y: float) -> None:
        return

    def curve_to(self, *args: float) -> None:
        return

    def get_current_point(self) -> tuple[float, float] | None:
        return None

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


# ---------- PDFStreamEngine.show_inline_image hook ----------


def test_show_inline_image_default_is_no_op() -> None:
    """Base class default: silently no-op (subclass override territory)."""
    engine = PDFStreamEngine()
    # Construct a minimal valid PDInlineImage by hand — bypasses the
    # BI/ID parser path; we only want to prove the hook signature.
    params = COSDictionary()
    params.set_int(COSName.get_pdf_name("W"), 1)
    params.set_int(COSName.get_pdf_name("H"), 1)
    params.set_int(COSName.get_pdf_name("BPC"), 8)
    params.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("G"))
    image = PDInlineImage(params, b"\x00", None)
    # Should not raise.
    engine.show_inline_image(image)


# ---------- end-to-end BI/ID/EI dispatch ----------


def test_bi_id_ei_invokes_show_inline_image_with_pdinlineimage() -> None:
    """Feed a content stream with ``BI ... ID <bytes> EI`` and assert
    the engine constructs a :class:`PDInlineImage` carrying the right
    width / height / colour-space / bytes, and forwards it to
    :meth:`show_inline_image`."""
    engine = _RecordingEngine()
    engine._process_bytes(_INLINE_STREAM)  # noqa: SLF001 — test introspection
    assert len(engine.inline_images) == 1
    image = engine.inline_images[0]
    assert isinstance(image, PDInlineImage)
    assert image.get_width() == 2
    assert image.get_height() == 2
    assert image.get_bits_per_component() == 8
    cs = image.get_color_space()
    assert cs.get_name() == "DeviceGray"
    # No filters → decoded bytes equal the raw bytes the parser
    # captured between ``ID`` and ``EI`` (raster + separator).
    assert image.get_data() == _DATA_AS_PARSED


def test_bi_id_ei_drives_draw_image_through_graphics_engine() -> None:
    """``PDFGraphicsStreamEngine.show_inline_image`` defaults to
    delegating to :meth:`draw_image` — verify the subclass receives
    exactly one image with the expected geometry."""
    engine = _RecordingGraphicsEngine()
    engine._process_bytes(_INLINE_STREAM)  # noqa: SLF001 — test introspection
    assert len(engine.drawn) == 1
    image = engine.drawn[0]
    assert isinstance(image, PDInlineImage)
    assert image.get_width() == 2
    assert image.get_height() == 2


def test_inline_image_dispatch_passes_engine_resources() -> None:
    """The engine's current ``_resources`` is forwarded to
    :class:`PDInlineImage` so /CS lookups against named colour spaces
    can resolve. We don't exercise the lookup path here (DeviceGray is
    self-contained); we just confirm the resources reference travels
    through unchanged."""
    from pypdfbox.pdmodel.pd_resources import PDResources  # local import

    engine = _RecordingEngine()
    resources = PDResources()
    engine._resources = resources  # noqa: SLF001 — test introspection
    engine._process_bytes(_INLINE_STREAM)  # noqa: SLF001 — test introspection
    assert len(engine.inline_images) == 1
    # PDInlineImage stores resources in a private slot; access via the
    # public surface is deliberately limited, so peek under the hood.
    assert engine.inline_images[0]._resources is resources  # noqa: SLF001


def test_bi_with_missing_data_does_not_raise() -> None:
    """Defensive: a malformed BI without an ID payload (or with an
    empty payload) should not abort the dispatch loop. We synthesise
    such an operator directly via :meth:`process_operator`."""
    from pypdfbox.contentstream.operator import Operator

    engine = _RecordingEngine()
    op = Operator.get_operator("BI")
    op.set_image_parameters(COSDictionary())  # empty dict
    op.set_image_data(b"")
    operands: list[COSBase] = []
    # Should not raise, even with a width/height of -1 (unset).
    engine.process_operator(op, operands)
    # The image still gets built (PDInlineImage tolerates -1 dimensions
    # and the renderer's draw_image short-circuits later).
    assert len(engine.inline_images) == 1
