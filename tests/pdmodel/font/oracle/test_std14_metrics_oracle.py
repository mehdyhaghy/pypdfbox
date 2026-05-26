"""Live PDFBox differential parity for the Standard-14 AFM (non-embedded) path.

This wave (1431) covers the **direct** Standard-14 font path: the 14 core
PostScript fonts constructed straight from their ``/BaseFont`` name with no PDF,
no ``/Widths`` array, and no embedded program — every metric comes from the
bundled Adobe Core 14 AFM files. PDFBox ships those same AFMs, so the numbers
must match exactly.

Companion to:
  * ``test_font_metrics_oracle.py`` (wave 1408) — per-code widths over the
    fonts *embedded in PDFs* (the ``/Widths`` / embedded-program path).
  * ``test_font_descriptor_oracle.py`` (wave 1412) — descriptor block over
    PDF-resident fonts.

The oracle is produced by ``oracle/probes/Std14MetricsProbe.java``, which builds
each of the 14 fonts via ``new PDType1Font(Standard14Fonts.FontName.X)`` and
emits, per font: per-code advance widths (codes 32..255 via ``getWidth(code)``),
``getStringWidth`` over a battery of representative strings, the font bounding
box, and the descriptor's ascent/descent/capHeight/xHeight/italicAngle. The
Python side reconstructs the identical line format so a divergence shows up as a
single differing line.

Parity rules (Standard-14 metrics are deterministic AFM-table lookups — no
tolerance):
  * Per-code ``getWidth(code)`` — EXACT, every code, every font. This is the
    high-value check: it pins the code -> glyph-name -> AFM-width path,
    including the WinAnsi default encoding for the Latin fonts and the
    font-specific Symbol / ZapfDingbats encodings.
  * Font bounding box, ascent, descent, cap height, x-height, italic angle —
    EXACT.
  * ``getStringWidth`` — EXACT wherever Java produces a number. The single
    tolerated divergence is the documented encode-leniency contract: PDFBox
    raises ``IllegalArgumentException`` (probe emits ``ERR``) on an unencodable
    glyph (e.g. a Greek string under Helvetica's WinAnsi encoding, or Latin
    letters under Symbol/ZapfDingbats), while pypdfbox's lenient ``encode``
    substitutes and returns a number. This whole-string encode contract is a
    cross-module decision out of scope here (see CHANGES.md / the
    ``test_font_metrics_oracle.py`` rationale); the test asserts pypdfbox is
    *never stricter* than Java and *never numerically different* when both
    succeed.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from tests.oracle.harness import requires_oracle, run_probe_text

# All 14 standard fonts, in the same order the Java probe emits them.
_FONT_NAMES = [
    PDType1Font.HELVETICA,
    PDType1Font.HELVETICA_BOLD,
    PDType1Font.HELVETICA_OBLIQUE,
    PDType1Font.HELVETICA_BOLD_OBLIQUE,
    PDType1Font.TIMES_ROMAN,
    PDType1Font.TIMES_BOLD,
    PDType1Font.TIMES_ITALIC,
    PDType1Font.TIMES_BOLD_ITALIC,
    PDType1Font.COURIER,
    PDType1Font.COURIER_BOLD,
    PDType1Font.COURIER_OBLIQUE,
    PDType1Font.COURIER_BOLD_OBLIQUE,
    PDType1Font.SYMBOL,
    PDType1Font.ZAPF_DINGBATS,
]

# Representative strings — must match the probe's SAMPLES/SAMPLE_IDS arrays.
_SAMPLE_IDS = ["space", "ABC", "Hello", "digits", "mixed", "punct", "latin1", "symbol"]
_SAMPLES = [
    " ",
    "ABC",
    "Hello, World!",
    "0123456789",
    "The quick brown fox jumps over 12 lazy dogs.",
    "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~",
    "éèüñç",  # éèüñç (latin-1 accented)
    "ΑΒΓ•♦",  # ΑΒΓ•♦ (greek + bullet + diamond)
]


def _fmt(v: float) -> str:
    """Match the Java probe's ``String.format("%.4f", ...)`` with -0.0 collapse."""
    if v == 0.0:
        v = 0.0
    return f"{v:.4f}"


def _make_font(base_font: str) -> PDType1Font:
    """Construct a non-embedded Standard-14 font from its canonical name —
    mirrors the probe's ``new PDType1Font(FontName.X)``."""
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), base_font)
    return PDType1Font(font_dict)


