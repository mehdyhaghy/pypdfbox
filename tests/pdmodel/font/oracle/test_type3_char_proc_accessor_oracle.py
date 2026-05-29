"""Live PDFBox differential parity for PDType3Font structural accessors.

Wave 1467. The existing ``test_type3_font_oracle`` already pins
``getFontMatrix`` / the ``getEncoding`` code->name map / ``getWidth`` /
``getCharProcs`` key set / ``getFontBBox`` / ``getDisplacement``. This module
covers the remaining structural-accessor surface of :class:`PDType3Font`:

* ``get_char_proc(int code)`` — the per-code resolution that walks
  ``/Encoding /Differences`` to a glyph name and then to the ``/CharProcs``
  stream. The classic divergences here are (a) returning a glyph for a code
  that maps to ``.notdef`` or is unlisted in ``/Differences`` (must be
  ``None``), and (b) reading the wrong stream. We pin the resolved proc's
  ``d0/d1`` advance (``get_width()``), its ``d1`` glyph bbox
  (``get_glyph_bbox()``), and its decoded content-stream byte length so a
  mis-resolution shows up immediately.
* ``get_resources()`` — the shared ``/Resources`` dictionary every char proc
  inherits, plus ``PDType3CharProc.get_resources()`` falling back to the
  font's ``/Resources`` in the well-formed case.

The fixture is built with pypdfbox (no Type 3 PDF ships in the corpus): three
glyphs over codes 65/66/67 via ``/Differences``, an explicit ``/Widths`` array
whose entries deliberately differ from each glyph's ``d1`` advance (so the
char-proc ``get_width()`` is proven to read the stream, not ``/Widths``), and a
shared font ``/Resources`` carrying a sub-font so ``getFontNames()`` is
non-empty. The probe emits ``null`` for any in-window code that resolves to no
glyph, so a port that wrongly synthesised a glyph for an unmapped code would
diverge.

The oracle output comes from ``oracle/probes/Type3CharProcAccessorProbe.java``;
the Python side reconstructs the identical line format so any divergence shows
up as a single differing line.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

# Glyph d1 advances differ from the /Widths entries below so a char-proc
# get_width() that wrongly read /Widths would diverge.
_GLYPHS = [
    (65, "alpha", 600.0),   # d1 wx = 600
    (66, "beta", 700.0),    # d1 wx = 700
    (67, "gamma", 550.0),   # d1 wx = 550
]
# /Widths intentionally different from the d1 advances above.
_WIDTHS = [610.0, 720.0, 530.0]
_FIRST_CHAR = 65
_LAST_CHAR = 67


def _char_proc_stream(width: float) -> COSStream:
    """A minimal valid Type 3 glyph content stream led by ``d1`` (sets the
    glyph advance + bbox) then a filled box. The d1 advance is ``width``."""
    body = (f"{width} 0 0 0 500 700 d1\n0 0 500 700 re f\n").encode("ascii")
    stream = COSStream()
    stream.set_data(body)
    return stream


def _build_type3_pdf(out_path: Path) -> None:
    """Write a one-page PDF whose only font is a Type 3 font with a shared
    /Resources, /Differences encoding, /Widths, and hand-rolled /CharProcs."""
    from pypdfbox.pdmodel.pd_page import PDPage
    from pypdfbox.pdmodel.pd_resources import PDResources

    char_procs = COSDictionary()
    for _code, gname, w in _GLYPHS:
        char_procs.set_item(COSName.get_pdf_name(gname), _char_proc_stream(w))

    differences = COSArray()
    prev: int | None = None
    for code, gname, _w in _GLYPHS:
        if prev is None or code != prev + 1:
            differences.add(COSInteger.get(code))
        differences.add(COSName.get_pdf_name(gname))
        prev = code
    enc = COSDictionary()
    enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc.set_item(COSName.get_pdf_name("Differences"), differences)

    widths = COSArray([COSFloat(w) for w in _WIDTHS])
    matrix = COSArray([COSFloat(v) for v in (0.001, 0.0, 0.0, 0.001, 0.0, 0.0)])
    bbox = COSArray([COSInteger.get(v) for v in (0, 0, 500, 700)])

    # Shared font /Resources: carry a sub-font so getFontNames() is non-empty,
    # proving every char proc inherits it via getResources().
    shared_res = _shared_resources_dict()

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type3")
    )
    font_dict.set_item(COSName.get_pdf_name("Name"), COSName.get_pdf_name("T3Acc"))
    font_dict.set_item(COSName.get_pdf_name("FontMatrix"), matrix)
    font_dict.set_item(COSName.get_pdf_name("FontBBox"), bbox)
    font_dict.set_item(COSName.get_pdf_name("CharProcs"), char_procs)
    font_dict.set_item(COSName.get_pdf_name("Encoding"), enc)
    font_dict.set_int(COSName.FIRST_CHAR, _FIRST_CHAR)
    font_dict.set_int(COSName.LAST_CHAR, _LAST_CHAR)
    font_dict.set_item(COSName.get_pdf_name("Widths"), widths)
    font_dict.set_item(COSName.get_pdf_name("Resources"), shared_res)

    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        font = PDType3Font(font_dict)
        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), font)
        page.set_resources(res)

        content = b"BT\n/F1 12 Tf\n100 700 Td\n<414243> Tj\nET\n"
        content_stream = COSStream()
        content_stream.set_data(content)
        page.set_contents(content_stream)

        doc.save(str(out_path))
    finally:
        doc.close()


def _shared_resources_dict() -> COSDictionary:
    """A /Resources dictionary with one /Font entry (a Type1 Helvetica) so
    ``getFontNames()`` returns a deterministic non-empty set on both sides."""
    helv = COSDictionary()
    helv.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    helv.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type1"))
    helv.set_item(
        COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("Helvetica")
    )
    fonts = COSDictionary()
    fonts.set_item(COSName.get_pdf_name("HelvSub"), helv)
    res = COSDictionary()
    res.set_item(COSName.get_pdf_name("Font"), fonts)
    return res


# --- Python-side reconstruction of the probe output -------------------------


def _fmt(v: float) -> str:
    return f"{v:.6f}"


def _font_names(res: object) -> str:
    if res is None:
        return "null"
    names = sorted(n.name for n in res.get_font_names())  # type: ignore[attr-defined]
    return "\t".join([str(len(names)), *names])


def _py_output(pdf_path: Path) -> str:
    lines: list[str] = []
    doc = PDDocument.load(pdf_path)
    try:
        for page_index, page in enumerate(doc.get_pages()):
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                font = res.get_font(name)
                if isinstance(font, PDType3Font):
                    _emit_font(lines, page_index, name, font)
    finally:
        doc.close()
    return "\n".join(lines)


def _emit_font(
    lines: list[str], page_index: int, name: COSName, font: PDType3Font
) -> None:
    lines.append(f"FONT\t{page_index}\t{name.name}\t{font.get_name()}")

    first = font.get_first_char()
    last = font.get_last_char()
    for code in range(256):
        proc = font.get_char_proc(code)
        if proc is None:
            if first >= 0 and first <= code <= last:
                lines.append(f"CHARPROC\t{code}\tnull")
            continue
        wx = proc.get_width()
        gb = proc.get_glyph_bbox()
        if gb is None:
            bbox = "NONE"
        else:
            bbox = (
                f"{_fmt(gb.get_lower_left_x())} {_fmt(gb.get_lower_left_y())} "
                f"{_fmt(gb.get_upper_right_x())} {_fmt(gb.get_upper_right_y())}"
            )
        length = len(proc.to_byte_array())
        lines.append(
            f"CHARPROC\t{code}\tpresent\t{_fmt(wx)}\t{bbox}\t{length}"
        )
        lines.append(f"PROCRES\t{code}\t{_font_names(proc.get_resources())}")

    lines.append(f"FONTRES\t{_font_names(font.get_resources())}")


def _assert_parity(pdf_path: Path) -> None:
    java = run_probe_text("Type3CharProcAccessorProbe", str(pdf_path))
    py = _py_output(pdf_path)
    jl = java.rstrip().splitlines()
    pl = py.rstrip().splitlines()
    assert len(jl) == len(pl), (
        f"line-count mismatch: java={len(jl)} py={len(pl)}\n"
        f"  java tail: {jl[-6:]}\n  py tail: {pl[-6:]}"
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(jl, pl, strict=True))
        if j != p
    ]
    assert not diffs, (
        "Type 3 char-proc accessor parity broken:\n" + "\n".join(diffs[:40])
    )


@requires_oracle
def test_type3_char_proc_accessors_match_pdfbox(tmp_path: Path) -> None:
    """``get_char_proc(code)`` per-code resolution (advance, glyph bbox,
    decoded length), plus shared ``get_resources()`` font names, must match
    Apache PDFBox 3.0.7 line-for-line."""
    pdf_path = tmp_path / "type3_accessors.pdf"
    _build_type3_pdf(pdf_path)
    _assert_parity(pdf_path)
