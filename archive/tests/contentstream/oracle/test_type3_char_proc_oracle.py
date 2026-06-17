"""Live PDFBox differential parity for the Type 3 glyph char-proc metric
operators ``d0`` / ``d1``.

Wave 1459. Distinct from ``tests/pdmodel/font/oracle/test_type3_font_oracle.py``
(which pins ``/FontMatrix``, the ``/Widths``-array ``get_width(code)`` path, the
``/Encoding`` map, char-proc names, ``/FontBBox`` and displacement): this file
pins the *content-stream-operator* surface that begins every Type 3 glyph
procedure —

  wx wy                       d0    (set glyph width, no bounding box)
  wx wy  llx lly urx ury      d1    (set glyph width AND bounding box)

i.e. :meth:`PDType3CharProc.get_width` (the ``wx`` advance lifted straight from
the d0/d1 op, the ``get_width_from_font`` path — *not* the ``/Widths`` array),
:meth:`PDType3CharProc.get_glyph_b_box` (the ``d1`` bbox; ``None`` for a leading
``d0``), and :meth:`PDType3CharProc.get_matrix` (the parent font's
``/FontMatrix`` applied to the char-proc — char procs carry no matrix of their
own).

The fixture deliberately mixes the two operator forms across glyphs so a port
that confuses d0/d1 bbox semantics, or that reads the ``/Widths`` array instead
of the in-stream ``wx``, diverges immediately:

* ``alpha`` — ``d1`` with a non-axis-aligned bbox (negative ``lly``) and a
  ``wx`` that differs from the ``/Widths`` entry;
* ``beta``  — ``d0`` (width only) → ``get_glyph_b_box()`` must be ``None``;
* ``gamma`` — ``d1`` with whitespace / a leading comment before the operator so
  the tokeniser's whitespace + comment skipping is exercised.

The oracle output is produced by ``oracle/probes/Type3CharProcProbe.java``; the
Python side reconstructs the identical tab-separated line format so any
divergence shows up as a single differing line.
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
from pypdfbox.pdmodel.font.pd_type3_char_proc import PDType3CharProc
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

# Custom (non-default) Type 3 font matrix with a shear so a buggy
# "always [0.001,0,0,0.001,0,0]" default diverges on PROCMATRIX.
_FONT_MATRIX = [0.002, 0.0001, 0.0, 0.0018, 0.0, 0.0]

_FIRST_CHAR = 65
_LAST_CHAR = 67

# (code, glyph-name, /Widths entry, char-proc body). The char-proc body's
# leading d0/d1 ``wx`` is intentionally different from the /Widths entry so the
# two get_width paths are distinguishable.
_GLYPHS: list[tuple[int, str, float, bytes]] = [
    # d1: width 640, bbox (10, -20, 480, 700) — negative lly, wx != Widths(600).
    (65, "alpha", 600.0, b"640 0 10 -20 480 700 d1\n0 0 480 700 re f\n"),
    # d0: width 720, no bbox.
    (66, "beta", 700.0, b"720 0 d0\n0 0 460 680 re f\n"),
    # d1 with a leading comment + extra whitespace before the operator.
    (
        67,
        "gamma",
        550.0,
        b"% glyph gamma\n  555  0   5 5 470 690   d1\n0 0 470 690 re f\n",
    ),
]


def _char_proc_stream(body: bytes) -> COSStream:
    stream = COSStream()
    stream.set_data(body)
    return stream


def _build_type3_pdf(out_path: Path) -> None:
    """Write a one-page PDF whose only font is a Type 3 font whose glyphs use a
    mix of ``d0`` and ``d1`` leading metric operators."""
    from pypdfbox.pdmodel.pd_page import PDPage
    from pypdfbox.pdmodel.pd_resources import PDResources

    char_procs = COSDictionary()
    for _code, gname, _w, body in _GLYPHS:
        char_procs.set_item(COSName.get_pdf_name(gname), _char_proc_stream(body))

    differences = COSArray()
    prev: int | None = None
    for code, gname, _w, _b in _GLYPHS:
        if prev is None or code != prev + 1:
            differences.add(COSInteger.get(code))
        differences.add(COSName.get_pdf_name(gname))
        prev = code
    enc = COSDictionary()
    enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc.set_item(COSName.get_pdf_name("Differences"), differences)

    widths = COSArray([COSFloat(w) for _c, _g, w, _b in _GLYPHS])
    matrix = COSArray([COSFloat(v) for v in _FONT_MATRIX])
    bbox = COSArray([COSInteger.get(v) for v in (0, -20, 480, 700)])

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type3")
    )
    font_dict.set_item(
        COSName.get_pdf_name("Name"), COSName.get_pdf_name("T3CharProc")
    )
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

        content = b"BT\n/F1 12 Tf\n100 700 Td\n<414243> Tj\nET\n"
        content_stream = COSStream()
        content_stream.set_data(content)
        page.set_contents(content_stream)

        doc.save(str(out_path))
    finally:
        doc.close()


def _fmt(v: float) -> str:
    """Mirror the Java probe's ``String.format(Locale.US, "%.6f", v)``."""
    return f"{v:.6f}"