def _py_std14_metrics() -> list[str]:
    """Reconstruct the Std14MetricsProbe output from pypdfbox, line-for-line."""
    lines: list[str] = []
    for base_font in _FONT_NAMES:
        font = _make_font(base_font)
        lines.append(f"FONT\t{font.get_name()}")
        for code in range(32, 256):
            try:
                w = _fmt(font.get_width(code))
            except Exception:
                w = "ERR"
            lines.append(f"W\t{code}\t{w}")
        for sid, sample in zip(_SAMPLE_IDS, _SAMPLES, strict=True):
            try:
                sw = _fmt(font.get_string_width(sample))
            except Exception:
                sw = "ERR"
            lines.append(f"SW\t{sid}\t{sw}")
        bbox = font.get_bounding_box()
        if bbox is None:
            lines.append("BBOX\tNULL")
        else:
            lines.append(
                f"BBOX\t{_fmt(bbox.get_lower_left_x())}\t{_fmt(bbox.get_lower_left_y())}\t"
                f"{_fmt(bbox.get_upper_right_x())}\t{_fmt(bbox.get_upper_right_y())}"
            )
        fd = font.get_font_descriptor()
        if fd is None:
            lines.append("DESC\tNULL")
        else:
            lines.append(
                f"DESC\t{_fmt(fd.get_ascent())}\t{_fmt(fd.get_descent())}\t"
                f"{_fmt(fd.get_cap_height())}\t{_fmt(fd.get_x_height())}\t"
                f"{_fmt(fd.get_italic_angle())}"
            )
    return lines


@requires_oracle
def test_std14_metrics_match_pdfbox() -> None:
    """Every Standard-14 metric must match Apache PDFBox 3.0.7 exactly.

    Per-code ``getWidth``, the font bounding box, and every descriptor
    metric are asserted line-for-line. ``getStringWidth`` is asserted
    exactly except for the documented ``java=ERR vs py=<number>``
    encode-leniency boundary.
    """
    jl = run_probe_text("Std14MetricsProbe").splitlines()
    pl = _py_std14_metrics()
    assert len(jl) == len(pl), f"line-count mismatch: java={len(jl)} py={len(pl)}"

    current_font = "<none>"
    hard_diffs: list[str] = []
    lenient_skips = 0
    for i, (j, p) in enumerate(zip(jl, pl, strict=True)):
        if j.startswith("FONT\t"):
            current_font = j.split("\t", 1)[1]
        if j == p:
            continue
        jf = j.split("\t")
        pf = p.split("\t")
        kind = jf[0]
        # FONT header, per-code W, BBOX and DESC must be exact.
        if kind in ("FONT", "W", "BBOX", "DESC"):
            hard_diffs.append(f"  [{current_font}] line {i}: java={j!r} py={p!r}")
            continue
        # SW: tolerate ONLY java=ERR (PDFBox threw on an unencodable glyph)
        # vs py=<number> (pypdfbox's lenient encode). Any other shape — a
        # both-numeric mismatch, or pypdfbox being *stricter* (py=ERR while
        # java succeeded) — is a hard failure.
        if kind == "SW":
            jv, pv = jf[2], pf[2]
            if jv == "ERR" and pv != "ERR":
                lenient_skips += 1
                continue
            hard_diffs.append(f"  [{current_font}] line {i}: java={j!r} py={p!r}")
            continue
        hard_diffs.append(f"  [{current_font}] line {i}: java={j!r} py={p!r}")

    assert not hard_diffs, (
        f"Standard-14 metric parity broken "
        f"(tolerated encode-leniency skips: {lenient_skips}):\n"
        + "\n".join(hard_diffs[:60])
    )


@requires_oracle
@pytest.mark.parametrize("base_font", _FONT_NAMES)
def test_std14_per_code_widths_exact(base_font: str) -> None:
    """Focused per-font assertion: every ``getWidth(code)`` for codes
    32..255 is exactly equal to PDFBox's, with no tolerance. Isolates a
    single font so a regression points straight at the offending family /
    encoding table."""
    # Build the per-font expected map from the probe output once.
    jl = run_probe_text("Std14MetricsProbe").splitlines()
    expected: dict[int, str] = {}
    in_font = False
    for line in jl:
        if line.startswith("FONT\t"):
            in_font = line.split("\t", 1)[1] == base_font
            continue
        if in_font and line.startswith("W\t"):
            _, code_s, w = line.split("\t")
            expected[int(code_s)] = w
    assert expected, f"probe produced no W rows for {base_font}"

    font = _make_font(base_font)
    diffs: list[str] = []
    for code in range(32, 256):
        try:
            py_w = _fmt(font.get_width(code))
        except Exception:
            py_w = "ERR"
        if py_w != expected[code]:
            diffs.append(f"  code {code}: java={expected[code]} py={py_w}")
    assert not diffs, f"width divergence for {base_font}:\n" + "\n".join(diffs[:40])
