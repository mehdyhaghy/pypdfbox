"""Live PDFBox differential parity for simple-font ``/Encoding`` resolution.

Wave 1417. Verifies that pypdfbox resolves a :class:`PDSimpleFont`'s
``/Encoding`` — the base-encoding selection (Standard / WinAnsi / MacRoman /
MacExpert), whether it is a :class:`DictionaryEncoding`, and the full
code -> glyph-name map for codes 0..255 — exactly as Apache PDFBox 3.0.7 does.

This surface is bug-prone: earlier waves found real MacRoman / PDFDocEncoding
glyph-name bugs, and the symbolic-vs-non-symbolic TrueType base-encoding default
is a classic divergence. The oracle output is produced by
``oracle/probes/EncodingDiffProbe.java``; the Python side here reconstructs the
identical line format so any divergence shows up as a single differing line.

Two fixture sources:

* *real* fixtures whose AcroForm default-resources fonts carry a
  ``/Differences`` array (Helvetica family over StandardEncoding, LucidaGrande
  TrueType over MacRomanEncoding);
* a *built* fixture (``_built_diff_pdf``) with a custom ``/Differences`` array
  over each of the four base encodings (Standard / WinAnsi / MacRoman /
  MacExpert) so the base-selection + override logic is fully exercised against
  the live oracle, not just our hand-written expectations.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.font.encoding.dictionary_encoding import DictionaryEncoding
from pypdfbox.pdmodel.font.pd_simple_font import PDSimpleFont
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures"

# Real fixtures whose AcroForm DR fonts use /Differences. The probe walks page
# resources then the AcroForm default resources, so these exercise the reader
# path (font dict -> DictionaryEncoding) over StandardEncoding (Type1 Helvetica
# family) and MacRomanEncoding (TrueType LucidaGrande).
_FIXTURES_REL = [
    "pdfwriter/acroform.pdf",  # Helvetica/Bold/Oblique over StandardEncoding
    "pdmodel/interactive/form/AcroFormsBasicFields.pdf",  # + LucidaGrande/MacRoman
    "pdmodel/interactive/form/AlignmentTests.pdf",  # Helv diff + Arial WinAnsi
    "pdmodel/interactive/form/DifferentDALevels.pdf",
    "pdmodel/interactive/form/AcroFormsRotation.pdf",
]


def _encoding_id(enc: object) -> str:
    """Mirror the probe's ``encodingId``: the encoding's /Encoding COSName
    literal when it has one, else the class simple name, else "null"."""
    if enc is None:
        return "null"
    cos = enc.get_cos_object()
    if isinstance(cos, COSName):
        return cos.name
    return type(enc).__name__


def _py_encoding(pdf_path: Path) -> str:
    """Reconstruct EncodingDiffProbe output from pypdfbox.

    Mirrors the probe's control flow line-for-line so a textual diff isolates a
    single divergence.
    """
    lines: list[str] = []
    doc = PDDocument.load(pdf_path)
    try:
        for page_index, page in enumerate(doc.get_pages()):
            res = page.get_resources()
            if res is not None:
                for name in res.get_font_names():
                    _emit_font(lines, page_index, name, res)
        form = doc.get_document_catalog().get_acro_form()
        if form is not None:
            dr = form.get_default_resources()
            if dr is not None:
                for name in dr.get_font_names():
                    _emit_font(lines, -1, name, dr)
    finally:
        doc.close()
    return "\n".join(lines) + ("\n" if lines else "")


def _emit_font(lines: list[str], page_index: int, name: COSName, res: object) -> None:
    key = name.name
    try:
        font = res.get_font(name)
    except Exception:
        lines.append(f"FONT\t{page_index}\t{key}\tLOAD_ERR")
        return
    if font is None:
        lines.append(f"FONT\t{page_index}\t{key}\tNULL")
        return
    if not isinstance(font, PDSimpleFont):
        lines.append(f"SKIP\t{page_index}\t{key}\t{type(font).__name__}")
        return

    lines.append(
        f"FONT\t{page_index}\t{key}\t{font.get_name()}\t{font.get_sub_type()}"
    )
    enc = font.get_encoding_typed()
    is_dict = isinstance(enc, DictionaryEncoding)
    enc_class = "null" if enc is None else type(enc).__name__
    if enc is None:
        base_id = "null"
    elif is_dict:
        base_id = _encoding_id(enc.get_base_encoding())
    else:
        base_id = _encoding_id(enc)
    lines.append(f"ENC\t{enc_class}\t{str(is_dict).lower()}\t{base_id}")
    for code in range(256):
        glyph = ".notdef" if enc is None else enc.get_name(code)
        lines.append(f"CODE\t{code}\t{glyph}")


# --- DOCUMENTED DIVERGENCE -------------------------------------------------
#
# A *non-embedded Standard-14 ZapfDingbats* font with NO /Encoding entry
# resolves differently between the two libraries, and the difference is a
# cross-module ``PDType1Font`` source-selection concern, NOT an encoding/ table
# bug:
#
#   * Upstream PDFBox's PDType1Font.readEncodingFromFont() builds a
#     Type1Encoding from the bundled AFM's CharMetrics (which maps the full
#     0..255 Zapf vector, including codes 128..141 / glyphs a89..a96).
#   * pypdfbox's PDSimpleFont.get_encoding_typed() returns None when /Encoding
#     is absent — its established contract; the built-in font-program encoding
#     is surfaced lazily by per-subclass helpers, and 29 existing tests pin the
#     None-when-absent behaviour. The static ZapfDingbatsEncoding tables are
#     byte-identical between the libraries (verified: PDFBox's own
#     ZapfDingbatsEncoding class also returns .notdef for 128..141), so the
#     encoding tables under test are correct.
#
# To keep the differential strict on the /Differences surface (the actual
# subject of this test) while not over-fitting to that cross-module divergence,
# drop the built-in (non-/Differences, AFM-resolved Type1Encoding) ZapfDingbats
# font block from BOTH sides. The divergence is tracked in CHANGES.md.


def _drop_zapf_builtin_block(lines: list[str]) -> list[str]:
    """Drop the no-/Encoding built-in ZapfDingbats font block.

    Java emits it as a Type1Encoding (AFM-derived); pypdfbox emits ENC<TAB>null
    (encoding absent). Both blocks start at a FONT line whose base font is
    ZapfDingbats and run until the next FONT/SKIP line.
    """
    out: list[str] = []
    skipping = False
    for line in lines:
        if line.startswith(("FONT\t", "SKIP\t")):
            cols = line.split("\t")
            skipping = (
                line.startswith("FONT\t")
                and len(cols) >= 4
                and cols[3] == "ZapfDingbats"
            )
            if skipping:
                continue
        if skipping and line.startswith(("ENC\t", "CODE\t")):
            continue
        out.append(line)
    return out


def _assert_parity(fixture_id: str, pdf_path: Path) -> None:
    jl = _drop_zapf_builtin_block(
        run_probe_text("EncodingDiffProbe", str(pdf_path)).splitlines()
    )
    pl = _drop_zapf_builtin_block(_py_encoding(pdf_path).splitlines())
    assert len(jl) == len(pl), (
        f"line-count mismatch for {fixture_id}: java={len(jl)} py={len(pl)}\n"
        f"  first java tail: {jl[-3:]}\n  first py tail: {pl[-3:]}"
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(jl, pl, strict=True))
        if j != p
    ]
    assert not diffs, (
        f"simple-font encoding parity broken for {fixture_id}:\n"
        + "\n".join(diffs[:40])
    )


@requires_oracle
@pytest.mark.parametrize("fixture_rel", _FIXTURES_REL)
def test_simple_font_encoding_matches_pdfbox(fixture_rel: str) -> None:
    """Every PDSimpleFont's resolved encoding (class, dictionary flag, base
    identifier, and the full code -> glyph-name map for 0..255) must match
    Apache PDFBox exactly across the /Differences-bearing real fixtures."""
    pdf_path = _FIXTURES / fixture_rel
    assert pdf_path.is_file(), f"missing fixture: {pdf_path}"
    _assert_parity(fixture_rel, pdf_path)


# --- built fixture: /Differences over each base encoding --------------------

# A custom /Differences run reusable across base encodings. Codes chosen so the
# override genuinely diverges from every base (e.g. remapping a digit slot to a
# named ligature, and a control-range code 1 to a glyph the bases leave as
# .notdef).
_DIFF_ENTRIES: list[tuple[int, str]] = [
    (1, "fi"),  # control range — base leaves .notdef, /Differences sets it
    (65, "Aacute"),  # 'A' slot remapped
    (66, "Bsmall"),  # consecutive run continues
    (67, "Ccircumflex"),
    (200, "bullet"),  # high code remapped
    (255, "ydieresis"),
]


def _build_diff_pdf(out_path: Path, base_encoding: str) -> None:
    """Write a minimal one-page PDF whose single Type1 font (Helvetica) has a
    dictionary /Encoding: ``/BaseEncoding <base>`` plus a ``/Differences`` array
    built from ``_DIFF_ENTRIES`` (consecutive codes coalesced under one marker).
    """
    differences = COSArray()
    prev: int | None = None
    for code, gname in _DIFF_ENTRIES:
        if prev is None or code != prev + 1:
            differences.add(COSInteger.get(code))
        differences.add(COSName.get_pdf_name(gname))
        prev = code

    enc = COSDictionary()
    enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc.set_item(COSName.get_pdf_name("BaseEncoding"), COSName.get_pdf_name(base_encoding))
    enc.set_item(COSName.get_pdf_name("Differences"), differences)

    # Minimal Standard-14 Helvetica font dict (the shape Java's
    # ``new PDType1Font(FontName.HELVETICA)`` would emit) plus our /Encoding.
    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type1"))
    font_dict.set_item(COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("Helvetica"))
    font_dict.set_item(COSName.get_pdf_name("Encoding"), enc)

    doc = PDDocument()
    try:
        from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
        from pypdfbox.pdmodel.pd_page import PDPage
        from pypdfbox.pdmodel.pd_resources import PDResources

        page = PDPage()
        doc.add_page(page)
        helv = PDType1Font(font_dict)
        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), helv)
        page.set_resources(res)
        doc.save(str(out_path))
    finally:
        doc.close()


@requires_oracle
@pytest.mark.parametrize(
    "base_encoding",
    ["StandardEncoding", "WinAnsiEncoding", "MacRomanEncoding", "MacExpertEncoding"],
)
def test_built_differences_over_base_matches_pdfbox(
    base_encoding: str, tmp_path: Path
) -> None:
    """A built PDF whose Type1 font carries ``/BaseEncoding <base>`` plus a
    custom ``/Differences`` array must resolve identically to Apache PDFBox for
    every base encoding — exercising base-selection + /Differences overlay."""
    pdf_path = tmp_path / f"diff_{base_encoding}.pdf"
    _build_diff_pdf(pdf_path, base_encoding)
    _assert_parity(f"built/{base_encoding}", pdf_path)
