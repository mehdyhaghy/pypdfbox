"""Live PDFBox differential parity for FontMapper substitution decisions.

Pins the host-*independent* (deterministic) facets of
``org.apache.pdfbox.pdmodel.font.FontMapperImpl`` against Apache PDFBox 3.0.7:

1. ``getFallbackFontName(PDFontDescriptor)`` — the flag- and name-driven
   Standard-14 family + style selection (fixed-pitch -> Courier, serif ->
   Times, else Helvetica; ``-Bold`` / ``-Oblique`` / ``-Italic`` suffixing
   from the italic flag and the bold-name heuristic). This depends only on
   descriptor bits and the font name string, never on which fonts are
   installed, so it is fully deterministic.

2. ``getSubstitutes(String)`` — the constructor-built substitute table,
   *including the Standard14Fonts alias expansion* (Acrobat names such as
   ``Arial`` / ``ArialMT`` / ``TimesNewRoman`` / ``CourierNew`` resolve to the
   canonical font's substitute list). The returned list is the static
   constructor table — independent of host font availability.

Both surfaces are read through ``oracle/probes/FontSubstituteProbe.java`` via
reflection on the package-private ``FontMapperImpl``. The chosen *substitute
binary* depends on the host system, so we deliberately assert only on these
stable PostScript-name facets, never on glyph outlines.

Wave 1461 root-caused a divergence here: pypdfbox's ``FontMapperImpl``
constructor never ran the upstream Acrobat-alias expansion loop, so
``getSubstitutes("Arial")`` returned an empty list where PDFBox returns
Helvetica's substitutes. Fixed by mirroring the constructor loop.
"""

from __future__ import annotations

from pypdfbox.pdmodel.font.font_mapper_impl import FontMapperImpl
from tests.oracle.harness import requires_oracle, run_probe_text

# Descriptor flag bits (mirror PDFontDescriptor's private constants).
_FLAG_FIXED_PITCH = 1
_FLAG_SERIF = 2
_FLAG_ITALIC = 64


def _py_fallback_name(flags: int, font_name: str | None) -> str:
    """Reproduce FontMapperImpl.getFallbackFontName via a stub descriptor.

    Mirrors the probe's reflective call without constructing a real
    COSDictionary-backed descriptor; the production method consults only
    ``is_fixed_pitch`` / ``is_serif`` / ``is_italic`` / ``get_font_name``.
    """

    class _Desc:
        def is_fixed_pitch(self) -> bool:
            return bool(flags & _FLAG_FIXED_PITCH)

        def is_serif(self) -> bool:
            return bool(flags & _FLAG_SERIF)

        def is_italic(self) -> bool:
            return bool(flags & _FLAG_ITALIC)

        def get_font_name(self) -> str | None:
            return font_name

    return FontMapperImpl.get_fallback_font_name(_Desc())


def _py_probe_output() -> str:
    """Reconstruct FontSubstituteProbe's stdout from pypdfbox.

    Mirrors the probe's control flow line-for-line so a textual diff isolates
    a single divergence.
    """
    lines: list[str] = []
    # ---- surface 1: getFallbackFontName matrix ----
    lines.append(f"FALLBACK\tNULL\t{FontMapperImpl.get_fallback_font_name(None)}")
    names = [None, "FooRegular", "FooBold", "FooBlack", "FooHeavy"]
    for fp in (0, 1):
        for sf in (0, 1):
            for it in (0, 1):
                for nm in names:
                    flags = 0
                    if fp == 1:
                        flags |= _FLAG_FIXED_PITCH
                    if sf == 1:
                        flags |= _FLAG_SERIF
                    if it == 1:
                        flags |= _FLAG_ITALIC
                    label = f"fp{fp}_sf{sf}_it{it}_n{'null' if nm is None else nm}"
                    lines.append(f"FALLBACK\t{label}\t{_py_fallback_name(flags, nm)}")

    # ---- surface 2: getSubstitutes table ----
    mapper = FontMapperImpl()
    queries = [
        "Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique",
        "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
        "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic",
        "Symbol", "ZapfDingbats",
        "Arial", "ArialMT", "Arial-Bold", "Arial-BoldMT", "Arial-Italic",
        "Arial-ItalicMT", "Arial-BoldItalic", "Arial-BoldItalicMT",
        "CourierNew", "CourierNewPSMT", "CourierNew-Bold", "CourierNewPS-BoldMT",
        "TimesNewRoman", "TimesNewRomanPSMT", "TimesNewRoman-Bold",
        "TimesNewRomanPS-BoldMT", "TimesNewRomanPS-Italic",
        "arial", "Arial ", "TIMESNEWROMAN",
        "NoSuchFont-XYZ",
    ]
    for q in queries:
        subs = ",".join(mapper.get_substitutes(q))
        lines.append(f"SUBST\t{q}\t{subs}")
    return "\n".join(lines) + "\n"


@requires_oracle
def test_font_substitution_decisions_match_pdfbox() -> None:
    """FontMapperImpl fallback-name + substitute-table decisions must match
    Apache PDFBox exactly (host-independent facets).
    """
    jl = run_probe_text("FontSubstituteProbe").splitlines()
    pl = _py_probe_output().splitlines()
    assert len(jl) == len(pl), f"line-count mismatch: java={len(jl)} py={len(pl)}"
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(jl, pl, strict=True))
        if j != p
    ]
    assert not diffs, "font substitution parity broken:\n" + "\n".join(diffs[:40])
