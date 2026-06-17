"""Live PDFBox differential parity for content-stream GENERATION.

Does pypdfbox's :class:`PDPageContentStream` emit the same content-stream
operators (and operands) as Apache PDFBox for an identical sequence of
drawing calls?

The Java side is ``oracle/probes/ContentGenProbe.java``: it builds a
one-page PDF with a FIXED sequence of ``PDPageContentStream`` calls
(save/transform, line state, every device colour space stroking +
non-stroking, path construction + painting, a text block, restore),
saves it, re-parses the page with ``PDFStreamParser`` and emits a
canonical token stream (``OP:`` / ``INT:`` / ``REAL:`` / ``NAME:`` /
``STR:`` / ``ARRAY:`` ...).

Here we reproduce the byte-for-byte identical drawing sequence with
pypdfbox's :class:`PDPageContentStream`, tokenise the generated buffer
with our own :class:`PDFStreamParser`, render the same canonical grammar,
and assert the streams match.

Normalisation (legitimate, format-only differences — NOT operator bugs):

- **Float operands** are canonicalised with the same rule the tokenize
  oracle uses (round to 5 decimals HALF_EVEN, strip trailing zeros / dot),
  so a ``2.5`` operand compares equal regardless of whether one side
  carried it as an int-valued float vs the other as a real.
- **Numeric int-vs-real classification** is collapsed: an integral operand
  is compared by value, not by whether the parser tagged it ``INT`` or
  ``REAL``. PDFBox round-trips ``2.5 w`` through its writer as a COSFloat
  but ``1 J`` as a COSInteger; pypdfbox formats whole-valued floats as
  bare integers. Both are valid PDF numbers — only the *value* matters.
- **Auto-allocated resource keys** (the ``/Fn`` font name in ``Tf``) are
  arbitrary per-implementation slots (PDFBox emits ``/F1``, pypdfbox
  ``/F0``). The name token preceding a ``Tf`` operator is normalised to a
  placeholder so the resource-slot number does not count as a divergence.

A missing / extra / wrong OPERATOR, or a wrong operand *value*, is a real
bug and fails the assertion.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_EVEN, Decimal

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from tests.oracle.harness import requires_oracle, run_probe_text


def _canon_float(value: float) -> str:
    """Locale-independent canonical float — matches ``ContentGenProbe``/
    ``TokenizeProbe.canonFloat``: round to 5 decimals HALF_EVEN, strip
    trailing zeros / dot, normalise ``-0`` to ``0``."""
    d = Decimal(repr(float(value))).quantize(
        Decimal("0.00001"), rounding=ROUND_HALF_EVEN
    ).normalize()
    s = format(d, "f")
    if s == "-0":
        s = "0"
    return s


def _py_draw(cs: PDPageContentStream, font: PDType1Font) -> None:
    """Reproduce ``ContentGenProbe.drawFixedSequence`` byte-for-byte."""
    # --- graphics state save + transform ---
    cs.save_graphics_state()
    cs.transform(1, 0, 0, 1, 10, 20)

    # --- line state ---
    cs.set_line_width(2.5)
    cs.set_line_cap_style(1)
    cs.set_line_join_style(2)
    cs.set_miter_limit(4.0)
    cs.set_line_dash_pattern([3, 2], 1)

    # --- colors (every device space, stroking + non-stroking) ---
    cs.set_stroking_color(1.0, 0.0, 0.0)          # RG
    cs.set_non_stroking_color(0.0, 1.0, 0.0)      # rg
    cs.set_stroking_color(0.25)                   # G  (gray)
    cs.set_non_stroking_color(0.75)               # g
    cs.set_stroking_color(0.1, 0.2, 0.3, 0.4)     # K  (cmyk)
    cs.set_non_stroking_color(0.5, 0.6, 0.7, 0.8)  # k

    # --- path construction + painting ---
    cs.move_to(0, 0)
    cs.line_to(50, 0)
    cs.curve_to(60, 10, 70, 20, 80, 30)
    cs.add_rect(5, 5, 20, 20)
    cs.close_path()
    cs.fill_and_stroke()

    cs.move_to(100, 100)
    cs.line_to(150, 150)
    cs.stroke()

    cs.add_rect(200, 200, 30, 40)
    cs.fill()

    # --- text block ---
    cs.begin_text()
    cs.set_font(font, 12)
    cs.set_leading(14)
    cs.new_line_at_offset(15, 200)
    cs.show_text("Hello")
    cs.new_line()
    cs.show_text("World")
    # String-escaping stress (see ContentGenProbe.drawFixedSequence):
    # balanced parens, backslash, non-ASCII. Both impls escape ( ) \ in
    # the ASCII-safe literal form and fall back to hex for non-ASCII; the
    # tokenizer compares the decoded bytes, so a wrong escape would fail.
    cs.new_line()
    cs.show_text("paren (a) and \\backslash")
    cs.new_line()
    cs.show_text("café é")
    cs.end_text()

    # --- restore ---
    cs.restore_graphics_state()


def _tokenize_py(data: bytes) -> list[str]:
    """Tokenise ``data`` with pypdfbox's PDFStreamParser, rendering the
    same canonical grammar ContentGenProbe emits."""
    lines: list[str] = []
    parser = PDFStreamParser.from_bytes(data)
    try:
        for tok in parser.parse():
            _emit(lines, tok)
    finally:
        parser.close()
    return lines


def _emit(lines: list[str], tok: object) -> None:
    if isinstance(tok, Operator):
        lines.append(f"OP:{tok.get_name()}")
    else:
        _emit_base(lines, tok)


def _emit_base(lines: list[str], b: object) -> None:
    if isinstance(b, COSInteger):
        lines.append(f"INT:{b.long_value()}")
    elif isinstance(b, COSFloat):
        lines.append(f"REAL:{_canon_float(b.float_value())}")
    elif isinstance(b, COSName):
        lines.append(f"NAME:/{b.get_name()}")
    elif isinstance(b, COSString):
        lines.append(f"STR:{b.get_bytes().hex()}")
    elif isinstance(b, COSBoolean):
        lines.append(f"BOOL:{'true' if b.get_value() else 'false'}")
    elif isinstance(b, COSNull):
        lines.append("NULL")
    elif isinstance(b, COSArray):
        lines.append(f"ARRAY:{len(b)}")
        for el in b:
            _emit_base(lines, el)
    elif isinstance(b, COSDictionary):
        keys = list(b.key_set())
        lines.append(f"DICT:{len(keys)}")
        for key in keys:
            lines.append(f"NAME:/{key.get_name()}")
            _emit_base(lines, b.get_dictionary_object(key))
    else:
        lines.append(f"COS:{type(b).__name__}")


# A numeric token line: capture INT/REAL value for value-based comparison.
_NUM_RE = re.compile(r"^(INT|REAL):(.+)$")


def _normalize(lines: list[str]) -> list[str]:
    """Collapse legitimate format-only differences so only operator
    structure + operand *values* are compared.

    - INT:n and REAL:n that denote the same numeric value compare equal
      (token rendered as ``NUM:<canon>``).
    - The font resource-key NAME immediately preceding a ``Tf`` operator
      is replaced with ``NAME:/<font-key>`` (the slot number is arbitrary).
    """
    out: list[str] = []
    for line in lines:
        m = _NUM_RE.match(line)
        if m:
            out.append(f"NUM:{_canon_float(float(m.group(2)))}")
        else:
            out.append(line)
    # Normalise the font key: the NAME token right before OP:Tf.
    for i, line in enumerate(out):
        if line == "OP:Tf" and i >= 2 and out[i - 1].startswith("NUM:") \
                and out[i - 2].startswith("NAME:/"):
            out[i - 2] = "NAME:/<font-key>"
    return out


@requires_oracle
def test_content_generation_matches_pdfbox(tmp_path) -> None:
    out_pdf = tmp_path / "content_gen.pdf"
    java_raw = run_probe_text("ContentGenProbe", str(out_pdf))
    java = _normalize([ln for ln in java_raw.splitlines() if ln])

    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 300.0, 400.0))
        doc.add_page(page)
        font = PDType1Font()
        font.get_cos_object().set_name(
            COSName.get_pdf_name("BaseFont"), "Helvetica"
        )
        with PDPageContentStream(doc, page) as cs:
            _py_draw(cs, font)
        body = page.get_contents()
    finally:
        doc.close()

    py = _normalize(_tokenize_py(body))

    assert py == java, (
        "content-stream token streams diverge from PDFBox.\n"
        f"--- pypdfbox ---\n{chr(10).join(py)}\n"
        f"--- java ---\n{chr(10).join(java)}"
    )
