"""Live Apache PDFBox differential parity for the ported
:class:`PlainTextFormatter` word-wrap engine (wave 1508).

Surface
-------
``org.apache.pdfbox.pdmodel.interactive.annotation.layout.PlainTextFormatter``
— the formatter the FreeText appearance handler routes ``/Contents`` through to
break a text block into wrapped lines and emit the ``Td`` / ``Tj`` run that
paints them. The Python port re-exports the formatter / style / text-align from
:mod:`pypdfbox.pdmodel.interactive.form` (functionally identical upstream) and
ships the genuinely-distinct annotation-layout :class:`PlainText` in
:mod:`pypdfbox.pdmodel.interactive.annotation.layout` (no PDFBOX-5049/6082
force-split; distinct empty-paragraph constructor), all surfaced through the
``annotation.layout`` package the FreeText handler imports.

How it works
------------
The Java probe ``PlainTextFormatterProbe`` drives the upstream formatter
directly::

    java ... PlainTextFormatterProbe <width> <fontSize> <align> <wrap> <text>

It writes ``BT`` / ``Tf`` / ``format()`` / ``ET`` into a bare appearance
stream and re-tokenises the result, emitting one ``TOK <op> <operand>...`` line
per operator token with canonical 3-dp floats. pypdfbox runs the **same**
Builder configuration through the ported formatter and renders the parsed
tokens with the identical canonicalisation, so the two op-sequences are
compared token-for-token, operands included.

The single legitimate difference is the auto-assigned font-resource name
(``/F1`` in the probe's fresh ``PDResources`` vs ``/F0`` in pypdfbox's) — that
operand of the leading ``Tf`` is normalised on both sides before comparison.

Parity asserted — EXACT
-----------------------
Across a matrix of multi-paragraph text, long-word overflow (force-split),
``wrapLines`` on/off, LEFT / CENTER / RIGHT / JUSTIFY alignment, unicode text,
the empty string and a trailing newline, the emitted ``Td`` / ``Tj`` cadence
**and operands** match Apache PDFBox 3.0.7 exactly.

Pinned jar quirk (PDFBOX — JUSTIFY single-word line)
----------------------------------------------------
Upstream ``PlainTextFormatter.processLines`` computes the inter-word spacing
for every non-last JUSTIFY line as ``(width - lineWidth) / (words.size() - 1)``
with **no** guard against a single-word line. A single-word non-last line
therefore divides by zero, yielding a non-finite (``Infinity``) operand which
``PDAbstractContentStream.newLineAtOffset`` rejects with
``IllegalArgumentException: Infinity is not a finite number``. The Python port
reproduces this faithfully: ``get_inter_word_spacing`` returns ``inf`` (Java
float div-by-zero semantics) and ``new_line_at_offset`` raises ``ValueError``
(pypdfbox's analogue of the upstream guard). Both sides are pinned to raise on
the same input. Wave 1508 removed an earlier divergent Python ``len(words) > 1``
guard that silently produced ``0`` spacing instead.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.interactive.annotation.layout import (
    AppearanceStyle,
    PlainText,
    PlainTextFormatter,
    TextAlign,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
    PDAppearanceContentStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "PlainTextFormatterProbe"

_ALIGN = {
    "left": TextAlign.LEFT,
    "center": TextAlign.CENTER,
    "right": TextAlign.RIGHT,
    "justify": TextAlign.JUSTIFY,
}


# ---------------------------------------------------------------------------
# canonical operand rendering — mirrors PlainTextFormatterProbe.operand /
# canonFloat (Java): names as ``/name``, numbers HALF_EVEN-rounded to 3 dp,
# COSString as ``COSString{<text>}`` (Java ``COSString.toString()``).
# ---------------------------------------------------------------------------


def _canon_float(value: float) -> str:
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


def _operand(token: object) -> str:
    from pypdfbox.cos import COSName, COSNumber, COSString

    if isinstance(token, COSName):
        return "/" + token.get_name()
    if isinstance(token, COSNumber):
        return _canon_float(token.float_value())
    if isinstance(token, COSString):
        return "COSString{" + token.get_string() + "}"
    return str(token)


def _tok_lines(stream: PDAppearanceStream) -> list[str]:
    """Render the appearance stream's operator tokens into the probe's
    ``TOK <op> <operand>...`` line format (operator first, then its
    preceding operands in order), normalising the leading ``Tf`` font
    name to ``/F`` so the auto-assigned resource index doesn't matter."""
    parser = PDFStreamParser.from_content_stream(stream)
    lines: list[str] = []
    operands: list[str] = []
    while True:
        token = parser.parse_next_token()
        if token is None:
            break
        if isinstance(token, Operator):
            name = token.get_name()
            if name == "Tf" and operands:
                # First operand is the font resource name (/F0 vs /F1).
                operands[0] = "/F"
            line = "TOK " + name
            for op in operands:
                line += " " + op
            lines.append(line)
            operands = []
        else:
            operands.append(_operand(token))
    return lines


