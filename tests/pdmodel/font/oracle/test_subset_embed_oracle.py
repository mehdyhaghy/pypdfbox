"""Live Apache PDFBox differential parity for pypdfbox's TrueType / Type0 font
*embedding* and *subsetting* output.

Where ``test_cid_gid_oracle`` reads the glyph-resolution pipeline of *existing*
embedded fonts, this module pins the inverse: pypdfbox *produces* the embedded
font program (full embed and subset), and Apache PDFBox 3.0.7 must be able to
parse it and read consistent metrics. The invariant under test is that the
subset TrueType program pypdfbox writes is a valid font that PDFBox loads via
``PDCIDFontType2.getTrueTypeFont()`` / ``PDTrueTypeFont.getTrueTypeFont()`` and
that yields the same advance widths for the embedded glyphs, plus the text the
content stream encoded round-trips through ``PDFTextStripper``.

Two engines confirm each build:

* **pypdfbox round-trip** — build, save, reload in pypdfbox; assert the embedded
  program's glyph count / unitsPerEm and the per-code widths match the source
  font.
* **SubsetEmbedProbe (Java)** — load the same bytes in PDFBox and report glyph
  count, unitsPerEm, table presence (cmap / glyf / hmtx), per-GID advances, and
  per-used-code ``getWidthFromFont``. The Python side reconstructs the identical
  line format so any divergence surfaces as a single differing line.

Divergence history:
  * Wave 1418 found pypdfbox's embedded Identity Type0 ``encode`` emitted the
    Unicode codepoint as the CID instead of the embedded program's glyph id, so
    PDFBox rendered the wrong glyphs (e.g. "Hello" -> "e£ªª­"), and ``subset()``
    left ``/W`` keyed by the full font's glyph ids with ``/CIDToGIDMap
    /Identity`` after fontTools renumbered the subset glyphs. Fixed in
    ``PDType0Font.encode`` (codepoint -> GID via the embedded cmap) and
    ``PDType0Font.subset`` (rebuild ``/CIDToGIDMap`` + ``/W`` against the subset
    glyph renumbering). See CHANGES.md.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSName, COSNumber
from pypdfbox.pdmodel import PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.text import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_TTF = (
    Path(__file__).resolve().parents[4]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)

_TEXT = "Hello World 123"


# --------------------------------------------------------------------------- #
# PDF builders — produce a single-page document that embeds the bundled
# LiberationSans, writes _TEXT, and saves to a bytes buffer.
# --------------------------------------------------------------------------- #


def _build_type0_pdf(*, subset: bool) -> bytes:
    """Embed LiberationSans as a composite CIDFontType2 (full or subset)."""
    doc = PDDocument()
    page = PDPage(PDRectangle.LETTER)
    doc.add_page(page)
    with _TTF.open("rb") as fh:
        font = PDType0Font.load(doc, fh, subset)
    encoded = font.encode(_TEXT)
    if subset:
        font.subset(_TEXT)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 14)
        cs.new_line_at_offset(50, 700)
        cs.show_text(encoded)
        cs.end_text()
    sink = io.BytesIO()
    doc.save(sink)
    doc.close()
    return sink.getvalue()


def _build_simple_pdf(*, subset: bool) -> bytes:
    """Embed LiberationSans as a simple TrueType font (full or subset)."""
    doc = PDDocument()
    page = PDPage(PDRectangle.LETTER)
    doc.add_page(page)
    with _TTF.open("rb") as fh:
        font = PDTrueTypeFont.load(doc, fh)
    if subset:
        font.subset(_TEXT)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 14)
        cs.new_line_at_offset(50, 700)
        cs.show_text(_TEXT)
        cs.end_text()
    sink = io.BytesIO()
    doc.save(sink)
    doc.close()
    return sink.getvalue()


def _write_pdf(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


# --------------------------------------------------------------------------- #
# Python reproduction of SubsetEmbedProbe's line format.
# --------------------------------------------------------------------------- #


def _fmt(value: float) -> str:
    return f"{value:.4f}"


def _line_equiv(java_line: str, py_line: str) -> bool:
    """Compare two probe lines, tolerating last-digit width rounding.

    Java's ``String.format("%.4f")`` rounds half-up while Python's f-string
    rounds half-even, so a width whose 5th decimal is exactly 5 (e.g.
    ``519.53125``) renders as ``519.5313`` (Java) vs ``519.5312`` (Python).
    The underlying ``getWidthFromFont`` value is identical; only the display
    rounding differs. WID / GADV / PROG width columns are compared numerically
    with a 1e-3 tolerance; every other field must match byte-for-byte.
    """
    if java_line == py_line:
        return True
    jf = java_line.split("\t")
    pf = py_line.split("\t")
    if len(jf) != len(pf) or not jf:
        return False
    # Only the trailing width column may differ; all leading fields equal.
    if jf[:-1] != pf[:-1]:
        return False
    try:
        return abs(float(jf[-1]) - float(pf[-1])) < 1e-3
    except ValueError:
        return False


def _used_codes_type0(descendant: PDCIDFontType2) -> list[int]:
    """Mirror the probe's ``usedCodes`` for a Type0 font: the CIDs spelled out
    by the descendant's ``/W`` array, ascending and de-duplicated."""
    out: set[int] = set()
    w = descendant.get_cos_object().get_dictionary_object(COSName.get_pdf_name("W"))
    if not isinstance(w, COSArray):
        return []
    i = 0
    n = w.size()
    while i < n:
        first = w.get_object(i)
        if not isinstance(first, COSNumber):
            break
        c_first = first.int_value()
        if i + 1 >= n:
            break
        nxt = w.get_object(i + 1)
        if isinstance(nxt, COSArray):
            for k in range(nxt.size()):
                out.add(c_first + k)
            i += 2
        elif isinstance(nxt, COSNumber):
            if i + 2 >= n:
                break
            c_last = nxt.int_value()
            upper = min(c_last, c_first + 1024)
            for c in range(c_first, upper + 1):
                out.add(c)
            i += 3
        else:
            break
    return sorted(out)


