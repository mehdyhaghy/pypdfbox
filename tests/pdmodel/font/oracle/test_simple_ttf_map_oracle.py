"""Live PDFBox differential parity for the **non-symbolic embedded simple
TrueType** glyph-mapping surface of ``PDTrueTypeFont`` (PDF 32000-1 §9.6.6.4).

Wave 1463. A non-symbolic embedded simple TrueType font resolves a one-byte
character code to a glyph through the *encoding* — not the raw code:

  1. ``/Encoding`` (a base encoding name plus any ``/Differences`` overlay)
     maps the byte ``code`` to a PostScript glyph name;
  2. the glyph name maps to a Unicode scalar via the Adobe Glyph List, looked
     up in the embedded font's ``(3,1)`` Win-Unicode cmap;
  3. failing that, the name maps to a Mac-Roman byte looked up in the ``(1,0)``
     Mac-Roman cmap;
  4. failing that, the name is looked up directly in the font's ``post`` table
     (``nameToGID``).

This is the complement of ``test_symbolic_ttf_oracle.py`` (wave 1445), which
pins the *symbolic* branch (raw code / 0xF0xx Win-Symbol / Mac-Roman). Here we
drive three real upstream fixtures that each embed simple non-symbolic TTFs and
exercise a different base encoding:

  * ``eu-001.pdf``               — Verdana / Verdana,Bold, ``/WinAnsiEncoding``,
                                    resolved through the (3,1) Win-Unicode cmap;
  * ``PDFBOX-3110-poems-beads.pdf`` — Helvetica / Helvetica-Oblique,
                                    ``/MacRomanEncoding``, a subset shipping a
                                    (1,0) Mac-Roman cmap;
  * ``PDFA3A.pdf``               — Calibri, ``/WinAnsiEncoding``.

For every simple :class:`PDTrueTypeFont` on every page, three layers are
asserted line-for-line against Apache PDFBox 3.0.7 over byte codes 0..255:

  * ``code_to_gid(code)`` — the full encoding→name→cmap chain (pure integer
    arithmetic, zero tolerance);
  * ``get_width(code)``   — the ``/Widths`` lookup (with ``/FirstChar`` offset)
    falling back to the embedded ``hmtx`` advance, normalised to 4 d.p.;
  * ``has_glyph(code)``   — true iff ``code_to_gid`` resolves to a non-zero GID.

Result: pypdfbox already matches PDFBox on the full chain for all three
fixtures; this test pins the parity so a future regression in the non-symbolic
encoding→name→cmap order, the Mac-Roman fallback, the ``post``-table
``nameToGID`` last resort, or the dictionary-widths precedence (PDFBOX-427)
fails loudly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"

# (relative fixture path, human label) — each embeds simple non-symbolic TTFs.
_PDFS = [
    ("text/input/eu-001.pdf", "verdana_winansi"),
    ("pdfparser/linearized_PDFBOX-3110-poems-beads.pdf", "helvetica_macroman"),
    ("multipdf/PDFA3A.pdf", "calibri_winansi"),
]


def _fmt_width(value: float) -> str:
    """Match the probe's ``String.format("%.4f", v)`` formatting."""
    return f"{value:.4f}"


def _py_lines(pdf_path: Path) -> list[str]:
    """Reconstruct ``SimpleTtfMapProbe`` output line for line from pypdfbox."""
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
                except Exception:  # noqa: BLE001
                    continue
                if not isinstance(font, PDTrueTypeFont):
                    continue
                # Mirror the probe: only embedded simple TrueType fonts are a
                # deterministic differential target — a non-embedded font is
                # resolved through an environment-dependent substitute.
                if not font.is_embedded():
                    continue
                key = name.name if hasattr(name, "name") else str(name)
                descriptor = font.get_font_descriptor()
                symbolic = bool(descriptor.is_symbolic()) if descriptor else False
                lines.append(
                    f"FONT\t{page_index}\t{key}\t{font.get_name()}\t"
                    f"{'true' if symbolic else 'false'}\t"
                    f"{'true' if font.is_embedded() else 'false'}"
                )
                for code in range(256):
                    try:
                        gid = font.code_to_gid(code)
                    except Exception:  # noqa: BLE001
                        gid = -1
                    try:
                        width = _fmt_width(font.get_width(code))
                    except Exception:  # noqa: BLE001
                        width = "ERR"
                    try:
                        has = font.has_glyph(code)
                    except Exception:  # noqa: BLE001
                        has = False
                    lines.append(
                        f"ROW\t{code}\t{gid}\t{width}\t"
                        f"{'true' if has else 'false'}"
                    )
    finally:
        doc.close()
    return lines


# ---------------------------------------------------------------------------
# fixture proof (no oracle needed) — guard against a fixture that stops
# exercising the non-symbolic chain.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("rel", "label"), _PDFS, ids=[p[1] for p in _PDFS])
def test_fixture_has_nonsymbolic_embedded_ttf(rel: str, label: str) -> None:
    """Each fixture must carry at least one non-symbolic embedded simple TTF
    with an ``/Encoding``, or the chain under test would not be exercised."""
    pdf = _FIXTURES / rel
    assert pdf.is_file(), f"missing fixture {pdf}"
    doc = PDDocument.load(pdf)
    try:
        found = False
        for page in doc.get_pages():
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                try:
                    font = res.get_font(name)
                except Exception:  # noqa: BLE001
                    continue
                if not isinstance(font, PDTrueTypeFont):
                    continue
                descriptor = font.get_font_descriptor()
                if (
                    descriptor is not None
                    and not descriptor.is_symbolic()
                    and descriptor.get_font_file2() is not None
                ):
                    found = True
        assert found, f"{label}: no non-symbolic embedded simple TTF in fixture"
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# differential test against the live oracle
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(("rel", "label"), _PDFS, ids=[p[1] for p in _PDFS])
def test_simple_ttf_map_matches_pdfbox(rel: str, label: str) -> None:
    """Every ``code -> GID``, ``getWidth(code)`` and ``hasGlyph(code)`` for
    codes 0..255 on every simple TrueType font must match Apache PDFBox 3.0.7
    line for line — the full non-symbolic encoding→name→cmap chain plus the
    dictionary-width precedence and the GID-based ``hasGlyph``.
    """
    pdf = _FIXTURES / rel
    java = run_probe_text("SimpleTtfMapProbe", str(pdf)).splitlines()
    py = _py_lines(pdf)
    assert len(java) == len(py), (
        f"{label}: line-count mismatch java={len(java)} py={len(py)}"
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, (
        f"simple-TTF map parity broken for {label}:\n" + "\n".join(diffs[:40])
    )
