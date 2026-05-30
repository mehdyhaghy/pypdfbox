"""Live Apache PDFBox differential parity for the EXACT BYTES the high-level
``PDPageContentStream`` drawing API emits — operators *and* the float operand
formatter, compared byte-for-byte (not value-canonicalised).

Why a second content-generation oracle?
---------------------------------------
The sibling ``test_content_gen_oracle.py`` compares the *parsed token stream*
after canonicalising every numeric operand (round HALF_EVEN to 5 decimals,
strip trailing zeros). That value-based normalisation is exactly what masks a
*byte-level* formatter divergence: two writers that emit ``12345.6789`` and
``12345.67871`` for the same operand both canonicalise to the same rounded
value, so a token-value comparison passes while a viewer renders different
glyphs.

This test pins the **raw content-stream bytes**. PDFBox's
``PDPageContentStream`` formats every numeric operand by narrowing it to a Java
32-bit ``float`` and running ``NumberFormatUtil.formatFloatFast(value, 5,
buffer)`` — single-precision narrowing plus a truncating half-up round on the
narrowed fraction. ``format(f, ".5f")`` on the Python ``float`` (a 64-bit
double) diverges from this for many ordinary decimals (e.g. ``12345.6789f`` is
``12345.6787109375`` → ``12345.67871``; the float32 of ``0.000005`` is
``4.99999987e-06`` → truncates to ``0``, not ``0.00001``). Wave 1455 fixed the
formatter to replicate ``formatFloatFast``; this oracle pins it.

Two parities are asserted:

1. A fixed drawing script (text show + positioning, path construction +
   painting, gray/rgb/cmyk colour, line width, rect, transform, save/restore)
   produces byte-identical content streams — after normalising only the
   auto-allocated font resource key (``/F1`` upstream vs ``/F0`` pypdfbox), a
   separate resource-slot surface, not a formatting difference.
2. A battery of float-formatter boundary values (float32-narrowing,
   half-up-on-fraction, trailing-zero stripping, negative zero) formats
   byte-identically to upstream's ``writeOperand(float)``.

Decorated ``@requires_oracle`` so it skips without Java + jar. Hand-written.
"""

from __future__ import annotations

import re

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
from pypdfbox.pdmodel.pd_page_content_stream import (
    PDPageContentStream,
    _format_number,
)
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_PROBE = "ContentStreamGenProbe"

# The drawing script, mirroring ContentStreamGenProbe.drawScript() exactly.
_TEXT_LINE_2 = "Line (with parens) and \\ backslash"


def _py_draw_script() -> bytes:
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
        cs = PDPageContentStream(doc, page)
        # --- text block ---
        cs.begin_text()
        cs.set_font(font, 12)
        cs.new_line_at_offset(72, 720)
        cs.show_text("Hello World")
        cs.set_leading(14.5)
        cs.new_line()
        cs.show_text(_TEXT_LINE_2)
        cs.end_text()
        # --- path construction + painting ---
        cs.set_line_width(0.75)
        cs.move_to(100, 100)
        cs.line_to(200, 100.5)
        cs.curve_to(210.25, 110, 220, 120.333, 230, 100)
        cs.stroke()
        # --- rectangle + fill ---
        cs.add_rect(50, 50, 123.456, 78.9)
        cs.fill()
        # --- colour setters: gray / rgb / cmyk ---
        cs.set_stroking_color(0.5)
        cs.set_non_stroking_color(0.1, 0.2, 0.3)
        cs.set_stroking_color(0.11111, 0.22222, 0.33333, 0.44444)
        # --- transform + save/restore ---
        cs.save_graphics_state()
        cs.transform(1, 0, 0, 1, 12.5, 0)
        cs.add_rect(0, 0, 10, 10)
        cs.stroke()
        cs.restore_graphics_state()
        cs.close()
        return bytes(cs.get_target_stream().create_input_stream().read())
    finally:
        doc.close()


def _normalize_font_key(data: bytes) -> bytes:
    """Collapse the auto-allocated font resource key (``/F1`` vs ``/F0``) to a
    placeholder so the resource-slot number — a separate surface — does not
    register as a byte divergence. Only the name preceding a ``Tf`` operator
    is touched."""
    return re.sub(rb"/F\d+(\s+\S+\s+Tf)", rb"/F\1", data)


# Float-formatter boundary battery. Each value exercises a path where the
# float32-narrowing + truncating half-up round of formatFloatFast diverges
# from a naive float64 ``.5f`` format (or pins a case that must still agree).
_NUMBER_BATTERY: tuple[float, ...] = (
    0.5,
    0.000005,  # f32 ~4.99999e-6 -> truncates to 0 (NOT 0.00001)
    0.000004,
    1.000005,
    0.123455,  # f32 -> 0.12346 (half-up), float64 .5f -> 0.12345
    0.123465,
    2.5,
    0.125,
    0.135,
    1.999995,
    0.999995,
    100000.5,
    0.000015,
    0.000025,  # f32 ~2.49999e-5 -> 0.00002 (truncates), .5f -> 0.00003
    12345.6789,  # f32 12345.6787109375 -> 12345.67871
    -0.5,
    -0.000005,  # -> "-0" (negative zero preserved)
    0.1,
    0.2,
    0.3,
    3.14159265,
    0.12,
    0.120,
    100.0,
    0.01,
    0.001,
    0.0001,
)


@requires_oracle
def test_draw_script_bytes_match_pdfbox() -> None:
    """The fixed drawing script emits byte-identical content-stream bytes."""
    java = run_probe(_PROBE, "draw")
    py = _py_draw_script()
    assert _normalize_font_key(py) == _normalize_font_key(java), (
        "content-stream bytes diverge:\n"
        f"  pypdfbox: {py!r}\n  PDFBox:   {java!r}"
    )


@requires_oracle
def test_float_operand_formatter_matches_pdfbox() -> None:
    """Each operand formats byte-identically to ``writeOperand(float)``.

    The Java probe runs every value through a real ``PDPageContentStream`` and
    returns the formatted operand; pypdfbox runs the same value through
    ``_format_number``. The float32-narrowing + truncating-half-up algorithm
    must reproduce upstream digit-for-digit.
    """
    args = [repr(v) for v in _NUMBER_BATTERY]
    java_lines = run_probe_text(_PROBE, "numbers", *args).splitlines()
    assert len(java_lines) == len(_NUMBER_BATTERY)
    for value, java in zip(_NUMBER_BATTERY, java_lines, strict=True):
        py = _format_number(value).decode("ascii")
        assert py == java, (
            f"formatter diverges for {value!r}: pypdfbox={py!r} PDFBox={java!r}"
        )


@requires_oracle
def test_float32_narrowing_boundary_is_pinned() -> None:
    """Spell out the load-bearing float32 expectations so a regression names
    the exact value that drifted (the Java side is pinned by the parity
    test above)."""
    assert _format_number(0.000005) == b"0"
    assert _format_number(-0.000005) == b"-0"
    assert _format_number(0.000025) == b"0.00002"
    assert _format_number(0.123455) == b"0.12346"
    assert _format_number(12345.6789) == b"12345.67871"
    # Exactly-representable / trailing-zero cases still agree.
    assert _format_number(0.125) == b"0.125"
    assert _format_number(0.120) == b"0.12"
    assert _format_number(100.0) == b"100"