def _py_probe(pdf_bytes: bytes) -> str:
    """Reconstruct SubsetEmbedProbe output from pypdfbox, line-for-line."""
    lines: list[str] = []
    doc = PDDocument.load(io.BytesIO(pdf_bytes))
    try:
        for page_index, page in enumerate(doc.get_pages()):
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                font = res.get_font(name)
                key = name.name if hasattr(name, "name") else str(name)
                if isinstance(font, PDType0Font):
                    descendant = font.get_descendant_font()
                    ttf = (
                        descendant.get_true_type_font()
                        if isinstance(descendant, PDCIDFontType2)
                        else None
                    )
                    used = (
                        _used_codes_type0(descendant)
                        if isinstance(descendant, PDCIDFontType2)
                        else []
                    )
                elif isinstance(font, PDTrueTypeFont):
                    descendant = None
                    ttf = font.get_true_type_font()
                    used = list(range(font.get_first_char(), font.get_last_char() + 1))
                    used = [c for c in used if c - font.get_first_char() < 256]
                else:
                    continue

                embedded = font.is_embedded()
                lines.append(
                    f"FONT\t{page_index}\t{key}\t{font.get_name()}\t"
                    f"{font.get_sub_type()}\t{'true' if embedded else 'false'}\t"
                    f"{'TrueType' if ttf is not None else 'NONE'}"
                )
                if ttf is None:
                    continue
                num_glyphs = ttf.get_number_of_glyphs()
                lines.append(
                    f"PROG\t{page_index}\t{key}\t{num_glyphs}\t"
                    f"{ttf.get_units_per_em()}\t"
                    f"{'true' if ttf.get_table('cmap') is not None else 'false'}\t"
                    f"{'true' if ttf.get_glyph_table() is not None else 'false'}\t"
                    f"{'true' if ttf.get_horizontal_metrics() is not None else 'false'}"
                )
                for gid in range(num_glyphs):
                    lines.append(
                        f"GADV\t{page_index}\t{key}\t{gid}\t{ttf.get_advance_width(gid)}"
                    )
                for code in used:
                    if isinstance(font, PDType0Font):
                        cid = font.code_to_cid(code)
                        gid = descendant.code_to_gid(cid)
                    else:
                        gid = font.code_to_gid(code)
                    width = font.get_width_from_font(code)
                    lines.append(
                        f"WID\t{page_index}\t{key}\t{code}\t{gid}\t{_fmt(width)}"
                    )
    finally:
        doc.close()
    return "\n".join(lines) + ("\n" if lines else "")


# --------------------------------------------------------------------------- #
# (a) pypdfbox embeds -> reloads in pypdfbox -> widths / glyph count correct.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("builder", "subset"),
    [
        (_build_type0_pdf, False),
        (_build_type0_pdf, True),
        (_build_simple_pdf, False),
        (_build_simple_pdf, True),
    ],
    ids=["type0_full", "type0_subset", "simple_full", "simple_subset"],
)
def test_pypdfbox_embed_reload_program_is_valid(builder, subset) -> None:
    """pypdfbox must reload its own embedded program with a non-empty glyph
    count, the source font's unitsPerEm (2048 for LiberationSans), and the
    cmap / glyf / hmtx tables PDFBox requires to read metrics."""
    data = builder(subset=subset)
    doc = PDDocument.load(io.BytesIO(data))
    try:
        seen = 0
        for page in doc.get_pages():
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                font = res.get_font(name)
                if isinstance(font, PDType0Font):
                    ttf = font.get_descendant_font().get_true_type_font()
                elif isinstance(font, PDTrueTypeFont):
                    ttf = font.get_true_type_font()
                else:
                    continue
                assert ttf is not None
                assert ttf.get_number_of_glyphs() > 0
                assert ttf.get_units_per_em() == 2048
                assert ttf.get_table("cmap") is not None
                assert ttf.get_glyph_table() is not None
                assert ttf.get_horizontal_metrics() is not None
                seen += 1
        assert seen == 1
    finally:
        doc.close()


