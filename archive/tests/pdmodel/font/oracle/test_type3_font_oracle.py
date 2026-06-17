"""Live PDFBox differential parity for Type 3 fonts.

Wave 1419. Verifies that pypdfbox's :class:`PDType3Font` exposes the same
``/FontMatrix`` (6 floats), code -> glyph-name ``/Encoding`` map (0..255),
per-code advance widths (``get_width(code)``), ``/CharProcs`` glyph-name set,
and page text-extraction output as Apache PDFBox 3.0.7.

Type 3 fonts are bug-prone in a few classic spots:

* the ``/FontMatrix`` is a free-form 6-float transform (not the implicit
  1000-unit em of Type 1 / TrueType), so a wrong default or a wrong read of a
  custom matrix diverges immediately;
* ``getWidth(code)`` returns the *glyph-space* width straight from ``/Widths``
  (it is the renderer that later scales it through the FontMatrix), a frequent
  source of "off by a FontMatrix factor" bugs;
* the ``/Encoding`` is *always* a dictionary with a ``/Differences`` array (Type
  3 fonts have no built-in encoding), so the code -> name map must come purely
  from ``/Differences``.

No Type 3 fixture ships in the corpus (``grep -rl /Type3 tests/fixtures`` is
empty), so the test BUILDS a Type 3 font PDF with pypdfbox: three glyphs whose
shapes are hand-rolled ``/CharProcs`` content streams, a non-default custom
``/FontMatrix``, a ``/Differences`` encoding, an explicit ``/Widths`` array, and
a ``/ToUnicode`` CMap so text extraction is deterministic on both sides. The PDF
is saved once, then read back by BOTH libraries via the oracle harness.

The oracle output is produced by ``oracle/probes/Type3FontProbe.java``; the
Python side reconstructs the identical line format so any divergence shows up
as a single differing line.
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

# Custom (non-default) Type 3 font matrix: a 500-unit em (0.002 scale) with a
# tiny shear so a buggy "always [0.001,0,0,0.001,0,0]" default would diverge.
_FONT_MATRIX = [0.002, 0.0001, 0.0, 0.002, 0.0, 0.0]

# Three glyphs over codes 65 ('A'), 66 ('B'), 67 ('C'), mapped to letters via
# /Differences and /ToUnicode so text extraction yields "ABC".
_GLYPHS = [
    (65, "alpha", "A", 600.0),
    (66, "beta", "B", 700.0),
    (67, "gamma", "C", 550.0),
]
_FIRST_CHAR = 65
_LAST_CHAR = 67


def _char_proc_stream(width: float) -> COSStream:
    """A minimal but valid Type 3 glyph content stream.

    Starts with the ``d1`` operator (sets the glyph width + bbox, the spec form
    that lets the consumer ignore colour), then paints a filled box. The ``d1``
    width here is intentionally different from the ``/Widths`` entry so the test
    proves ``get_width(code)`` reads ``/Widths`` first (per §9.6.6), not the
    glyph-space width op.
    """
    body = (f"{width} 0 0 0 500 700 d1\n0 0 500 700 re f\n").encode("ascii")
    stream = COSStream()
    stream.set_data(body)
    return stream


def _build_type3_pdf(out_path: Path) -> None:
    """Write a one-page PDF whose only font is a Type 3 font with custom
    matrix, /Differences encoding, /Widths, /CharProcs, and /ToUnicode."""
    from pypdfbox.pdmodel.pd_page import PDPage
    from pypdfbox.pdmodel.pd_resources import PDResources

    # /CharProcs: glyph-name -> content stream.
    char_procs = COSDictionary()
    for _code, gname, _uni, w in _GLYPHS:
        char_procs.set_item(COSName.get_pdf_name(gname), _char_proc_stream(w))

    # /Encoding: dictionary with /Differences mapping codes -> glyph names.
    differences = COSArray()
    prev: int | None = None
    for code, gname, _uni, _w in _GLYPHS:
        if prev is None or code != prev + 1:
            differences.add(COSInteger.get(code))
        differences.add(COSName.get_pdf_name(gname))
        prev = code
    enc = COSDictionary()
    enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc.set_item(COSName.get_pdf_name("Differences"), differences)

    # /Widths array (glyph-space advance per code).
    widths = COSArray([COSFloat(w) for _c, _g, _u, w in _GLYPHS])

    # /FontMatrix.
    matrix = COSArray([COSFloat(v) for v in _FONT_MATRIX])

    # /FontBBox.
    bbox = COSArray([COSInteger.get(v) for v in (0, 0, 500, 700)])

    # /ToUnicode CMap so the text stripper yields deterministic Unicode.
    to_unicode = _build_to_unicode_cmap()

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type3"))
    font_dict.set_item(COSName.get_pdf_name("Name"), COSName.get_pdf_name("MyType3"))
    font_dict.set_item(COSName.get_pdf_name("FontMatrix"), matrix)
    font_dict.set_item(COSName.get_pdf_name("FontBBox"), bbox)
    font_dict.set_item(COSName.get_pdf_name("CharProcs"), char_procs)
    font_dict.set_item(COSName.get_pdf_name("Encoding"), enc)
    font_dict.set_int(COSName.FIRST_CHAR, _FIRST_CHAR)
    font_dict.set_int(COSName.LAST_CHAR, _LAST_CHAR)
    font_dict.set_item(COSName.get_pdf_name("Widths"), widths)
    font_dict.set_item(COSName.get_pdf_name("ToUnicode"), to_unicode)

    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        font = PDType3Font(font_dict)
        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), font)
        # Empty /Resources still wired so the font is reachable; the Type 3
        # font's own /Resources is unused by these glyph procs.
        font.set_resources(PDResources())
        page.set_resources(res)

        # Page content: show the three codes with our font so the text
        # stripper has something to extract.
        content = (
            b"BT\n/F1 12 Tf\n100 700 Td\n<414243> Tj\nET\n"
        )
        content_stream = COSStream()
        content_stream.set_data(content)
        page.set_contents(content_stream)

        doc.save(str(out_path))
    finally:
        doc.close()


def _build_to_unicode_cmap() -> COSStream:
    """Build a minimal /ToUnicode CMap mapping 0x41->A, 0x42->B, 0x43->C."""
    cmap = (
        "/CIDInit /ProcSet findresource begin\n"
        "12 dict begin\n"
        "begincmap\n"
        "/CMapName /Adobe-Identity-UCS def\n"
        "/CMapType 2 def\n"
        "1 begincodespacerange\n<00> <ff>\nendcodespacerange\n"
        "3 beginbfchar\n"
        "<41> <0041>\n"
        "<42> <0042>\n"
        "<43> <0043>\n"
        "endbfchar\n"
        "endcmap\n"
        "CMapName currentdict /CMap defineresource pop\n"
        "end\nend\n"
    ).encode("ascii")
    stream = COSStream()
    stream.set_data(cmap)
    return stream


# --- Python-side reconstruction of the probe output -------------------------


def _fmt(v: float) -> str:
    """Mirror the Java probe's ``String.format(Locale.US, "%.6f", v)``."""
    return f"{v:.6f}"


