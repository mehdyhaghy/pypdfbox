"""Live PDFBox differential for ``PDPageContentStream`` show-text encoding.

``show_text`` / ``show_text_with_positioning`` must encode ``str`` text
through the current font (``font.encode``), track subset code points, and
write the bytes with ``COSWriter.write_string`` (literal form for 7-bit
data without CR/LF, hex form otherwise), exactly like upstream
``PDAbstractContentStream.showTextInternal``.

The ``ShowTextEncodingProbe`` Java oracle builds the same one-page
documents with Apache PDFBox 3.0.8 and prints each page's decoded content
stream as hex; this module builds them with pypdfbox and compares line by
line. Fonts covered: Standard 14 Helvetica (WinAnsiEncoding),
``PDTrueTypeFont.load`` with WinAnsiEncoding, and ``PDType0Font.load``
(subset and non-subset). The Type 0 subset case is also saved, reloaded
and text-extracted on both sides.

Line grammar (must match ``archive/oracle/probes/ShowTextEncodingProbe.java``)::

    case \\t OK \\t HEX
    case \\t ERR \\t ExceptionSimpleName
    case.text \\t extracted-text
"""

from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import WinAnsiEncoding
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_TTF = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)

# Java exception simple name for each pypdfbox exception type.
_EXC_NAMES = {RuntimeError: "IllegalStateException", ValueError: "IllegalArgumentException"}

# Cases whose pypdfbox output intentionally differs from upstream.
# helv_unencodable: PDFont.encode substitutes "?" for a character the font
# cannot encode (permanent, documented divergence); upstream throws
# IllegalArgumentException.
_PINNED = {
    "helv_unencodable": (
        "helv_unencodable\tOK\t"
        + b"BT\n/F1 12 Tf\n(?) Tj\nET\n".hex().upper()
    ),
}


def _helv(_doc: PDDocument) -> Any:
    return PDType1Font.standard14("Helvetica")


def _true_type(doc: PDDocument) -> Any:
    return PDTrueTypeFont.load(doc, str(_TTF), WinAnsiEncoding.INSTANCE)


def _type0(doc: PDDocument) -> Any:
    return PDType0Font.load(doc, str(_TTF))


def _type0_full(doc: PDDocument) -> Any:
    return PDType0Font.load(doc, str(_TTF), embed_subset=False)


def _run(
    name: str,
    factory: Callable[[PDDocument], Any],
    body: Callable[[PDPageContentStream], None],
    extract: bool = False,
) -> list[str]:
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        font = factory(doc)
        cs = PDPageContentStream(doc, page)
        try:
            cs.begin_text()
            cs.set_font(font, 12)
            body(cs)
            cs.end_text()
        except (RuntimeError, ValueError) as exc:
            return [f"{name}\tERR\t{_EXC_NAMES[type(exc)]}"]
        finally:
            cs.close()
        lines = [f"{name}\tOK\t{page.get_contents().hex().upper()}"]
        if extract:
            buf = io.BytesIO()
            doc.save(buf)
            with PDDocument.load(buf.getvalue()) as reloaded:
                text = PDFTextStripper().get_text(reloaded)
            lines.append(
                f"{name}.text\t" + text.replace("\r", "\\r").replace("\n", "\\n")
            )
        return lines
    finally:
        doc.close()


def _helv_ascii(cs: PDPageContentStream) -> None:
    cs.new_line_at_offset(10, 20)
    cs.show_text("Hello (World) \\ x")
    cs.show_text_with_positioning(["A", -120.0, "B"])


def _type0_subset(cs: PDPageContentStream) -> None:
    cs.new_line_at_offset(72, 700)
    cs.show_text("AB")
    cs.show_text(" Hello World")
    cs.show_text_with_positioning([" Hi", -50.0, "there"])


def _type0_escapes(cs: PDPageContentStream) -> None:
    # Glyph ids 0x28 / 0x29 / 0x5C need escaping; 0x0A / 0x0D and >= 0x80
    # bytes switch COSWriter.writeString to hex form.
    cs.show_text("EFy")
    cs.show_text("'*")
    cs.show_text("\u00be\u013d")


def _type0_full_body(cs: PDPageContentStream) -> None:
    cs.show_text("AB")
    cs.show_text_with_positioning(["C", 10.0, "D"])


def _font_popped_by_restore(cs: PDPageContentStream) -> None:
    cs.end_text()
    cs.save_graphics_state()
    cs.set_font(PDType1Font.standard14("Courier"), 10)
    cs.restore_graphics_state()
    cs.restore_graphics_state()
    cs.begin_text()
    cs.show_text("x")


def _python_lines() -> list[str]:
    lines: list[str] = []
    lines += _run("helv_ascii", _helv, _helv_ascii)
    lines += _run(
        "helv_winansi", _helv, lambda cs: cs.show_text("\u20ac\u00e9 \u0152\u201c\u201d")
    )
    lines += _run("helv_unencodable", _helv, lambda cs: cs.show_text("\u0416"))

    def _tt_body(cs: PDPageContentStream) -> None:
        cs.show_text("AB \u00e9")
        cs.show_text_with_positioning(["Hi", -50.0, "(x)"])

    lines += _run("truetype_winansi", _true_type, _tt_body)
    lines += _run("type0_subset", _type0, _type0_subset, extract=True)
    lines += _run("type0_escapes", _type0, _type0_escapes)
    lines += _run("type0_full", _type0_full, _type0_full_body)
    lines += _run("font_popped_by_restore", _helv, _font_popped_by_restore)
    return lines


@pytest.fixture(scope="module")
def java_lines(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    scratch = tmp_path_factory.mktemp("show_text_probe")
    out = run_probe_text("ShowTextEncodingProbe", str(_TTF), str(scratch))
    return {line.split("\t", 1)[0]: line for line in out.splitlines() if line}


@pytest.fixture(scope="module")
def python_lines() -> dict[str, str]:
    return {line.split("\t", 1)[0]: line for line in _python_lines()}


_CASES = [
    "helv_ascii",
    "helv_winansi",
    "helv_unencodable",
    "truetype_winansi",
    "type0_subset",
    "type0_subset.text",
    "type0_escapes",
    "type0_full",
    "font_popped_by_restore",
]


@requires_oracle
@pytest.mark.parametrize("case", _CASES)
def test_show_text_matches_pdfbox(
    case: str, java_lines: dict[str, str], python_lines: dict[str, str]
) -> None:
    assert case in java_lines, f"probe emitted no line for {case}"
    if case in _PINNED:
        # Pinned both sides: upstream throws, pypdfbox substitutes.
        assert java_lines[case] == f"{case}\tERR\tIllegalArgumentException"
        assert python_lines[case] == _PINNED[case]
        return
    assert python_lines[case] == java_lines[case]
