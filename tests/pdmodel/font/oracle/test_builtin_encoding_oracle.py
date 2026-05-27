"""Live Apache PDFBox parity for embedded simple fonts with NO ``/Encoding``.

Pins the wave-1434 ``DEFERRED.md`` (pdmodel/font) bug: an embedded simple font
(Type 1 ``/FontFile`` or TrueType ``/FontFile2``) whose PDF font dict carries no
``/Encoding`` entry rendered **blank** in pypdfbox. Root cause was
``PDSimpleFont.get_encoding_typed``: its no-``/Encoding`` else-branch surfaced
the font program's built-in encoding only for non-embedded Standard-14 fonts
(the wave-1431 fix), returning ``None`` for embedded fonts — so
``PDType1Font._code_to_glyph_name`` resolved every code to ``None`` and the
glyph was dropped. Upstream ``PDSimpleFont.readEncoding`` falls back to
``readEncodingFromFont()`` for embedded fonts too.

The fix makes the else-branch always defer to ``read_encoding_from_font()``
(mirroring upstream). This test proves, against the live PDFBox 3.0.7 oracle
(``oracle/probes/BuiltinEncodingProbe.java``), that for BOTH an embedded Type 1
and an embedded TrueType simple font with no ``/Encoding``:

* the resolved per-code glyph name (``font.getEncoding().getName(code)``) and
* the per-code width (``font.getWidth(code)``) and
* the extracted ``PDFTextStripper`` text

match PDFBox exactly across all 256 codes, AND the rendered page matches
PDFBox's render fingerprint (16x16 luminance grid, MAD < 6 / MAXDIFF < 60) —
i.e. the glyphs are no longer blank.

Fixtures are reused from the wave-1416 Type 1 PFB and the fontbox TTF fixtures;
the no-``/Encoding`` PDFs are built in-test so the bug is reproduced exactly.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.rendering import PDFRenderer
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
_PFB = _FIXTURES / "fontbox" / "type1" / "DemoType1.pfb"
_TTF = _FIXTURES / "fontbox" / "ttf" / "LiberationSans-Regular.ttf"

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

# Big, multi-line text so the glyphs occupy several 16x16 grid cells — a
# blank page (the pre-fix symptom) then shows up as zero non-white cells.
_SHOWN = "ABCAB"
_LINES = 4


def _draw(doc: PDDocument, page: PDPage, font: object) -> None:
    cs = PDPageContentStream(doc, page)
    cs.begin_text()
    cs.set_font(font, 96)
    cs.new_line_at_offset(40, 600)
    for _ in range(_LINES):
        cs.show_text(_SHOWN)
        cs.new_line_at_offset(0, -110)
    cs.end_text()
    cs.close()


def _build_type1_no_encoding(out_path: Path) -> None:
    """Embed the Demo Type 1 PFB with ``encoding=None`` so the embedder writes
    NO ``/Encoding`` entry (the bug condition), then draw text."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        font = PDType1Font.load(doc, _PFB.read_bytes(), encoding=None)
        assert font.get_encoding() is None, "fixture must have no /Encoding entry"
        _draw(doc, page, font)
        doc.save(str(out_path))
    finally:
        doc.close()


def _build_truetype_no_encoding(out_path: Path) -> None:
    """Embed the Liberation Sans TTF, then strip the ``/Encoding`` entry the
    embedder writes so the resulting ``/FontFile2`` font dict has no
    ``/Encoding`` (the bug condition), then draw text."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        font = PDTrueTypeFont.load(doc, _TTF.read_bytes(), encoding=None)
        font.get_cos_object().remove_item(COSName.ENCODING)
        assert font.get_encoding() is None, "fixture must have no /Encoding entry"
        _draw(doc, page, font)
        doc.save(str(out_path))
    finally:
        doc.close()


def _canon_number(value: float) -> str:
    """Render a number the way the Java probe's ``canonNumber`` does."""
    if value == int(value):
        return str(int(value))
    return str(float(value))


def _py_per_code(path: Path) -> tuple[dict[int, str], dict[int, str]]:
    """pypdfbox per-code glyph name + canonical width for the first simple
    font on page 0."""
    doc = PDDocument.load(path)
    try:
        page = next(iter(doc.get_pages()))
        res = page.get_resources()
        assert res is not None
        font = res.get_font(next(iter(res.get_font_names())))
        enc = font.get_encoding_typed()
        names: dict[int, str] = {}
        widths: dict[int, str] = {}
        for code in range(256):
            name = enc.get_name(code) if enc is not None else ".notdef"
            names[code] = name or ".notdef"
            widths[code] = _canon_number(font.get_width(code))
        return names, widths
    finally:
        doc.close()


def _py_text(path: Path) -> str:
    doc = PDDocument.load(path)
    try:
        return PDFTextStripper().get_text(doc)
    finally:
        doc.close()