def _py_char_procs(pdf_path: Path) -> str:
    """Reconstruct Type3CharProcProbe output from pypdfbox, line-for-line."""
    lines: list[str] = []
    doc = PDDocument.load(pdf_path)
    try:
        page = next(iter(doc.get_pages()))
        res = page.get_resources()
        if res is None:
            return ""
        for name in res.get_font_names():
            font = res.get_font(name)
            if not isinstance(font, PDType3Font):
                continue
            char_procs = font.get_char_procs()
            if char_procs is None:
                continue
            gnames = sorted(key.name for key in char_procs.key_set())
            for gname in gnames:
                entry = char_procs.get_dictionary_object(
                    COSName.get_pdf_name(gname)
                )
                if not isinstance(entry, COSStream):
                    continue
                proc = PDType3CharProc(font, entry)
                lines.append(f"PROCWIDTH\t{gname}\t{_fmt(proc.get_width())}")

                bbox = proc.get_glyph_b_box()
                if bbox is None:
                    lines.append(f"GLYPHBBOX\t{gname}\tNONE")
                else:
                    lines.append(
                        "GLYPHBBOX\t" + gname + "\t"
                        + _fmt(bbox.get_lower_left_x()) + "\t"
                        + _fmt(bbox.get_lower_left_y()) + "\t"
                        + _fmt(bbox.get_upper_right_x()) + "\t"
                        + _fmt(bbox.get_upper_right_y())
                    )

                m = proc.get_matrix()
                lines.append(
                    f"PROCMATRIX\t{gname}\t" + "\t".join(_fmt(v) for v in m)
                )
    finally:
        doc.close()
    return "\n".join(lines)


@requires_oracle
def test_type3_char_proc_d0_d1_matches_pdfbox(tmp_path: Path) -> None:
    """The d0/d1 operand effects (glyph ``wx`` width, ``d1`` bounding box,
    applied /FontMatrix) of every Type 3 char-proc must decode identically to
    Apache PDFBox 3.0.7."""
    pdf_path = tmp_path / "type3_charproc.pdf"
    _build_type3_pdf(pdf_path)

    java = run_probe_text("Type3CharProcProbe", str(pdf_path))
    py = _py_char_procs(pdf_path)
    jl = java.rstrip().splitlines()
    pl = py.rstrip().splitlines()
    assert len(jl) == len(pl), (
        f"line-count mismatch: java={len(jl)} py={len(pl)}\n"
        f"  java: {jl}\n  py:   {pl}"
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(jl, pl, strict=True))
        if j != p
    ]
    assert not diffs, "Type 3 char-proc d0/d1 parity broken:\n" + "\n".join(diffs)


@requires_oracle
def test_type3_char_proc_d0_has_no_glyph_bbox(tmp_path: Path) -> None:
    """Targeted re-check: a glyph whose char-proc begins with ``d0`` (width
    only) must report ``get_glyph_b_box() is None`` on both sides, while a
    sibling ``d1`` glyph reports a non-None box — so a port that ignores the
    d0/d1 distinction is caught even if widths happen to match."""
    pdf_path = tmp_path / "type3_charproc.pdf"
    _build_type3_pdf(pdf_path)

    java_lines = run_probe_text("Type3CharProcProbe", str(pdf_path)).splitlines()
    java_bbox = [line for line in java_lines if line.startswith("GLYPHBBOX\t")]

    doc = PDDocument.load(pdf_path)
    try:
        page = next(iter(doc.get_pages()))
        font = next(
            f
            for name in page.get_resources().get_font_names()
            if isinstance((f := page.get_resources().get_font(name)), PDType3Font)
        )
        char_procs = font.get_char_procs()
        assert char_procs is not None
        py_bbox: list[str] = []
        for gname in sorted(key.name for key in char_procs.key_set()):
            entry = char_procs.get_dictionary_object(COSName.get_pdf_name(gname))
            assert isinstance(entry, COSStream)
            proc = PDType3CharProc(font, entry)
            bbox = proc.get_glyph_b_box()
            if bbox is None:
                py_bbox.append(f"GLYPHBBOX\t{gname}\tNONE")
            else:
                py_bbox.append(
                    "GLYPHBBOX\t" + gname + "\t"
                    + _fmt(bbox.get_lower_left_x()) + "\t"
                    + _fmt(bbox.get_lower_left_y()) + "\t"
                    + _fmt(bbox.get_upper_right_x()) + "\t"
                    + _fmt(bbox.get_upper_right_y())
                )
    finally:
        doc.close()

    # The d0 glyph ("beta") must be NONE on the Python side; the d1 glyphs must
    # carry a box. Pin the exact set against PDFBox.
    assert py_bbox == java_bbox, (
        "Type 3 d0/d1 bbox distinction diverges:\n"
        f"  java: {java_bbox}\n  py:   {py_bbox}"
    )
    assert "GLYPHBBOX\tbeta\tNONE" in py_bbox
