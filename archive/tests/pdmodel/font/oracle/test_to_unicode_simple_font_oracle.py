"""Live PDFBox differential parity for the simple-font /ToUnicode fallback chain.

The existing ``test_to_unicode_oracle`` module pins the Type0 / Identity-H path,
where codes equal CIDs and the ``/ToUnicode`` CMap is the *only* driver of
``to_unicode``. This module covers the complementary, equally load-bearing
surface: a **simple** font (Type1 / Helvetica with ``/WinAnsiEncoding``) whose
``/ToUnicode`` CMap maps some codes to Unicode that *differs* from what the
encoding's glyph name would yield, and *omits* other codes so they fall through
the rest of the chain.

Upstream ``PDSimpleFont.toUnicode(int)`` resolves a code in this order:

1. the ``/ToUnicode`` CMap (an explicit mapping always wins);
2. the font ``/Encoding`` → glyph name → Adobe Glyph List → Unicode.

The cases probed:

* ``0x41`` ('A'): WinAnsi encoding names it ``A`` (→ "A"), but the ``/ToUnicode``
  CMap remaps it to ``Z`` — ToUnicode must win, proving the CMap overrides the
  encoding even when the glyph name is a perfectly good Latin letter.
* ``0x66`` ('f'): the CMap maps it to the multi-char ligature ``ffi`` — a
  one-code → three-char destination on a *simple* font (the existing Type0 test
  only exercised the two-char ``fi`` ligature on Identity-H).
* ``0x42`` ('B') and ``0x43`` ('C'): absent from the CMap, so they fall back to
  the encoding + glyph list and resolve to "B" / "C". A parser that stops at the
  CMap miss (returning ``None`` instead of falling through) diverges here.
* ``0x20`` (space): also absent from the CMap; encoding names it ``space`` →
  "SP" code point U+0020.

Output comes from the generic ``oracle/probes/ToUnicodeCMapProbe.java``:
``UNI <code> -> U+XXXX[ U+YYYY...]`` per code (``(none)`` when unmapped), then a
``===TEXT===`` block with the ``PDFTextStripper`` output. Hand-written (not
ported from upstream JUnit). Decorated ``@requires_oracle`` so it skips cleanly
without the jar / JDK.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

# A ToUnicode CMap (CMapType 2) over a 1-byte simple-font code space. It
# deliberately:
#   * remaps 0x41 ('A') to U+005A ('Z') — overrides the WinAnsi glyph name;
#   * maps 0x66 ('f') to the three-char ligature "ffi" (U+0066 U+0066 U+0069);
#   * leaves 0x42, 0x43, 0x20 unmapped so they fall back to encoding+glyphlist.
_CMAP_TEXT = (
    "/CIDInit /ProcSet findresource begin\n"
    "12 dict begin\n"
    "begincmap\n"
    "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
    "/CMapName /Adobe-Identity-UCS def\n"
    "/CMapType 2 def\n"
    "1 begincodespacerange\n"
    "<00> <FF>\n"
    "endcodespacerange\n"
    "2 beginbfchar\n"
    "<41> <005A>\n"  # 'A' code -> "Z" (overrides encoding glyph name "A")
    "<66> <006600660069>\n"  # 'f' code -> "ffi" (three-char ligature)
    "endbfchar\n"
    "endcmap\n"
    "CMapName currentdict /CMap defineresource pop\n"
    "end\n"
    "end\n"
)

# Codes to probe (decimal). 0x41 'A', 0x42 'B', 0x43 'C', 0x66 'f', 0x20 space.
_CODES = [0x41, 0x42, 0x43, 0x66, 0x20]

# Codes shown in the content stream, spelling (post-ToUnicode) "Z B C ffi  ".
_SHOWN_CODES = [0x41, 0x42, 0x43, 0x66, 0x20]


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _build_font_dict() -> COSDictionary:
    """A non-embedded Type1 Helvetica with ``/WinAnsiEncoding`` and the
    override/fallback ``/ToUnicode`` CMap above. Helvetica is a Standard 14
    font, so no font program is required and the encoding fallback resolves
    through the built-in Adobe Glyph List on both sides."""
    to_unicode = COSStream()
    with to_unicode.create_output_stream() as out:
        out.write(_CMAP_TEXT.encode("ascii"))

    font = COSDictionary()
    font.set_name(_name("Type"), "Font")
    font.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    font.set_name(_name("BaseFont"), "Helvetica")
    font.set_name(_name("Encoding"), "WinAnsiEncoding")
    font.set_item(_name("ToUnicode"), to_unicode)
    return font


def _build_pdf(path: Path) -> None:
    """Author a one-page PDF showing the probed codes with the simple font."""
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 200, 200))
        doc.add_page(page)
        res = page.get_or_create_resources()
        res.put(_name("Font"), _name("F1"), _build_font_dict())
        page.set_resources(res)
        shown = bytes(_SHOWN_CODES)
        content = (
            b"BT /F1 12 Tf 10 100 Td <" + shown.hex().encode("ascii") + b"> Tj ET"
        )
        cs = COSStream()
        with cs.create_output_stream() as out:
            out.write(content)
        page.set_contents(cs)
        doc.save(str(path))
    finally:
        doc.close()


def _fmt_unicode(s: str) -> str:
    """Render ``s`` as the probe does — space-separated ``U+XXXX`` per code
    point (Python iterates code points natively)."""
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
def test_simple_font_to_unicode_matches_pdfbox(tmp_path: Path) -> None:
    """pypdfbox's ``to_unicode(code)`` on a simple Type1 font must equal Java's
    ``toUnicode(code)`` for every case of the fallback chain, and the extracted
    text must match byte-for-byte.

    Locks in: ToUnicode-overrides-encoding (0x41 -> Z), the multi-char ligature
    destination on a simple font (0x66 -> ffi), and the encoding+glyph-list
    fallback for codes absent from the CMap (0x42/0x43/0x20).
    """
    pdf_path = tmp_path / "tounicode_simple.pdf"
    _build_pdf(pdf_path)

    java_out = run_probe_text(
        "ToUnicodeCMapProbe", str(pdf_path), *(str(c) for c in _CODES)
    )
    java_parts = java_out.split("===TEXT===\n", 1)
    java_uni = [ln for ln in java_parts[0].splitlines() if ln.startswith("UNI ")]
    java_text = java_parts[1] if len(java_parts) > 1 else ""

    py_uni, py_text = _py_lines(pdf_path)

    assert py_uni == java_uni, (
        "simple-font code->unicode parity broken:\n"
        f"  JAVA: {java_uni}\n"
        f"  PY:   {py_uni}"
    )
    assert py_text == java_text, (
        "extracted text diverged:\n"
        f"  JAVA: {java_text!r}\n"
        f"  PY:   {py_text!r}"
    )


@requires_oracle
def test_simple_font_to_unicode_override_and_fallback(tmp_path: Path) -> None:
    """Spotlight the two precedence rules against Java explicitly.

    The override code (0x41) must yield "Z" (not the encoding's "A"), the
    ligature code (0x66) the three-char "ffi", and a CMap-absent code (0x42)
    must fall back to the encoding glyph "B" — never ``(none)``.
    """
    pdf_path = tmp_path / "tounicode_simple2.pdf"
    _build_pdf(pdf_path)

    java_out = run_probe_text("ToUnicodeCMapProbe", str(pdf_path), "65", "102", "66")
    java_uni = [ln for ln in java_out.splitlines() if ln.startswith("UNI ")]

    py_uni, _ = _py_lines(pdf_path)
    py_override = next(ln for ln in py_uni if ln.startswith("UNI 65 "))
    py_ligature = next(ln for ln in py_uni if ln.startswith("UNI 102 "))
    py_fallback = next(ln for ln in py_uni if ln.startswith("UNI 66 "))

    # pypdfbox-internal expectations, then parity against Java.
    assert py_override == "UNI 65 -> U+005A"
    assert py_ligature == "UNI 102 -> U+0066 U+0066 U+0069"
    assert py_fallback == "UNI 66 -> U+0042"
    assert java_uni == [py_override, py_ligature, py_fallback]