def _py_type3(pdf_path: Path) -> str:
    """Reconstruct Type3FontProbe output from pypdfbox, line-for-line."""
    from pypdfbox.text.pdf_text_stripper import PDFTextStripper

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
        text = PDFTextStripper().get_text(doc)
        lines.append("TEXT\t" + text.rstrip("\n"))
    finally:
        doc.close()
    return "\n".join(lines)


def _emit_font(
    lines: list[str], page_index: int, name: COSName, font: PDType3Font
) -> None:
    lines.append(f"FONT\t{page_index}\t{name.name}\t{font.get_name()}")

    matrix = font.get_font_matrix()
    lines.append("MATRIX\t" + "\t".join(_fmt(v) for v in matrix))

    enc = font.get_encoding_typed()
    for code in range(256):
        glyph = ".notdef" if enc is None else enc.get_name(code)
        if glyph is None:
            glyph = ".notdef"
        lines.append(f"ENC\t{code}\t{glyph}")

    first = font.get_first_char()
    last = font.get_last_char()
    if first >= 0:
        for code in range(first, last + 1):
            lines.append(f"WIDTH\t{code}\t{_fmt(font.get_width(code))}")

    char_procs = font.get_char_procs()
    if char_procs is not None:
        names = sorted(key.name for key in char_procs.key_set())
        for n in names:
            lines.append(f"PROC\t{n}")

    bbox = font.get_font_bbox()
    if bbox is None:
        lines.append("BBOX\tNONE")
    else:
        lines.append(
            "BBOX\t"
            + _fmt(bbox.get_lower_left_x()) + "\t"
            + _fmt(bbox.get_lower_left_y()) + "\t"
            + _fmt(bbox.get_upper_right_x()) + "\t"
            + _fmt(bbox.get_upper_right_y())
        )

    if first >= 0:
        for code in range(first, last + 1):
            tx, ty = font.get_displacement(code)
            lines.append(f"DISP\t{code}\t{_fmt(tx)}\t{_fmt(ty)}")


