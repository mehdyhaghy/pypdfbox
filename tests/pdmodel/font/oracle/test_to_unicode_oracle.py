"""Live PDFBox differential parity for the embedded /ToUnicode CMap path.

A font's ``/ToUnicode`` stream (PDF 32000-1 §9.10.3) is the authoritative
code -> Unicode source used by every text extractor. This module hand-authors
a Type0 / Identity-H font whose ``/ToUnicode`` CMap exercises every shape the
parser must handle, then compares ``font.to_unicode(code)`` against Apache
PDFBox's ``font.toUnicode(code)`` for each interesting code, plus the
:class:`PDFTextStripper` output for the shown string:

* a ``bfchar`` block (single code -> single char): ``<0003> <0041>`` -> ``A``;
* a contiguous ``bfrange`` (start-dst increments): ``<0010> <0012> <0061>``
  -> ``a b c``;
* an array-form ``bfrange`` (explicit dst per code):
  ``<0020> <0022> [<0078> <0079> <007A>]`` -> ``x y z``;
* a multi-char (ligature) destination: ``<0030> <0030> <00660069>`` -> ``fi``
  (one code maps to a two-char string);
* a non-BMP destination via a UTF-16 surrogate pair: ``<0040> <D83DDE00>``
  -> ``U+1F600`` (a single code point once decoded).

The multi-char and surrogate cases are the high-value ones: a parser that
truncates the ligature destination, or mishandles the surrogate pair, diverges
from Java here and nowhere else.

The oracle output is produced by ``oracle/probes/ToUnicodeCMapProbe.java``:
``UNI <code> -> U+XXXX[ U+YYYY...]`` per code (``(none)`` when unmapped), then a
``===TEXT===`` block with the stripper output. Hand-written (not ported from
upstream JUnit). Decorated ``@requires_oracle`` so it skips cleanly without the
jar / JDK.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

# A ToUnicode CMap (CMapType 2) over a 2-byte Identity-H codespace covering
# all five mapping shapes the parser must handle.
_CMAP_TEXT = (
    "/CIDInit /ProcSet findresource begin\n"
    "12 dict begin\n"
    "begincmap\n"
    "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
    "/CMapName /Adobe-Identity-UCS def\n"
    "/CMapType 2 def\n"
    "1 begincodespacerange\n"
    "<0000> <FFFF>\n"
    "endcodespacerange\n"
    # bfchar block — single code -> single char.
    "2 beginbfchar\n"
    "<0003> <0041>\n"  # -> A
    "<0004> <0042>\n"  # -> B
    "endbfchar\n"
    # bfrange — contiguous start-dst (0x10->a, 0x11->b, 0x12->c) plus a
    # single-code range whose destination is a two-char ligature.
    "2 beginbfrange\n"
    "<0010> <0012> <0061>\n"  # contiguous -> a b c
    "<0030> <0030> <00660069>\n"  # one code -> "fi" (multi-char dst)
    "endbfrange\n"
    # bfrange — array of explicit destinations (0x20->x, 0x21->y, 0x22->z).
    "1 beginbfrange\n"
    "<0020> <0022> [<0078> <0079> <007A>]\n"
    "endbfrange\n"
    # bfchar — non-BMP destination expressed as a UTF-16 surrogate pair.
    "1 beginbfchar\n"
    "<0040> <D83DDE00>\n"  # -> U+1F600 GRINNING FACE
    "endbfchar\n"
    "endcmap\n"
    "CMapName currentdict /CMap defineresource pop\n"
    "end\n"
    "end\n"
)

# Interesting codes to probe (decimal), in ascending order.
_CODES = [0x0003, 0x0004, 0x0010, 0x0011, 0x0012, 0x0020, 0x0021, 0x0022, 0x0030, 0x0040]

# Codes shown in the content stream (2-byte big-endian each), spelling the
# string A B a x fi 😀.
_SHOWN_CODES = [0x0003, 0x0004, 0x0010, 0x0020, 0x0030, 0x0040]


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _build_font_dict() -> COSDictionary:
    """A Type0 / Identity-H font with a CIDFontType2 descendant and the
    five-shape ``/ToUnicode`` CMap above. Identity-H keeps codes == CIDs so
    the ToUnicode CMap is the sole driver of ``to_unicode``."""
    desc = COSDictionary()
    desc.set_name(_name("Type"), "Font")
    desc.set_name(COSName.SUBTYPE, "CIDFontType2")  # type: ignore[attr-defined]
    desc.set_name(_name("BaseFont"), "ABCDEF+TestFont")
    cid_si = COSDictionary()
    cid_si.set_string(_name("Registry"), "Adobe")
    cid_si.set_string(_name("Ordering"), "Identity")
    cid_si.set_int(_name("Supplement"), 0)
    desc.set_item(_name("CIDSystemInfo"), cid_si)
    desc.set_int(_name("DW"), 1000)

    to_unicode = COSStream()
    with to_unicode.create_output_stream() as out:
        out.write(_CMAP_TEXT.encode("ascii"))

    font = COSDictionary()
    font.set_name(_name("Type"), "Font")
    font.set_name(COSName.SUBTYPE, "Type0")  # type: ignore[attr-defined]
    font.set_name(_name("BaseFont"), "ABCDEF+TestFont")
    font.set_name(_name("Encoding"), "Identity-H")
    arr = COSArray()
    arr.add(desc)
    font.set_item(_name("DescendantFonts"), arr)
    font.set_item(_name("ToUnicode"), to_unicode)
    return font


def _build_pdf(path: Path) -> None:
    """Author a one-page PDF showing the interesting codes with the Type0
    font, and save it to ``path``."""
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 200, 200))
        doc.add_page(page)
        res = page.get_resources()
        res.put(_name("Font"), _name("F1"), _build_font_dict())
        page.set_resources(res)
        shown = b"".join(
            bytes([(c >> 8) & 0xFF, c & 0xFF]) for c in _SHOWN_CODES
        )
        content = b"BT /F1 12 Tf 10 100 Td <" + shown.hex().encode("ascii") + b"> Tj ET"
        cs = COSStream()
        with cs.create_output_stream() as out:
            out.write(content)
        page.set_contents(cs)
        doc.save(str(path))
    finally:
        doc.close()


def _fmt_unicode(s: str) -> str:
    """Render ``s`` as the probe does — space-separated ``U+XXXX`` per code
    point (Python iterates code points natively, collapsing surrogate pairs)."""
    return " ".join(f"U+{ord(ch):04X}" for ch in s)


def _py_lines(pdf_path: Path) -> tuple[list[str], str]:
    """Reproduce the probe's ``UNI`` lines and the extracted text from
    pypdfbox, closing the document in a ``finally``."""
    doc = PDDocument.load(str(pdf_path))
    try:
        page = doc.get_pages()[0]
        res = page.get_resources()
        font_name = next(iter(res.get_font_names()))
        font = res.get_font(font_name)
        lines: list[str] = []
        for code in _CODES:
            uni = font.to_unicode(code)
            if not uni:
                lines.append(f"UNI {code} -> (none)")
            else:
                lines.append(f"UNI {code} -> {_fmt_unicode(uni)}")
        text = PDFTextStripper().get_text(doc)
        return lines, text
    finally:
        doc.close()


@requires_oracle
def test_to_unicode_cmap_matches_pdfbox(tmp_path: Path) -> None:
    """pypdfbox's ``to_unicode(code)`` must equal Java's ``toUnicode(code)``
    for every shape of ``/ToUnicode`` entry, and the extracted text must
    match byte-for-byte.

    The per-code lines lock in bfchar, contiguous bfrange, array-form
    bfrange, the multi-char ligature destination, and the non-BMP surrogate
    destination. A truncated ligature or a mishandled surrogate shows up as a
    single differing ``UNI`` line.
    """
    pdf_path = tmp_path / "tounicode.pdf"
    _build_pdf(pdf_path)

    java_out = run_probe_text(
        "ToUnicodeCMapProbe", str(pdf_path), *(str(c) for c in _CODES)
    )
    java_lines = java_out.split("===TEXT===\n", 1)
    java_uni = [ln for ln in java_lines[0].splitlines() if ln.startswith("UNI ")]
    java_text = java_lines[1] if len(java_lines) > 1 else ""

    py_uni, py_text = _py_lines(pdf_path)

    assert py_uni == java_uni, (
        "code->unicode parity broken:\n"
        f"  JAVA: {java_uni}\n"
        f"  PY:   {py_uni}"
    )
    assert py_text == java_text, (
        "extracted text diverged:\n"
        f"  JAVA: {java_text!r}\n"
        f"  PY:   {py_text!r}"
    )


@requires_oracle
def test_to_unicode_ligature_and_non_bmp(tmp_path: Path) -> None:
    """Spotlight the two high-value cases against Java explicitly.

    The ligature code (0x0030) must yield the two-char string ``fi`` and the
    surrogate-pair code (0x0040) must yield the single non-BMP code point
    U+1F600 — both exactly as Apache PDFBox reports them.
    """
    pdf_path = tmp_path / "tounicode2.pdf"
    _build_pdf(pdf_path)

    java_out = run_probe_text("ToUnicodeCMapProbe", str(pdf_path), "48", "64")
    java_uni = [
        ln for ln in java_out.splitlines() if ln.startswith("UNI ")
    ]

    py_uni, _ = _py_lines(pdf_path)
    py_lig = next(ln for ln in py_uni if ln.startswith("UNI 48 "))
    py_emoji = next(ln for ln in py_uni if ln.startswith("UNI 64 "))

    # pypdfbox-internal expectations, then parity against Java.
    assert py_lig == "UNI 48 -> U+0066 U+0069"
    assert py_emoji == "UNI 64 -> U+1F600"
    assert java_uni == [py_lig, py_emoji]
