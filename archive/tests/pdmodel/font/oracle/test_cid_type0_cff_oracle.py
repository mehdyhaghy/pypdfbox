"""Live PDFBox differential parity for ``PDCIDFontType0`` (CFF CID-keyed).

Pins the CIDFontType0 surface for a composite font whose descendant is a
``PDCIDFontType0`` backed by an embedded CID-keyed CFF program
(``/FontFile3 /Subtype /CIDFontType0C``). Drives the four glyph-level surfaces
Apache PDFBox exposes off the descendant:

* ``getFontMatrix()`` — the CFF Top DICT FontMatrix (default ``[0.001 0 0
  0.001 0 0]``).
* ``codeToGID(code)`` — ``cid = codeToCID(code); cidFont.getCharset()
  .getGIDForCID(cid)`` (verified against the 3.0.7 bytecode).
* ``getWidthFromFont(code)`` — the CID's Type 2 charstring advance transformed
  through the font matrix into 1/1000 em (no ``hasGlyph`` gate; ``.notdef``
  and unmapped CIDs resolve to GID 0's ``defaultWidthX``).
* ``hasGlyph(code)`` — ``getType2CharString(codeToCID(code)).getGID() != 0``.

This is a different surface from the adjacent oracle tests:

* ``test_cid_width_oracle`` drives ``PDCIDFont.getWidth`` (``/W``/``/DW``).
* ``test_cid_gid_oracle`` drives the ``code -> CID -> GID`` pipeline for the
  CIDFontType2 (TrueType) fixtures.

Here the embedded program is a CID-keyed CFF, so GID and width come from the
CFF charset + Type 2 charstrings rather than a TrueType ``glyf`` table.

The oracle output is produced by ``oracle/probes/CidType0CffProbe.java``; the
Python side reconstructs the identical line format. GID and ``hasGlyph`` are
integer/boolean lookups (no platform-dependent float) and must match exactly.
The ``getWidthFromFont`` value is compared within a small tolerance: upstream
computes it via a 32-bit ``AffineTransform`` (``width * fontMatrix[0] * 1000``
in Java ``float``), which rounds e.g. an 802-unit advance to ``802.0001`` —
a precision artifact of Java single-precision math, not a metric difference.

Divergence history:
  * Wave 1462 found pypdfbox's ``PDCIDFontType0.get_type2_char_string``
    pre-resolved the CID to a GID and then passed that GID into
    ``CFFCIDFont.get_type2_char_string`` — which does its own CID→GID
    resolution — so a *second* CID→GID lookup corrupted the wrapper's GID.
    ``hasGlyph`` therefore returned ``False`` for every real glyph. Fixed by
    passing the CID straight through (matching upstream
    ``cidFont.getType2CharString(cid)``). See CHANGES.md.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSArray, COSName, COSNumber
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures"

# The one project fixture carrying composite fonts whose descendant is a
# CIDFontType0 with an embedded CID-keyed CFF (/FontFile3 /CIDFontType0C):
# two such fonts (GoudySans-Medium, ACaslonPro-Regular) on one page.
_FIXTURE_REL = "pdmodel/font/PDFBOX-3062-005717-p1.pdf"

# Synthetic CIDs beyond the embedded subset font's glyph count — exercise the
# out-of-range path (codeToGID -> GID 0, hasGlyph false, width = .notdef
# defaultWidthX). Kept in lockstep with the probe.
_OOB_CIDS = (60000, 65535)

# Tolerance absorbing the Java 32-bit-float font-matrix transform artifact in
# getWidthFromFont (e.g. 802.0 vs 802.0001).
_WIDTH_TOL = 0.01


def _covered_codes(descendant: PDCIDFontType0) -> list[int]:
    """Resolve probed CIDs from the descendant's ``/W`` array, mirroring the
    probe's ``coveredCodes``: under Identity encoding code == CID, so the
    ``/W`` CIDs are the addressable codes. CID 0 and two out-of-range CIDs are
    always included.
    """
    out: set[int] = {0}
    out.update(_OOB_CIDS)
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


def _parse_oracle(text: str) -> tuple[dict[str, dict], dict[str, dict]]:
    """Split probe output into ``{fontKey: font_record}`` and
    ``{fontKey: {code: glyph_record}}`` maps keyed on the per-page font key.
    """
    fonts: dict[str, dict] = {}
    glyphs: dict[str, dict] = {}
    for ln in text.splitlines():
        parts = ln.split("\t")
        if parts[0] == "FONT":
            _, page, key, base, embedded, damaged, *m = parts
            fkey = f"{page}\t{key}"
            fonts[fkey] = {
                "base": base,
                "embedded": embedded,
                "damaged": damaged,
                "matrix": tuple(float(x) for x in m),
            }
            glyphs.setdefault(fkey, {})
        elif parts[0] == "GLYPH":
            _, page, key, code, cid, gid, width, has_glyph = parts
            fkey = f"{page}\t{key}"
            glyphs.setdefault(fkey, {})[int(code)] = {
                "cid": cid,
                "gid": gid,
                "width": width,
                "has_glyph": has_glyph,
            }
    return fonts, glyphs


def _py_records(
    pdf_path: Path,
) -> tuple[dict[str, dict], dict[str, dict]]:
    """Reconstruct the probe's FONT + GLYPH records from pypdfbox."""
    fonts: dict[str, dict] = {}
    glyphs: dict[str, dict] = {}
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
                descendant = font.get_descendant_font()
                if not isinstance(descendant, PDCIDFontType0):
                    continue
                key = name.name if hasattr(name, "name") else str(name)
                fkey = f"{page_index}\t{key}"
                fonts[fkey] = {
                    "base": str(font.get_name()),
                    "embedded": "true" if descendant.is_embedded() else "false",
                    "damaged": "true" if descendant.is_damaged() else "false",
                    "matrix": tuple(
                        float(x) for x in descendant.get_font_matrix()
                    ),
                }
                glyphs[fkey] = {}
                for code in _covered_codes(descendant):
                    cid = font.code_to_cid(code)
                    glyphs[fkey][code] = {
                        "cid": str(cid),
                        "gid": str(descendant.code_to_gid(code)),
                        "width": f"{descendant.get_width_from_font(cid):.4f}",
                        "has_glyph": "true" if descendant.has_glyph(code) else "false",
                    }
    finally:
        doc.close()
    return fonts, glyphs