def _normalize_text_block(text: str) -> str:
    """Strip trailing whitespace so the two libraries' page-text block line
    layout (form feeds / trailing newlines) does not over-fit the diff."""
    return text.rstrip()


def _assert_parity(pdf_path: Path) -> None:
    java = run_probe_text("Type3FontProbe", str(pdf_path))
    py = _py_type3(pdf_path)
    jl = _normalize_text_block(java).splitlines()
    pl = _normalize_text_block(py).splitlines()
    assert len(jl) == len(pl), (
        f"line-count mismatch: java={len(jl)} py={len(pl)}\n"
        f"  java tail: {jl[-4:]}\n  py tail: {pl[-4:]}"
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(jl, pl, strict=True))
        if j != p
    ]
    assert not diffs, "Type 3 font parity broken:\n" + "\n".join(diffs[:40])


@requires_oracle
def test_built_type3_font_matches_pdfbox(tmp_path: Path) -> None:
    """A built Type 3 font PDF (custom /FontMatrix, /Differences encoding,
    explicit /Widths, hand-rolled /CharProcs, /ToUnicode) must resolve its
    font matrix, encoding map, per-code widths, char-proc names, and page text
    identically to Apache PDFBox 3.0.7."""
    pdf_path = tmp_path / "type3.pdf"
    _build_type3_pdf(pdf_path)
    _assert_parity(pdf_path)


