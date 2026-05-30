"""Live Apache PDFBox differential parity for **text extraction over a Type 3
font** — the ``PDFTextStripper`` string, the word/line segmentation, and the
per-run ``TextPosition`` origins when a page draws glyphs with a Type 3 font
whose advance widths are governed by a non-default ``/FontMatrix``.

No Type 3 fixture ships in the corpus, so (like the Type 3 *metrics* oracle in
``tests/pdmodel/font/oracle/test_type3_font_oracle.py``) this builds a one-page
PDF on the fly: a Type 3 font with a 500-unit em (``/FontMatrix`` x-scale
``0.002``, i.e. 2× the implicit ``0.001``), ``/Differences`` encoding,
``/ToUnicode``, explicit ``/Widths`` per glyph, and hand-rolled ``/CharProcs``.
The page draws two lines; the second splits its glyphs into two separate
``Tj`` runs (``<41>`` then ``<4243>``) so the *origin of the second run on a
line* depends on the advance the stripper gave the first run — the exact place
a Type 3 advance-scaling bug surfaces as a divergent run origin (not merely the
documented intra-line drift, which only moves glyphs *within* a single run).

Two oracle signals:

* ``Type3FontProbe`` emits the page's ``PDFTextStripper`` text in its trailing
  ``TEXT`` block — asserted equal to pypdfbox's extracted string.
* ``TextPosGeomProbe`` emits one canonical ``unicode x y width height fs`` line
  per glyph. pypdfbox is a lite per-*run* stripper, so the per-glyph Java
  stream is reduced to its per-run boundaries (the unicode column concatenates
  to pypdfbox's run text in the same sorted order) and each pypdfbox run origin
  is compared against the Java glyph that begins it.

Bug fixed (wave-level): ``PDFTextStripper._compute_avg_advance`` divided the
average ``/Widths`` value by a fixed ``1000`` to reach the user-space advance.
That is correct only for the implicit ``0.001`` FontMatrix of ordinary simple
fonts; a Type 3 font's ``/Widths`` are in the glyph space of its explicit
``/FontMatrix``. With the 500-unit-em fixture every Type 3 advance was 2× too
short, so the second run on a line was anchored ~7pt left of Apache PDFBox.
The fix scales a Type 3 font's average width by ``fontMatrix[a]`` (matching
upstream ``PDType3Font.getDisplacement``) instead of ``1/1000``.

Reference-frame reconciliation (Y-axis flip, sub-glyph intra-run drift, font
size rounding) is identical to ``test_text_position_oracle.py`` — see that
file's module docstring; nothing here overturns those documented lite-port
carve-outs.

Decorated ``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from pypdfbox.text.text_position import TextPosition
from tests.oracle.harness import requires_oracle, run_probe_text

# Non-default Type 3 FontMatrix: a 500-unit em (x-scale 0.002 == 2× the
# implicit 0.001) so a port that hard-codes the 1/1000 glyph-space scale
# advances every glyph 2× too short and diverges from Apache PDFBox.
_FONT_MATRIX = [0.002, 0.0, 0.0, 0.002, 0.0, 0.0]

# Codes 65/66/67 ('A'/'B'/'C') mapped to letters via /Differences + /ToUnicode.
_GLYPHS = [
    (65, "alpha", "A", 600.0),
    (66, "beta", "B", 700.0),
    (67, "gamma", "C", 550.0),
]
_FIRST_CHAR = 65
_LAST_CHAR = 67

_COORD_EPS = 0.5
_FS_EPS = 0.5


def _char_proc_stream(width: float) -> COSStream:
    """Minimal valid Type 3 glyph proc: ``d1`` (width + bbox) then a box."""
    body = (f"{width} 0 0 0 500 700 d1\n0 0 500 700 re f\n").encode("ascii")
    stream = COSStream()
    stream.set_data(body)
    return stream


def _build_to_unicode_cmap() -> COSStream:
    """Minimal /ToUnicode CMap mapping 0x41->A, 0x42->B, 0x43->C."""
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


def _build_type3_pdf(out_path: Path) -> None:
    """One-page PDF whose only font is a Type 3 font with a 500-unit-em
    FontMatrix, drawing two lines; the second line splits into two ``Tj``
    runs so the second run's origin depends on the first run's advance."""
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
    matrix = COSArray([COSFloat(v) for v in _FONT_MATRIX])
    bbox = COSArray([COSInteger.get(v) for v in (0, 0, 500, 700)])

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
    font_dict.set_item(COSName.get_pdf_name("ToUnicode"), _build_to_unicode_cmap())

    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        font = PDType3Font(font_dict)
        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), font)
        font.set_resources(PDResources())
        page.set_resources(res)

        content = (
            b"BT\n/F1 12 Tf\n"
            b"100 700 Td\n<414243> Tj\n"
            b"0 -20 Td\n<41> Tj\n<4243> Tj\n"
            b"ET\n"
        )
        content_stream = COSStream()
        content_stream.set_data(content)
        page.set_contents(content_stream)

        doc.save(str(out_path))
    finally:
        doc.close()


class _Glyph:
    """One parsed line of TextPosGeomProbe per-glyph output."""

    __slots__ = ("unicode", "x", "y", "width", "height", "fs")

    def __init__(self, fields: list[str]) -> None:
        self.unicode = fields[0]
        self.x = float(fields[1])
        self.y = float(fields[2])
        self.width = float(fields[3])
        self.height = float(fields[4])
        self.fs = float(fields[5])


def _java_glyphs(pdf_path: Path) -> list[_Glyph]:
    out = run_probe_text("TextPosGeomProbe", str(pdf_path), "1")
    glyphs: list[_Glyph] = []
    for line in out.splitlines():
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) != 6:
            continue
        glyphs.append(_Glyph(fields))
    return glyphs


def _java_text(pdf_path: Path) -> str:
    """The page's PDFTextStripper text from Type3FontProbe's TEXT block."""
    out = run_probe_text("Type3FontProbe", str(pdf_path))
    return out.split("TEXT\t", 1)[1]


def _py_runs(pdf_path: Path) -> tuple[list[TextPosition], float]:
    captured: list[TextPosition] = []

    class _Capture(PDFTextStripper):
        def write_string(self, text, text_positions, sink=None):  # type: ignore[override]
            captured.extend(text_positions)
            return super().write_string(text, text_positions, sink)

    doc = PDDocument.load(str(pdf_path))
    try:
        page = doc.get_page(0)
        ph = page.get_media_box().get_height()
        stripper = _Capture()
        stripper.set_sort_by_position(True)
        stripper.set_start_page(1)
        stripper.set_end_page(1)
        stripper.get_text(doc)
        return captured, ph
    finally:
        doc.close()


def _py_text(pdf_path: Path) -> str:
    doc = PDDocument.load(str(pdf_path))
    try:
        return PDFTextStripper().get_text(doc)
    finally:
        doc.close()


@requires_oracle
def test_type3_extracted_text_matches_pdfbox(tmp_path: Path) -> None:
    """The Type 3 page's ``PDFTextStripper`` string (and its line breaks)
    matches Apache PDFBox byte-for-byte."""
    pdf_path = tmp_path / "type3_text.pdf"
    _build_type3_pdf(pdf_path)
    assert _py_text(pdf_path) == _java_text(pdf_path)


@requires_oracle
def test_type3_glyph_stream_concatenates_to_run_text(tmp_path: Path) -> None:
    """Granularity precondition: the Java per-glyph unicode stream
    concatenates to pypdfbox's per-run text in the same sorted order."""
    pdf_path = tmp_path / "type3_text.pdf"
    _build_type3_pdf(pdf_path)
    glyphs = _java_glyphs(pdf_path)
    runs, _ph = _py_runs(pdf_path)
    assert "".join(r.text for r in runs) == "".join(g.unicode for g in glyphs)