@pytest.mark.parametrize(
    ("builder", "subset"),
    [
        (_build_type0_pdf, True),
        (_build_simple_pdf, True),
    ],
    ids=["type0_subset", "simple_subset"],
)
def test_subset_is_smaller_than_full_program(builder, subset) -> None:
    """A subset embed must be a small fraction of the ~316 KiB source font."""
    data = builder(subset=subset)
    assert len(data) < _TTF.stat().st_size // 3


# --------------------------------------------------------------------------- #
# (b) SubsetEmbedProbe (Java) reads the same program and reports consistent
#     glyph count / widths / unitsPerEm — line-for-line parity with pypdfbox.
# --------------------------------------------------------------------------- #


@requires_oracle
@pytest.mark.parametrize(
    ("builder", "subset"),
    [
        (_build_type0_pdf, False),
        (_build_type0_pdf, True),
        (_build_simple_pdf, False),
        (_build_simple_pdf, True),
    ],
    ids=["type0_full", "type0_subset", "simple_full", "simple_subset"],
)
def test_pdfbox_reads_embedded_program_consistently(
    builder, subset, tmp_path: Path
) -> None:
    """Apache PDFBox must parse pypdfbox's embedded (subset) TrueType program
    and report the same glyph count, unitsPerEm, table presence, per-GID
    advances and per-used-code widths that pypdfbox computes."""
    data = builder(subset=subset)
    path = _write_pdf(tmp_path, "embed.pdf", data)
    java = run_probe_text("SubsetEmbedProbe", str(path)).splitlines()
    py = _py_probe(data).splitlines()
    assert len(java) == len(py), (
        f"line-count mismatch: java={len(java)} py={len(py)}\n"
        f"java head: {java[:6]}\npy head: {py[:6]}"
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if not _line_equiv(j, p)
    ]
    assert not diffs, "embed/subset parity broken:\n" + "\n".join(diffs[:40])


@requires_oracle
@pytest.mark.parametrize(
    ("builder", "subset"),
    [
        (_build_type0_pdf, False),
        (_build_type0_pdf, True),
        (_build_simple_pdf, False),
        (_build_simple_pdf, True),
    ],
    ids=["type0_full", "type0_subset", "simple_full", "simple_subset"],
)
def test_pdfbox_extracts_the_text_pypdfbox_wrote(builder, subset, tmp_path: Path) -> None:
    """The end-to-end invariant: the glyphs pypdfbox encoded into the content
    stream, mapped through the embedded (subset) program's /CIDToGIDMap, must
    let PDFBox extract back the exact text — proving the encode + subset
    glyph-renumbering round-trips."""
    data = builder(subset=subset)
    path = _write_pdf(tmp_path, "text.pdf", data)
    java = run_probe_text("TextExtractProbe", str(path)).strip()
    assert java == _TEXT


# --------------------------------------------------------------------------- #
# pypdfbox-only round-trip: extraction parity without the oracle (regression
# pin for the wave-1418 encode + subset-remap fix).
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("builder", "subset"),
    [
        (_build_type0_pdf, False),
        (_build_type0_pdf, True),
        (_build_simple_pdf, False),
        (_build_simple_pdf, True),
    ],
    ids=["type0_full", "type0_subset", "simple_full", "simple_subset"],
)
def test_pypdfbox_text_extraction_round_trip(builder, subset) -> None:
    """pypdfbox's own text stripper must recover _TEXT from the embedded
    (subset) font it produced."""
    data = builder(subset=subset)
    doc = PDDocument.load(io.BytesIO(data))
    try:
        extracted = PDFTextStripper().get_text(doc).strip()
    finally:
        doc.close()
    assert extracted == _TEXT


def test_subset_remaps_w_to_used_glyphs_only() -> None:
    """Regression pin for the wave-1418 subset /W rebuild (no oracle needed).

    After subsetting a Type0 font down to _TEXT, the descendant's /W must
    describe only the handful of used CIDs (the original glyph ids of the
    text's characters), not the full font's ~2600 glyphs."""
    data = _build_type0_pdf(subset=True)
    doc = PDDocument.load(io.BytesIO(data))
    try:
        descendant = None
        for page in doc.get_pages():
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                font = res.get_font(name)
                if isinstance(font, PDType0Font):
                    descendant = font.get_descendant_font()
        assert isinstance(descendant, PDCIDFontType2)
        used = _used_codes_type0(descendant)
        # _TEXT has 11 distinct visible glyphs (incl. space); CID 0 is not in
        # /W (its default width is dropped). Must be well under the full font.
        assert 0 < len(used) <= 16
        # The embedded subset program must hold only those glyphs (+ .notdef).
        ttf = descendant.get_true_type_font()
        assert ttf.get_number_of_glyphs() <= 16
    finally:
        doc.close()
