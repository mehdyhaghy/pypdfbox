"""Live PDFBox differential parity for the Type0 ``code -> CID -> GID`` pipeline.

Compares pypdfbox's composite-font glyph-resolution chain against Apache PDFBox
3.0.7 for every Type0 font on every page of the project's CID-font fixtures. The
chain under test is:

    code --(PDType0Font CMap)--> CID --(descendant /CIDToGIDMap)--> GID

pypdfbox delegates the embedded font program to fontTools; this test verifies the
*indices* it produces match the ones PDFBox computes. A divergence in either the
CMap (``code_to_cid``) or the ``/CIDToGIDMap`` interpretation (``cid_to_gid`` /
``code_to_gid``) shows up as a single differing line.

The oracle output is produced by ``oracle/probes/CidGidProbe.java``. The Python
side here reconstructs the identical line format. Covered codes are derived from
the descendant CIDFont's ``/W`` width array (under Identity-H — the encoding all
the project's Type0 fixtures use — the input code equals the CID, so the ``/W``
CIDs are exactly the addressable codes), plus CID 0 (``.notdef``) and two
synthetic out-of-range CIDs (60000, 65535) that exercise the embedded-program
glyph-count bound in ``codeToGID``.

Divergence history:
  * Wave 1413 found pypdfbox returned the raw CID as the GID for an Identity
    ``/CIDToGIDMap`` *without* bounding it against the embedded program's glyph
    count, while PDFBox's ``codeToGID`` returns GID 0 for ``cid >=
    numberOfGlyphs``. Fixed in ``PDCIDFontType2.cid_to_gid`` — see CHANGES.md.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSName, COSNumber
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import _BUILD, _JAR, requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures"

# Every fixture that carries at least one Type0 / CIDFontType2 font (discovered
# by loading each fixture and checking the resource font dictionaries). All use
# Identity-H + an embedded /FontFile2; the /CIDToGIDMap is either absent, the
# name /Identity, or a stream.
_FIXTURES_REL = [
    "text/input/eu-001.pdf",  # CIDFontType2, /CIDToGIDMap absent (Identity)
    "multipdf/PDFBOX-4417-001031.pdf",  # CIDFontType2, absent, 2 pages
    "multipdf/PDFBOX-4417-054080.pdf",  # CIDFontType2, absent
    "multipdf/PDFBOX-5809-509329.pdf",  # two CIDFontType2 on one page
    "pdfwriter/attachment.pdf",  # CIDFontType2, /CIDToGIDMap = name /Identity
    "pdfwriter/unencrypted.pdf",  # CIDFontType2, name /Identity, dense /W
]

# Synthetic high CIDs beyond any embedded subset font's glyph count — these
# exercise the embedded-program glyph-count bound in codeToGID (must resolve to
# GID 0 on an embedded Identity CIDFontType2). Kept in lockstep with the probe.
_OOB_CIDS = (60000, 65535)


def _covered_codes(descendant: object) -> list[int]:
    """Resolve the covered character codes from the descendant's ``/W`` array.

    Mirrors the probe's ``coveredCodes`` exactly: under Identity-H the input
    code equals the CID, so the ``/W`` CIDs are the addressable codes. CID 0
    and the synthetic out-of-range CIDs are always included.
    """
    out: set[int] = {0}
    out.update(_OOB_CIDS)
    if descendant is None:
        return sorted(out)
    w = descendant._dict.get_dictionary_object(COSName.get_pdf_name("W"))
    if not isinstance(w, COSArray):
        return sorted(out)
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


def _descendant_subtype(descendant: object) -> str:
    if descendant is None:
        return "NONE"
    if isinstance(descendant, PDCIDFontType2):
        return "CIDFontType2"
    if isinstance(descendant, PDCIDFontType0):
        return "CIDFontType0"
    return type(descendant).__name__


def _cid_to_gid_kind(descendant: object) -> str:
    if not isinstance(descendant, PDCIDFontType2):
        return "n/a"
    entry = descendant._dict.get_dictionary_object(COSName.get_pdf_name("CIDToGIDMap"))
    if entry is None:
        return "Identity(absent)"
    if isinstance(entry, COSName):
        return "name:" + entry.name
    return "stream"


def _descendant_gid(descendant: object, cid: int) -> int:
    """Resolve CID -> GID through the descendant, matching the probe.

    PDCIDFontType2 maps the CID through ``/CIDToGIDMap``; PDCIDFontType0 (CFF)
    treats CID == GID for its Identity-ordered charset.
    """
    if isinstance(descendant, PDCIDFontType2):
        return descendant.code_to_gid(cid)
    if isinstance(descendant, PDCIDFontType0):
        return cid
    return cid


def _py_cid_gid(pdf_path: Path) -> str:
    """Reconstruct the CidGidProbe output from pypdfbox, line-for-line."""
    lines: list[str] = []
    doc = PDDocument.load(pdf_path)
    try:
        for page_index, page in enumerate(doc.get_pages()):
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                try:
                    font = res.get_font(name)
                except Exception:
                    continue
                if not isinstance(font, PDType0Font):
                    continue
                key = name.name if hasattr(name, "name") else str(name)
                descendant = font.get_descendant_font()
                try:
                    embedded = font.is_embedded()
                except Exception:
                    embedded = False
                lines.append(
                    f"FONT\t{page_index}\t{key}\t{font.get_name()}\t"
                    f"{_descendant_subtype(descendant)}\t"
                    f"{_cid_to_gid_kind(descendant)}\t"
                    f"{'true' if embedded else 'false'}"
                )
                for code in _covered_codes(descendant):
                    try:
                        cid = font.code_to_cid(code)
                    except Exception:
                        lines.append(
                            f"CODE\t{page_index}\t{key}\t{code}\tCID_ERR\tCID_ERR"
                        )
                        continue
                    try:
                        gid = str(_descendant_gid(descendant, cid))
                    except Exception:
                        gid = "GID_ERR"
                    lines.append(f"CODE\t{page_index}\t{key}\t{code}\t{cid}\t{gid}")
    finally:
        doc.close()
    return "\n".join(lines) + ("\n" if lines else "")


@requires_oracle
@pytest.mark.parametrize("fixture_rel", _FIXTURES_REL)
def test_cid_gid_pipeline_matches_pdfbox(fixture_rel: str) -> None:
    """Every ``code -> CID -> GID`` triple must match Apache PDFBox exactly.

    This pins both halves of the composite-font glyph chain:

    * ``code_to_cid`` — the ``/Encoding`` CMap (Identity-H pass-through here).
    * ``cid_to_gid`` — the descendant CIDFontType2's ``/CIDToGIDMap``
      interpretation, including the embedded-program glyph-count bound that
      sends out-of-range CIDs to GID 0.

    No divergence is tolerated: the index pipeline is purely integer arithmetic
    over the CMap and the GID map, with no platform- or library-dependent
    floating point in play.
    """
    pdf_path = _FIXTURES / fixture_rel
    assert pdf_path.is_file(), f"missing fixture: {pdf_path}"
    java = run_probe_text("CidGidProbe", str(pdf_path)).splitlines()
    py = _py_cid_gid(pdf_path).splitlines()
    assert len(java) == len(py), (
        f"line-count mismatch for {fixture_rel}: java={len(java)} py={len(py)}"
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, (
        f"code->cid->gid parity broken for {fixture_rel}:\n" + "\n".join(diffs[:40])
    )


@requires_oracle
def test_at_least_one_fixture_exercises_a_type0_font() -> None:
    """Guard against the parametrised suite silently covering zero fonts.

    If a future fixture re-sync drops every Type0 font, the per-fixture tests
    would all pass with empty output. This asserts the corpus still carries the
    surface under test.
    """
    total_fonts = 0
    for rel in _FIXTURES_REL:
        out = run_probe_text("CidGidProbe", str(_FIXTURES / rel))
        total_fonts += sum(1 for ln in out.splitlines() if ln.startswith("FONT\t"))
    assert total_fonts > 0


def test_out_of_range_cid_resolves_to_gid_zero_on_embedded_identity() -> None:
    """Regression pin for the wave-1413 fix (no oracle needed).

    An embedded CIDFontType2 with an Identity ``/CIDToGIDMap`` must clamp a CID
    at or beyond its embedded program's glyph count to GID 0 — matching
    upstream ``PDCIDFontType2.codeToGID``'s ``cid < numberOfGlyphs ? cid : 0``
    guard. Before the fix pypdfbox returned the raw CID unbounded.
    """
    pdf_path = _FIXTURES / "pdfwriter/unencrypted.pdf"
    doc = PDDocument.load(pdf_path)
    try:
        checked = False
        for page in doc.get_pages():
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                font = res.get_font(name)
                if not isinstance(font, PDType0Font):
                    continue
                descendant = font.get_descendant_font()
                if not isinstance(descendant, PDCIDFontType2):
                    continue
                ttf = descendant.get_true_type_font()
                if ttf is None:
                    continue
                num_glyphs = ttf.get_number_of_glyphs()
                assert num_glyphs > 0
                # In-range CID passes through (Identity); out-of-range -> 0.
                assert descendant.cid_to_gid(1) == 1
                assert descendant.cid_to_gid(num_glyphs) == 0
                assert descendant.cid_to_gid(num_glyphs + 100) == 0
                assert descendant.cid_to_gid(65535) == 0
                checked = True
        assert checked, "no embedded CIDFontType2 found in fixture"
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Sanity: the Python reproduction helper must agree with a direct probe run so
# a future probe edit that changes the line format fails loudly here rather
# than silently skewing the parity assertion.
# ---------------------------------------------------------------------------
@requires_oracle
def test_probe_and_python_helper_share_line_shape() -> None:
    """Both engines emit the same record count for a known fixture."""
    pdf_path = _FIXTURES / "pdfwriter/unencrypted.pdf"
    java = run_probe_text("CidGidProbe", str(pdf_path)).splitlines()
    # Re-run via the low-level subprocess path to ensure the build dir/jar
    # wiring matches the harness (defensive, mirrors harness internals).
    raw = subprocess.run(
        [
            "java",
            "-cp",
            f"{_JAR}{os.pathsep}{_BUILD}",
            "CidGidProbe",
            str(pdf_path),
        ],
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")
    assert raw.splitlines() == java
    assert len(java) == len(_py_cid_gid(pdf_path).splitlines())
