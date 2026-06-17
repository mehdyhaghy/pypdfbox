"""Live PDFBox differential parity for the built-in Symbol / ZapfDingbats
encoding path on a non-embedded Standard-14 font (PDF 32000-1 §9.6.6.1,
Annex D.5 / D.6).

A Symbol or ZapfDingbats font carries NO ``/Encoding`` entry and NO
``/ToUnicode`` stream. PDFBox therefore resolves each character code through
the *font-specific built-in encoding* (``SymbolEncoding`` /
``ZapfDingbatsEncoding``) to a glyph NAME, then maps that name to Unicode via
the matching glyph list — the Adobe Glyph List for Symbol, the Zapf glyph list
for ZapfDingbats (``PDSimpleFont.getGlyphList`` / ``assignGlyphList``).

Companion to ``test_std14_metrics_oracle.py`` (wave 1431), which pins the
per-code *widths* of all 14 core fonts but never the glyph NAME or the
``toUnicode`` result. This module pins the two un-probed halves of the
Symbol/ZapfDingbats chain against the live PDFBox 3.0.7 oracle:

* ``N\t<code>\t<glyphName>`` — ``font.getEncoding().getName(code)`` over codes
  0..255: pins code -> glyph-name (the built-in encoding table). This is where
  the Symbol-specific names (``alpha``, ``universal``, ``bullet``,
  ``arrowright`` …) and the Zapf ``a1``..``a202`` names live.
* ``U\t<code>\t<U+XXXX...>`` — ``font.toUnicode(code)`` over codes 0..255:
  pins code -> glyph-name -> glyph-list -> Unicode. The Zapf path is the
  high-value one — a font bound to the AGL instead of the Zapf list would
  produce ``(none)`` for most Zapf codes, so this catches a wrong glyph-list
  selection that the width check is blind to.

Both are deterministic table lookups — no tolerance. The oracle output is
produced by ``oracle/probes/SymbolEncodingProbe.java``; the Python side
reconstructs the identical line format so any divergence isolates to a single
differing line. Decorated ``@requires_oracle`` so it skips cleanly without the
jar / JDK. Hand-authored (not ported from upstream JUnit).
"""

from __future__ import annotations

from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from tests.oracle.harness import requires_oracle, run_probe_text

# Same order the Java probe emits.
_FONT_NAMES = [PDType1Font.SYMBOL, PDType1Font.ZAPF_DINGBATS]


def _make_font(base_font: str) -> PDType1Font:
    """Construct a non-embedded Standard-14 font from its canonical name —
    mirrors the probe's *direct* ``new PDType1Font(FontName.X)`` constructor
    via :meth:`PDType1Font.standard14`. That constructor assigns the
    FontSpecific built-in ``SymbolEncoding`` / ``ZapfDingbatsEncoding``
    singletons in memory (so ``getEncoding().getClass()`` reports those
    class names, and ZapfDingbats codes 128-141 stay ``.notdef``). A
    dict-loaded core with NO /Encoding instead reads the AFM's
    ``Type1Encoding`` (wave-1491 toUnicode split), where those codes map to
    real ``a89``-``a96`` glyphs — a different construction path."""
    return PDType1Font.standard14(base_font)


def _fmt_unicode(uni: str | None) -> str:
    """Match the Java probe's per-code-point ``U+XXXX`` rendering with
    ``(none)`` for an empty/None result."""
    if not uni:
        return "(none)"
    return " ".join(f"U+{ord(ch):04X}" for ch in uni)


def _py_symbol_encoding() -> list[str]:
    """Reconstruct the SymbolEncodingProbe output from pypdfbox, line-for-line."""
    lines: list[str] = []
    for base_font in _FONT_NAMES:
        font = _make_font(base_font)
        enc = font.get_encoding_typed()
        enc_cls = "null" if enc is None else type(enc).__name__
        lines.append(f"FONT\t{font.get_name()}\t{enc_cls}")
        for code in range(256):
            name = ".notdef" if enc is None else enc.get_name(code)
            lines.append(f"N\t{code}\t{name}")
        for code in range(256):
            try:
                uni = font.to_unicode(code)
            except Exception:
                uni = None
            lines.append(f"U\t{code}\t{_fmt_unicode(uni)}")
    return lines


@requires_oracle
def test_symbol_encoding_matches_pdfbox() -> None:
    """Every built-in Symbol / ZapfDingbats code -> glyph-name and
    code -> Unicode mapping must match Apache PDFBox 3.0.7 exactly, with no
    tolerance — these are deterministic table lookups."""
    jl = run_probe_text("SymbolEncodingProbe").splitlines()
    pl = _py_symbol_encoding()
    assert len(jl) == len(pl), f"line-count mismatch: java={len(jl)} py={len(pl)}"

    current_font = "<none>"
    diffs: list[str] = []
    for i, (j, p) in enumerate(zip(jl, pl, strict=True)):
        if j.startswith("FONT\t"):
            current_font = j.split("\t")[1]
        if j != p:
            diffs.append(f"  [{current_font}] line {i}: java={j!r} py={p!r}")
    assert not diffs, (
        "Symbol/ZapfDingbats encoding parity broken:\n" + "\n".join(diffs[:60])
    )
