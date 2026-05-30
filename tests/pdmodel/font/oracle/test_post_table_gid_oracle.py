"""Live PDFBox differential parity for the **post-table-name code→GID
fallback** of ``PDTrueTypeFont`` (PDF 32000-1 §9.6.6.4, last-resort branch).

Wave 1475. For a non-symbolic embedded simple TrueType font,
``code_to_gid(code)`` walks:

  1. ``/Encoding`` (base encoding + ``/Differences`` overlay) → a PostScript
     glyph name;
  2. the name → a Unicode scalar via the Adobe Glyph List, looked up in the
     embedded font's ``(3,1)`` Win-Unicode cmap;
  3. failing that, the name → a Mac-Roman byte looked up in the ``(1,0)``
     Mac-Roman cmap;
  4. failing *both* cmaps, the name is resolved directly in the font's
     ``post`` table via ``TrueTypeFont.name_to_gid(name)``.

Step 4 — the post-table tail — is what this test isolates. The sibling
``test_simple_ttf_map_oracle.py`` (wave 1463, non-symbolic cmap chain) and
``test_symbolic_ttf_oracle.py`` (wave 1445, symbolic raw/0xF0xx branch) cover
the cmap branches over real fixtures, but a real-world fixture rarely *needs*
the post-table last resort — the cmap almost always answers first. To exercise
it deterministically the ``PostTableGidProbe`` embeds the full, un-subset
``DejaVuSansMono.ttf`` (so its glyph order and ``post`` format-2.0 names survive
untouched) and hand-builds a font dict with a ``/Differences`` overlay naming,
at fixed byte codes, glyphs that each route through a different branch:

  * code 65 → ``u1D670`` (MATHEMATICAL MONOSPACE CAPITAL A) — a glyph name with
    **no** Adobe-Glyph-List Unicode mapping that is *not* the ``uniXXXX`` form,
    so neither cmap step nor ``name_to_gid``'s uni-name fallback fires: only the
    ``post`` name→GID map answers (the branch under test, GID 3018);
  * code 66 → ``A`` — a control resolving via the (3,1) cmap (AGL → U+0041);
  * code 67 → ``bullet`` — a second cmap control (AGL → U+2022).

The probe's ``BUILD`` mode saves the PDF (so Java and pypdfbox read byte-
identical input); its ``DUMP`` mode prints, per byte code 0..255,
``codeToGID(code)`` and ``hasGlyph(code)``. The pypdfbox side reconstructs the
same lines and asserts line-for-line equality.

Result: pypdfbox already matches Apache PDFBox 3.0.7 on the full chain
including the post-table tail; this pins the cmap→post fallback order so a
future regression — e.g. accidentally resolving ``u1D670`` to ``.notdef``
because the ``name_to_gid`` post-table lookup was dropped, or a reordering that
let a cmap step shadow the post name — fails loudly.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_TTF = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "DejaVuSansMono.ttf"
)


def _first_ttf_font(doc: PDDocument) -> PDTrueTypeFont:
    res = doc.get_pages()[0].get_resources()
    assert res is not None
    for name in res.get_font_names():
        font = res.get_font(name)
        if isinstance(font, PDTrueTypeFont):
            return font
    raise AssertionError("no PDTrueTypeFont on page 0")


def _py_lines(pdf_path: Path) -> list[str]:
    """Reconstruct ``PostTableGidProbe DUMP`` output line for line."""
    doc = PDDocument.load(pdf_path)
    try:
        font = _first_ttf_font(doc)
        lines = [f"EMBEDDED\t{'true' if font.is_embedded() else 'false'}"]
        for code in range(256):
            try:
                gid = font.code_to_gid(code)
            except Exception:  # noqa: BLE001
                gid = -1
            try:
                has = font.has_glyph(code)
            except Exception:  # noqa: BLE001
                has = False
            lines.append(
                f"ROW\t{code}\t{gid}\t{'true' if has else 'false'}"
            )
        return lines
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# value pin (no oracle needed) — the post-table fallback resolves a non-AGL,
# non-uniXXXX glyph name, while AGL names still route through the cmap.
# ---------------------------------------------------------------------------


@requires_oracle
def test_post_table_fallback_resolves_via_post_name(tmp_path: Path) -> None:
    """``u1D670`` (no AGL Unicode, not ``uniXXXX``) resolves only through the
    ``post`` table; the two AGL controls resolve through the (3,1) cmap."""
    pdf = tmp_path / "posttable.pdf"
    run_probe("PostTableGidProbe", "BUILD", str(_TTF), str(pdf))
    doc = PDDocument.load(pdf)
    try:
        font = _first_ttf_font(doc)
        assert font.is_embedded()
        # post-table-name fallback (DejaVuSansMono GID for u1D670).
        assert font.code_to_gid(65) == 3018
        assert font.has_glyph(65)
        # cmap controls.
        assert font.code_to_gid(66) == 36  # "A" -> U+0041 via (3,1) cmap
        assert font.code_to_gid(67) == 1739  # "bullet" -> U+2022 via (3,1) cmap
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# differential test against the live oracle
# ---------------------------------------------------------------------------


@requires_oracle
def test_post_table_gid_matches_pdfbox(tmp_path: Path) -> None:
    """Every ``code -> GID`` and ``hasGlyph(code)`` for codes 0..255 must
    match Apache PDFBox 3.0.7 line for line — including the post-table-name
    last-resort fallback exercised at code 65."""
    pdf = tmp_path / "posttable.pdf"
    # Java builds the canonical PDF so both engines read identical bytes.
    run_probe("PostTableGidProbe", "BUILD", str(_TTF), str(pdf))
    java = run_probe_text("PostTableGidProbe", "DUMP", str(pdf)).splitlines()
    py = _py_lines(pdf)
    assert len(java) == len(py), (
        f"line-count mismatch java={len(java)} py={len(py)}"
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, (
        "post-table code→GID parity broken:\n" + "\n".join(diffs[:40])
    )