@requires_oracle
def test_type3_run_origins_match_pdfbox(tmp_path: Path) -> None:
    """Each pypdfbox run origin matches the Java glyph that begins it on x,
    flipped y, and font size — within the documented average-advance
    tolerance. This is the regression pin for the Type 3 advance-scaling
    fix: a port that divides ``/Widths`` by a fixed 1000 anchors the second
    run on line two ~7pt left of Apache PDFBox (well past ``_COORD_EPS``).
    """
    pdf_path = tmp_path / "type3_text.pdf"
    _build_type3_pdf(pdf_path)
    glyphs = _java_glyphs(pdf_path)
    runs, ph = _py_runs(pdf_path)
    assert "".join(r.text for r in runs) == "".join(g.unicode for g in glyphs)

    idx = 0
    for run in runs:
        first = glyphs[idx]
        assert run.text[0] == first.unicode
        # The avg-advance approximation can differ from the true width of the
        # specific first glyph by less than one glyph width; 1.0pt is well
        # inside the FontMatrix-scaled advance yet far below the ~7pt bug.
        assert run.x == pytest.approx(first.x, abs=1.0)
        assert (ph - run.y) == pytest.approx(first.y, abs=_COORD_EPS)
        assert run.get_font_size_in_pt() == pytest.approx(first.fs, abs=_FS_EPS)
        idx += len(run.text)


@requires_oracle
def test_type3_run_width_matches_font_matrix_scaled_advance(tmp_path: Path) -> None:
    """The full first-line run (``ABC``) advance width equals the sum of the
    three FontMatrix-scaled glyph widths Apache PDFBox reports, proving the
    advance honours ``/FontMatrix`` rather than a fixed 1/1000 scale."""
    pdf_path = tmp_path / "type3_text.pdf"
    _build_type3_pdf(pdf_path)
    glyphs = _java_glyphs(pdf_path)
    runs, _ph = _py_runs(pdf_path)

    first_run = runs[0]
    assert first_run.text == "ABC"
    java_total = sum(g.width for g in glyphs[:3])  # A + B + C on line one
    assert first_run.width == pytest.approx(java_total, abs=1.0)