@requires_oracle
def test_cid_type0_cff_surfaces_match_pdfbox() -> None:
    """Every CIDFontType0 glyph surface must match Apache PDFBox.

    Pins, per probed code: ``codeToCID``, ``codeToGID``, ``hasGlyph``
    (all exact), ``getWidthFromFont`` (within a 32-bit-float tolerance), and
    per-font ``getFontMatrix`` / ``isEmbedded`` / ``isDamaged``.
    """
    pdf_path = _FIXTURES / _FIXTURE_REL
    assert pdf_path.is_file(), f"missing fixture: {pdf_path}"
    java_fonts, java_glyphs = _parse_oracle(
        run_probe_text("CidType0CffProbe", str(pdf_path))
    )
    py_fonts, py_glyphs = _py_records(pdf_path)

    assert set(java_fonts) == set(py_fonts), (
        f"font set mismatch: java={set(java_fonts)} py={set(py_fonts)}"
    )
    assert java_fonts, "fixture exercised no CIDFontType0 font"

    diffs: list[str] = []
    for fkey, jf in java_fonts.items():
        pf = py_fonts[fkey]
        for attr in ("base", "embedded", "damaged"):
            if jf[attr] != pf[attr]:
                diffs.append(f"{fkey} FONT.{attr}: java={jf[attr]!r} py={pf[attr]!r}")
        for i, (jm, pm) in enumerate(zip(jf["matrix"], pf["matrix"], strict=True)):
            if abs(jm - pm) > 1e-6:
                diffs.append(f"{fkey} FONT.matrix[{i}]: java={jm} py={pm}")

        jg = java_glyphs[fkey]
        pg = py_glyphs[fkey]
        assert set(jg) == set(pg), (
            f"{fkey}: code set mismatch java={sorted(jg)} py={sorted(pg)}"
        )
        for code in sorted(jg):
            jr = jg[code]
            pr = pg[code]
            for attr in ("cid", "gid", "has_glyph"):
                if jr[attr] != pr[attr]:
                    diffs.append(
                        f"{fkey} code={code} {attr}: "
                        f"java={jr[attr]!r} py={pr[attr]!r}"
                    )
            if jr["width"] != "ERR" and pr["width"] != "ERR":
                if abs(float(jr["width"]) - float(pr["width"])) > _WIDTH_TOL:
                    diffs.append(
                        f"{fkey} code={code} width: "
                        f"java={jr['width']} py={pr['width']}"
                    )
            elif jr["width"] != pr["width"]:
                diffs.append(
                    f"{fkey} code={code} width: "
                    f"java={jr['width']!r} py={pr['width']!r}"
                )

    assert not diffs, "CIDFontType0 (CFF) parity broken:\n" + "\n".join(diffs[:40])


def test_has_glyph_resolves_real_cff_glyph(  # no oracle needed
) -> None:
    """Regression pin for the wave-1462 double-CID→GID-resolution fix.

    ``PDCIDFontType0.has_glyph`` must report ``True`` for a code whose CID
    maps to a non-``.notdef`` GID in the embedded CID-keyed CFF, and the
    Type 2 charstring wrapper must carry the correct GID. Before the fix the
    PD layer pre-resolved the CID to a GID and then passed that GID into
    ``CFFCIDFont.get_type2_char_string`` (which re-resolves CID→GID), so the
    wrapper's GID collapsed to 0 and ``has_glyph`` was always ``False``.
    """
    pdf_path = _FIXTURES / _FIXTURE_REL
    doc = PDDocument.load(pdf_path)
    try:
        checked = 0
        for page in doc.get_pages():
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                font = res.get_font(name)
                if not isinstance(font, PDType0Font):
                    continue
                descendant = font.get_descendant_font()
                if not isinstance(descendant, PDCIDFontType0):
                    continue
                # CID 0 (.notdef) -> GID 0 -> hasGlyph False.
                assert descendant.has_glyph(0) is False
                cs0 = descendant.get_type2_char_string(0)
                assert cs0.get_gid() == 0
                # First /W-covered non-zero CID must resolve to a non-zero GID.
                for code in _covered_codes(descendant):
                    if code == 0 or code in _OOB_CIDS:
                        continue
                    cid = font.code_to_cid(code)
                    gid = descendant.code_to_gid(code)
                    cs = descendant.get_type2_char_string(cid)
                    if gid != 0:
                        assert cs.get_gid() == gid
                        assert descendant.has_glyph(code) is True
                        checked += 1
                        break
        assert checked > 0, "no real CIDFontType0 glyph exercised"
    finally:
        doc.close()
