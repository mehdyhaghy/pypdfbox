"""Live PDFBox differential parity for the SYNTHESISED Standard-14 descriptor.

A Standard-14 font built straight from its name (``new PDType1Font(
FontName.HELVETICA)``) carries only ``/BaseFont`` — no ``/FontDescriptor``.
``getFontDescriptor()`` then returns a descriptor PDFBox *synthesises* from the
bundled AFM via ``PDType1FontEmbedder.buildFontDescriptor(FontMetrics)``.

Wave 1431 (``test_std14_metrics_oracle.py``) already pinned the synthesised
descriptor's *metric* block — ascent / descent / cap-height / x-height / italic
angle + the font bounding box. This wave (1472) covers the remaining
**identity + classification** block of that same synthesised descriptor, which
no oracle test asserted before:

  * ``getFontName`` — the descriptor's font name (from the AFM).
  * ``getFlags`` — the *computed* flag integer. The synthesiser sets ONLY
    symbolic / non-symbolic (Latin faces -> 32 ``FLAG_NON_SYMBOLIC``; Symbol /
    ZapfDingbats -> 4 ``FLAG_SYMBOLIC``). Crucially it does NOT derive serif
    (Times), fixed-pitch (Courier) or italic (oblique faces) bits — pinning
    that the classification is encoding-scheme-driven, not name-derived.
  * ``getFontFamily`` — AFM ``FamilyName`` (e.g. "Times", not "Times-Bold").
  * ``getCharSet`` — AFM ``CharacterSet`` ("ExtendedRoman" / "Special").
  * ``getStemV`` / ``getFontWeight`` / ``getMissingWidth`` — all 0 (the
    synthesiser hard-codes ``setStemV(0)`` "for PDF/A" and never sets weight or
    missing width).

The oracle output comes from ``oracle/probes/Std14SyntheticDescriptorProbe.java``;
the Python side reconstructs the identical line format so a divergence is one
differing line.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from tests.oracle.harness import requires_oracle, run_probe_text

# Same faces, in the same order, as the Java probe's NAMES array.
_FONT_NAMES = [
    PDType1Font.HELVETICA,
    PDType1Font.HELVETICA_BOLD,
    PDType1Font.HELVETICA_OBLIQUE,
    PDType1Font.TIMES_ROMAN,
    PDType1Font.TIMES_BOLD,
    PDType1Font.TIMES_ITALIC,
    PDType1Font.TIMES_BOLD_ITALIC,
    PDType1Font.COURIER,
    PDType1Font.COURIER_BOLD,
    PDType1Font.SYMBOL,
    PDType1Font.ZAPF_DINGBATS,
]


def _fmt(v: float) -> str:
    """Match the Java probe's ``String.format("%.4f", ...)`` with -0.0 collapse."""
    if v == 0.0:
        v = 0.0
    return f"{v:.4f}"


def _nz(s: str | None) -> str:
    """Match the probe's null-as-literal-"null" rendering for string entries."""
    return "null" if s is None else s


def _bool(b: bool) -> str:
    """Match Java ``%b`` formatting (lowercase ``true`` / ``false``)."""
    return "true" if b else "false"


def _make_font(base_font: str) -> PDType1Font:
    """Construct a non-embedded Standard-14 font from its canonical name —
    mirrors the probe's ``new PDType1Font(FontName.X)``."""
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), base_font)
    return PDType1Font(font_dict)


def _py_synthetic_descriptors() -> list[str]:
    """Reconstruct the Std14SyntheticDescriptorProbe output, line-for-line."""
    lines: list[str] = []
    for base_font in _FONT_NAMES:
        font = _make_font(base_font)
        fd = font.get_font_descriptor()
        lines.append(f"FONT\t{font.get_name()}")
        if fd is None:
            lines.append("NO_DESCRIPTOR")
            continue
        lines.append(
            f"ID\t{_nz(fd.get_font_name())}\t{fd.get_flags()}\t"
            f"{_nz(fd.get_font_family())}\t{_nz(fd.get_char_set())}"
        )
        lines.append(
            f"NUM\t{_fmt(fd.get_stem_v())}\t{_fmt(fd.get_font_weight())}\t"
            f"{_fmt(fd.get_missing_width())}"
        )
        lines.append(
            f"CLS\t{_bool(fd.is_symbolic())}\t{_bool(fd.is_non_symbolic())}\t"
            f"{_bool(fd.is_fixed_pitch())}\t{_bool(fd.is_serif())}\t"
            f"{_bool(fd.is_italic())}\t{_bool(fd.is_force_bold())}"
        )
    return lines


@requires_oracle
def test_std14_synthetic_descriptor_matches_pdfbox() -> None:
    """The synthesised Standard-14 descriptor's identity + classification block
    (font name, computed flags, family, char-set, stem-v, weight,
    missing-width) must match Apache PDFBox 3.0.7 exactly for every face."""
    jl = run_probe_text("Std14SyntheticDescriptorProbe").splitlines()
    pl = _py_synthetic_descriptors()
    assert len(jl) == len(pl), f"line-count mismatch: java={len(jl)} py={len(pl)}"

    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(jl, pl, strict=True))
        if j != p
    ]
    assert not diffs, (
        "synthesised Standard-14 descriptor parity broken:\n" + "\n".join(diffs[:40])
    )