@requires_oracle
def test_type3_displacement_with_translating_matrix(tmp_path: Path) -> None:
    """Probe ``get_displacement(code)`` against PDFBox under a font matrix
    with non-zero translation (e/f entries).

    Upstream's ``getDisplacement`` is ``FontMatrix.transform(Vector(width, 0))``
    where PDFBox's ``Matrix.transform(Vector)`` *does* fold translation into
    the transformed vector — i.e. the result is ``(a*width + e, b*width + f)``,
    not the geometrically-pure ``(a*width, b*width)``. This test pins the
    parity by setting ``e = 0.5`` / ``f = 0.25`` so a port that drops the
    translation diverges by a constant ``(0.5, 0.25)`` per glyph.
    """
    from pypdfbox.pdmodel.pd_page import PDPage
    from pypdfbox.pdmodel.pd_resources import PDResources

    pdf_path = tmp_path / "type3_translating.pdf"

    char_procs = COSDictionary()
    for _code, gname, _uni, w in _GLYPHS:
        char_procs.set_item(COSName.get_pdf_name(gname), _char_proc_stream(w))

    differences = COSArray()
    prev: int | None = None
    for code, gname, _uni, _w in _GLYPHS:
        if prev is None or code != prev + 1:
            differences.add(COSInteger.get(code))
        differences.add(COSName.get_pdf_name(gname))
        prev = code
    enc = COSDictionary()
    enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc.set_item(COSName.get_pdf_name("Differences"), differences)

    widths = COSArray([COSFloat(w) for _c, _g, _u, w in _GLYPHS])
    # Translating matrix: a=0.002, d=0.002, e=0.5, f=0.25.
    matrix = COSArray([
        COSFloat(0.002), COSFloat(0.0),
        COSFloat(0.0), COSFloat(0.002),
        COSFloat(0.5), COSFloat(0.25),
    ])
    bbox = COSArray([COSInteger.get(v) for v in (0, 0, 500, 700)])

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type3"))
    font_dict.set_item(COSName.get_pdf_name("Name"), COSName.get_pdf_name("T3Trans"))
    font_dict.set_item(COSName.get_pdf_name("FontMatrix"), matrix)
    font_dict.set_item(COSName.get_pdf_name("FontBBox"), bbox)
    font_dict.set_item(COSName.get_pdf_name("CharProcs"), char_procs)
    font_dict.set_item(COSName.get_pdf_name("Encoding"), enc)
    font_dict.set_int(COSName.FIRST_CHAR, _FIRST_CHAR)
    font_dict.set_int(COSName.LAST_CHAR, _LAST_CHAR)
    font_dict.set_item(COSName.get_pdf_name("Widths"), widths)

    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        font = PDType3Font(font_dict)
        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), font)
        font.set_resources(PDResources())
        page.set_resources(res)
        doc.save(str(pdf_path))
    finally:
        doc.close()

    java_lines = run_probe_text("Type3FontProbe", str(pdf_path)).splitlines()
    java_disp = [line for line in java_lines if line.startswith("DISP\t")]

    doc = PDDocument.load(pdf_path)
    try:
        font = None
        for page in doc.get_pages():
            res = page.get_resources()
            for name in res.get_font_names():
                f = res.get_font(name)
                if isinstance(f, PDType3Font):
                    font = f
                    break
        assert font is not None
        py_disp = []
        for code in range(font.get_first_char(), font.get_last_char() + 1):
            tx, ty = font.get_displacement(code)
            py_disp.append(f"DISP\t{code}\t{_fmt(tx)}\t{_fmt(ty)}")
    finally:
        doc.close()

    assert py_disp == java_disp, (
        "Type 3 displacement diverges under a translating font matrix:\n"
        f"  java: {java_disp}\n  py:   {py_disp}"
    )


@requires_oracle
def test_type3_matrix_and_widths_in_isolation(tmp_path: Path) -> None:
    """Targeted re-check of the two classic Type 3 divergence points — the
    custom /FontMatrix and the glyph-space /Widths — so a regression there is
    attributable without scanning the full 256-code encoding diff."""
    pdf_path = tmp_path / "type3.pdf"
    _build_type3_pdf(pdf_path)

    java_lines = run_probe_text("Type3FontProbe", str(pdf_path)).splitlines()
    java_matrix = next(line for line in java_lines if line.startswith("MATRIX\t"))
    java_widths = [line for line in java_lines if line.startswith("WIDTH\t")]

    doc = PDDocument.load(pdf_path)
    try:
        font = None
        for page in doc.get_pages():
            res = page.get_resources()
            for name in res.get_font_names():
                f = res.get_font(name)
                if isinstance(f, PDType3Font):
                    font = f
                    break
        assert font is not None
        py_matrix = "MATRIX\t" + "\t".join(_fmt(v) for v in font.get_font_matrix())
        py_widths = [
            f"WIDTH\t{c}\t{_fmt(font.get_width(c))}"
            for c in range(font.get_first_char(), font.get_last_char() + 1)
        ]
    finally:
        doc.close()

    assert py_matrix == java_matrix
    assert py_widths == java_widths