def _py_grid(path: Path) -> tuple[tuple[int, int], list[int]]:
    """pypdfbox 16x16 luminance fingerprint of page 0 at 72 DPI — same recipe
    as ``BuiltinEncodingProbe`` / ``RenderProbe``."""
    doc = PDDocument.load(path)
    try:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("L")
        w, h = img.size
        px = img.load()
        total = [0] * (_GRID * _GRID)
        count = [0] * (_GRID * _GRID)
        for y in range(h):
            cy = min(y * _GRID // h, _GRID - 1)
            for x in range(w):
                cx = min(x * _GRID // w, _GRID - 1)
                idx = cy * _GRID + cx
                total[idx] += px[x, y]
                count[idx] += 1
        grid = [
            round(total[i] / count[i]) if count[i] else 255
            for i in range(_GRID * _GRID)
        ]
        return (w, h), grid
    finally:
        doc.close()


def _parse_probe(output: str) -> dict:
    """Parse ``BuiltinEncodingProbe`` stdout into a structured dict."""
    font_line = None
    enc = None
    names: dict[int, str] = {}
    widths: dict[int, str] = {}
    text_lines: list[str] = []
    dim: tuple[int, int] | None = None
    grid: list[int] | None = None
    for line in output.splitlines():
        fields = line.split("\t")
        tag = fields[0]
        if tag == "FONT":
            font_line = fields[1:]
        elif tag == "ENC":
            enc = fields[1]
        elif tag == "CODE":
            code = int(fields[1])
            names[code] = fields[2]
            widths[code] = fields[3]
        elif tag == "TEXT":
            text_lines.append("" if fields[1] == "␀" else fields[1])
        elif tag == "DIM":
            dim = (int(fields[1]), int(fields[2]))
        elif tag == "GRID":
            grid = [int(x) for x in fields[1:]]
    return {
        "font": font_line,
        "enc": enc,
        "names": names,
        "widths": widths,
        "text_lines": text_lines,
        "dim": dim,
        "grid": grid,
    }


def _assert_render_matches(label: str, oracle: dict, path: Path) -> None:
    py_dim, py_grid = _py_grid(path)
    assert py_dim == oracle["dim"], f"{label}: dim {py_dim} != oracle {oracle['dim']}"
    oracle_grid = oracle["grid"]
    assert oracle_grid is not None
    diffs = [abs(a - b) for a, b in zip(oracle_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, f"{label}: render MAD {mad:.3f} >= {_MAD_TOLERANCE}"
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: render MAXDIFF {maxdiff} >= {_MAXDIFF_TOLERANCE}"
    )
    # The whole point of the bug fix: the glyphs are NOT blank. PDFBox draws
    # them (non-white grid cells), so pypdfbox must too.
    oracle_nonwhite = sum(1 for v in oracle_grid if v < 250)
    py_nonwhite = sum(1 for v in py_grid if v < 250)
    assert oracle_nonwhite > 0, f"{label}: oracle fixture unexpectedly blank"
    assert py_nonwhite > 0, f"{label}: pypdfbox rendered a BLANK page (the bug)"


@requires_oracle
def test_embedded_type1_no_encoding_matches_pdfbox(tmp_path: Path) -> None:
    """Embedded Type 1 (``/FontFile``) with no ``/Encoding``: glyph names,
    widths, extracted text and render all match PDFBox; glyphs not blank."""
    pdf = tmp_path / "type1_no_encoding.pdf"
    _build_type1_no_encoding(pdf)

    oracle = _parse_probe(run_probe_text("BuiltinEncodingProbe", str(pdf)))
    # The probe confirms PDFBox sees an embedded Type1 with no /Encoding dict.
    assert oracle["font"] is not None
    base_font, sub_type, embedded, has_enc_dict = oracle["font"]
    assert sub_type == "Type1"
    assert embedded == "true"
    assert has_enc_dict == "false"

    py_names, py_widths = _py_per_code(pdf)
    assert py_names == oracle["names"], "Type1 per-code glyph names diverge"
    assert py_widths == oracle["widths"], "Type1 per-code widths diverge"

    # Spot-check the built-in mapping the bug dropped (65->A, 66->B, 67->C).
    assert oracle["names"][65] == "A"
    assert py_names[65] == "A"

    py_lines = _py_text(pdf).split("\n")
    assert py_lines == oracle["text_lines"], "Type1 extracted text diverges"

    _assert_render_matches("Type1", oracle, pdf)


@requires_oracle
def test_embedded_truetype_no_encoding_matches_pdfbox(tmp_path: Path) -> None:
    """Embedded TrueType (``/FontFile2``) with no ``/Encoding``: glyph names,
    widths, extracted text and render all match PDFBox; glyphs not blank.

    Non-symbolic TrueType resolves the no-``/Encoding`` case to PDFBox's
    StandardEncoding (not the WinAnsi the embedder would otherwise write, and
    not the symbolic-cmap path) — verified against the oracle."""
    pdf = tmp_path / "truetype_no_encoding.pdf"
    _build_truetype_no_encoding(pdf)

    oracle = _parse_probe(run_probe_text("BuiltinEncodingProbe", str(pdf)))
    assert oracle["font"] is not None
    base_font, sub_type, embedded, has_enc_dict = oracle["font"]
    assert sub_type == "TrueType"
    assert embedded == "true"
    assert has_enc_dict == "false"

    py_names, py_widths = _py_per_code(pdf)
    assert py_names == oracle["names"], "TrueType per-code glyph names diverge"
    assert py_widths == oracle["widths"], "TrueType per-code widths diverge"

    assert oracle["names"][65] == "A"
    assert py_names[65] == "A"

    py_lines = _py_text(pdf).split("\n")
    assert py_lines == oracle["text_lines"], "TrueType extracted text diverges"

    _assert_render_matches("TrueType", oracle, pdf)