def _java_lines(
    width: float, font_size: float, align: str, wrap: str, text: str
) -> list[str]:
    out = run_probe_text(
        _PROBE,
        _canon_float(width),
        _canon_float(font_size),
        align,
        wrap,
        text,
    )
    lines: list[str] = []
    for raw in out.splitlines():
        if not raw.startswith("TOK Tf "):
            lines.append(raw)
            continue
        # normalise the font resource name (/F1 -> /F)
        parts = raw.split(" ")
        parts[2] = "/F"
        lines.append(" ".join(parts))
    return lines


def _py_lines(
    width: float, font_size: float, align: str, wrap: str, text: str
) -> list[str]:
    doc = PDDocument()
    try:
        font = PDType1Font.standard14(PDType1Font.HELVETICA)
        ap = PDAppearanceStream(doc)
        cs = PDAppearanceContentStream(ap)
        cs.begin_text()
        cs.set_font(font, font_size)
        style = AppearanceStyle()
        style.set_font(font)
        style.set_font_size(font_size)
        formatter = (
            PlainTextFormatter.Builder(cs)
            .style(style)
            .text(PlainText(text.replace("\\n", "\n")))
            .width(width)
            .wrap_lines(wrap != "nowrap")
            .initial_offset(0, 0)
            .text_align(_ALIGN[align])
            .build()
        )
        formatter.format()
        cs.end_text()
        cs.close()
        return _tok_lines(ap)
    finally:
        doc.close()


# Matrix of (id, width, font_size, align, wrap, text). ``\n`` in text is a
# hard break (the probe replaces the literal ``\n`` substring with a newline,
# and ``_py_lines`` does the same so both sides see identical input).
_CASES = [
    ("left_wrap_multi", 100, 12, "left", "wrap",
     "hello world this is a wrap test of several words"),
    ("left_nowrap", 100, 12, "left", "nowrap",
     "hello world this is a wrap test"),
    ("center_wrap", 100, 12, "center", "wrap",
     "hello world this is a wrap test"),
    ("right_wrap", 100, 12, "right", "wrap",
     "hello world this is a wrap test"),
    ("justify_wrap", 100, 12, "justify", "wrap",
     "hello world this is a wrap test of several words"),
    ("center_nowrap", 120, 12, "center", "nowrap", "centered line"),
    ("right_nowrap", 120, 12, "right", "nowrap", "right line"),
    ("multi_paragraph", 100, 12, "left", "wrap",
     "first line\\nsecond paragraph here\\nthird"),
    ("empty_string", 100, 12, "left", "wrap", ""),
    ("trailing_newline", 100, 12, "left", "wrap", "trailing newline\\n"),
    ("long_word_split", 30, 12, "left", "wrap",
     "supercalifragilisticexpialidocious"),
    ("unicode", 100, 12, "left", "wrap", "café résumé naïve über"),
    ("justify_single_word_last", 100, 12, "justify", "wrap", "singleword"),
    ("justify_two_words", 200, 12, "justify", "wrap", "two words"),
    ("justify_nowrap", 100, 12, "justify", "nowrap",
     "justify nowrap path test"),
    ("big_font_wrap", 80, 18, "left", "wrap", "one two three four five six"),
]


@requires_oracle
@pytest.mark.parametrize(
    ("width", "font_size", "align", "wrap", "text"),
    [c[1:] for c in _CASES],
    ids=[c[0] for c in _CASES],
)
def test_plain_text_formatter_op_sequence_exact(
    width: float, font_size: float, align: str, wrap: str, text: str
) -> None:
    """The ported PlainTextFormatter emits the same ``Td`` / ``Tj`` token
    cadence and operands as Apache PDFBox 3.0.7 for the given input."""
    java = _java_lines(width, font_size, align, wrap, text)
    py = _py_lines(width, font_size, align, wrap, text)
    assert py == java, (
        f"PlainTextFormatter op-sequence diverges for {text!r}\n"
        f" pypdfbox: {py}\n PDFBox:   {java}"
    )


@requires_oracle
def test_justify_single_word_non_last_line_raises_like_pdfbox() -> None:
    """A single-word non-last JUSTIFY line divides by ``words.size() - 1 ==
    0`` upstream, producing a non-finite operand that
    ``newLineAtOffset`` rejects. Upstream raises
    ``IllegalArgumentException: Infinity is not a finite number``; the
    port raises :class:`ValueError` from the same finiteness guard. Both
    sides are pinned to raise on the same input (the probe exits non-zero;
    pypdfbox raises ``ValueError``)."""
    import subprocess

    # Java side: the probe propagates the IllegalArgumentException, exiting
    # non-zero (its stderr names the "not a finite number" guard).
    with pytest.raises(subprocess.CalledProcessError):
        _java_lines(60, 12, "justify", "wrap", "wwwwwwwww ab cd")

    # Python side: the same input raises ValueError from new_line_at_offset.
    with pytest.raises(ValueError, match="finite"):
        _py_lines(60, 12, "justify", "wrap", "wwwwwwwww ab cd")
