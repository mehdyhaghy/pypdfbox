"""Live Apache PDFBox differential parity for the END-TO-END
``PDFTextStripper`` path over a Type0 font whose ``/ToUnicode`` CMap maps
character codes to MULTI-CHARACTER and SURROGATE-PAIR (astral, > U+FFFF)
destinations.

``tests/fontbox/cmap/oracle/test_to_unicode_surrogate_oracle.py`` pins the
*isolated* ``CMap.toUnicode(byte[])`` decode (it feeds a raw CMap stream
straight to the parser). This file is the distinct *end-to-end* counterpart:
a genuine one-page PDF whose Type0 (Identity-H, embedded TrueType) font
carries a ``/ToUnicode`` CMap with surrogate-pair / multi-char ``bfchar``
destinations, run through the whole ``PDType0Font.toUnicode`` ->
``PDFTextStripper`` assembly chain on a real multi-byte content stream.

PDFBox assembles the UTF-16BE destinations (collapsing each surrogate pair
into a single astral code point and keeping multi-char strings intact) into
the extracted text. ``oracle/probes/ToUnicodeSurrogateTextProbe.java`` runs
``PDFTextStripper.getText`` on the same file and emits one ``U+XXXX`` token
per Unicode code point plus the raw text; pypdfbox must match both.

The PDF is built with pypdfbox: a full-embed (``embed_subset=False``) Type0
font gives stable Identity-H two-byte codes for the show-text string, then
the font's ``/ToUnicode`` is overwritten with a CMap that remaps exactly
those codes to the astral / multi-char destinations under test. Because
``PDType0Font.toUnicode`` consults ``/ToUnicode`` first, the extracted text
is governed entirely by the injected CMap.

Decorated ``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "ToUnicodeSurrogateTextProbe"
_TTF = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)
_TO_UNICODE = COSName.get_pdf_name("ToUnicode")

# The string we draw. Five glyphs all present in LiberationSans so the
# Identity-H codes are real GIDs. We do not care what they look like — the
# extracted text is dictated entirely by the injected /ToUnicode below.
_SHOW = "ABCDE"

# /ToUnicode destinations, one per shown glyph (index 0..4). After encoding
# ``_SHOW`` we learn each glyph's actual 2-byte code and build a bfchar
# mapping code -> destination at parse time.
#   glyph 0 -> plain BMP  "X"            (U+0058)
#   glyph 1 -> surrogate  U+1F600        (emoji, <D83DDE00>)
#   glyph 2 -> multi-char "fi"           (U+0066 U+0069)
#   glyph 3 -> astral CJK ext-B U+20BB7  (<D842DFB7>)
#   glyph 4 -> astral + BMP combining    U+1D11E U+0301 (<D834DD1E0301>)
_DESTINATIONS: list[str] = [
    "0058",
    "D83DDE00",
    "00660069",
    "D842DFB7",
    "D834DD1E0301",
]

# The Unicode code points each destination decodes to (the expected
# extracted text, code point by code point). PDFTextStripper appends a
# trailing newline per page.
_EXPECTED_TEXT = (
    "X"
    + chr(0x1F600)
    + "fi"
    + chr(0x20BB7)
    + chr(0x1D11E)
    + chr(0x0301)
    + "\n"
)


def _build_pdf(path: Path) -> None:
    """One-page PDF showing ``_SHOW`` through a full-embed Identity-H Type0
    font whose ``/ToUnicode`` is overwritten so each shown code maps to a
    surrogate-pair / multi-char destination."""
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 400, 200))
        doc.add_page(page)
        # Full embed (no subsetting) so encode() yields stable GID codes and
        # PDFBox can resolve every glyph.
        font = PDType0Font.load(doc, str(_TTF), False)

        codes = font.encode(_SHOW)
        # Identity-H: two bytes per glyph.
        assert len(codes) == 2 * len(_SHOW)
        code_hexes = [
            codes[2 * i : 2 * i + 2].hex().upper() for i in range(len(_SHOW))
        ]

        # Build the /ToUnicode CMap program remapping exactly these codes.
        bfchar_lines = "".join(
            f"<{code_hexes[i]}> <{_DESTINATIONS[i]}>\n" for i in range(len(_SHOW))
        )
        cmap_text = (
            "/CIDInit /ProcSet findresource begin\n"
            "12 dict begin\n"
            "begincmap\n"
            "/CMapName /Adobe-Identity-UCS def\n"
            "/CMapType 2 def\n"
            "1 begincodespacerange\n"
            "<0000> <FFFF>\n"
            "endcodespacerange\n"
            f"{len(_SHOW)} beginbfchar\n"
            f"{bfchar_lines}"
            "endbfchar\n"
            "endcmap\n"
            "CMapName currentdict /CMap defineresource pop\n"
            "end\n"
            "end\n"
        )
        to_unicode = COSStream()
        with to_unicode.create_output_stream() as out:
            out.write(cmap_text.encode("latin-1"))
        font.get_cos_object().set_item(_TO_UNICODE, to_unicode)

        resources = page.get_or_create_resources()
        resources.add(font)
        page.set_resources(resources)

        cs = PDPageContentStream(doc, page)
        cs.begin_text()
        cs.set_font(font, 24.0)
        cs.new_line_at_offset(20.0, 150.0)
        # Emit the raw Identity-H code bytes directly (show_text renders a
        # non-ASCII byte string as a hex literal), so the shown bytes are
        # exactly ``codes``.
        cs.show_text(codes)
        cs.end_text()
        cs.close()

        doc.save(str(path))
    finally:
        doc.close()


def _unescape(s: str) -> str:
    return s.replace("\\r", "\r").replace("\\n", "\n").replace("\\\\", "\\")


def _java_codepoints_and_text(pdf: Path) -> tuple[str, str]:
    out = run_probe_text(_PROBE, str(pdf))
    cps = ""
    text = ""
    for line in out.splitlines():
        if line.startswith("CODEPOINTS:"):
            cps = line[len("CODEPOINTS:") :]
        elif line.startswith("TEXT:"):
            text = _unescape(line[len("TEXT:") :])
    return cps, text


def _py_codepoints_and_text(pdf: Path) -> tuple[str, str]:
    doc = PDDocument.load(str(pdf))
    try:
        stripper = PDFTextStripper()
        stripper.set_sort_by_position(True)
        text = stripper.get_text(doc)
    finally:
        doc.close()
    cps = " ".join(f"U+{ord(ch):04X}" for ch in text)
    return cps, text


def test_python_decodes_expected_codepoints(tmp_path: Path) -> None:
    """Value pin (runs without the oracle): the end-to-end extracted text
    equals the surrogate-pair / multi-char destinations declared in the
    injected ``/ToUnicode`` CMap."""
    pdf = tmp_path / "tounicode_surrogate.pdf"
    _build_pdf(pdf)
    _cps, text = _py_codepoints_and_text(pdf)
    assert text == _EXPECTED_TEXT


@requires_oracle
def test_tounicode_surrogate_text_matches_pdfbox(tmp_path: Path) -> None:
    """pypdfbox's ``PDFTextStripper`` output must equal Apache PDFBox's for a
    Type0 font whose ``/ToUnicode`` maps codes to surrogate-pair and
    multi-char destinations — both the per-code-point ``U+XXXX`` stream and
    the raw extracted text."""
    pdf = tmp_path / "tounicode_surrogate.pdf"
    _build_pdf(pdf)

    java_cps, java_text = _java_codepoints_and_text(pdf)
    py_cps, py_text = _py_codepoints_and_text(pdf)

    assert py_text == java_text
    assert py_cps == java_cps
    # The astral destinations prove the surrogate-pair collapse is exercised
    # (a naive UTF-16 char count would differ from the code-point count).
    assert "U+1F600" in py_cps
    assert "U+20BB7" in py_cps
