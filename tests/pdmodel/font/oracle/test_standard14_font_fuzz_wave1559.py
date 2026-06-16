"""Live PDFBox differential fuzz for the STATIC ``Standard14Fonts`` surface.

Wave 1559 (agent C). Targets facets of the Standard-14 machinery that the
existing Std14 oracle probes never pinned:

  * ``Std14MetricsProbe`` / ``Std14SyntheticDescriptorProbe`` drive a
    constructed ``PDType1Font`` and pin per-CODE widths + the synthesised
    descriptor — never the static name-mapping API.
  * ``FontSubstituteProbe`` pins the ``FontMapperImpl`` substitute *table*,
    not ``Standard14Fonts.getMappedFontName / containsName / getNames / getAFM``.

This wave fuzzes the static API directly against the live oracle
(``oracle/probes/Standard14FontFuzzProbe.java``):

  MAP   — getMappedFontName + containsName across canonical names, the
          Acrobat aliases (Arial / ArialMT / CourierNew / TimesNewRoman /
          ``-PS`` / ``-MT`` branches), case-folded inputs and unknowns.
  NAMES — getNames() cardinality.
  GW    — per-glyph AFM advance widths via getAFM(...).getCharacterWidth,
          including Symbol (alpha, summation) and ZapfDingbats (a1, a10).
  AFM   — getAFM presence for canonical / alias / unknown names.

TWO documented, deliberate pypdfbox divergences from upstream are pinned
BOTH-SIDES with honest comments (NOT silently normalised away):

  1. **Case-insensitive lookup.** Upstream ``Standard14Fonts`` lookups are
     case-SENSITIVE — ``getMappedFontName("helvetica") == null``. pypdfbox
     folds case (a documented extension; hand-written tests
     ``test_get_mapped_font_name_lookup_is_case_insensitive`` etc. assert it).

  2. **Extended alias set.** Upstream ships 24 aliases (38 names total).
     pypdfbox ships an extended set (59 names total) adding ``-PS`` / ``-MT``
     / ``-Bold`` / ``-Oblique`` Acrobat variants Acrobat itself accepts.

Both divergences are CONSERVATIVE: wherever BOTH sides resolve a name they
resolve it to the *same* canonical font, and wherever pypdfbox returns null
the oracle also returns null. The test asserts exactly that superset
property rather than masking the divergence.

The GW and AFM surfaces (the AFM-backed numerics) match the oracle
byte-for-byte — including the wave-1559 fix making ``get_afm`` return ``None``
(not raise) for an unmapped name, mirroring upstream ``getAFM``'s null return.
"""

from __future__ import annotations

from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
from tests.oracle.harness import requires_oracle, run_probe_text

# Same MAP_QUERIES, in the same order, as the Java probe.
_MAP_QUERIES = [
    # canonical
    "Helvetica", "Helvetica-Bold", "Times-Roman", "Times-BoldItalic",
    "Courier", "Courier-BoldOblique", "Symbol", "ZapfDingbats",
    # Arial branch
    "Arial", "ArialMT", "Arial-Bold", "Arial-BoldMT", "Arial-Italic",
    "Arial-BoldItalicMT",
    # TimesNewRoman branch
    "TimesNewRoman", "TimesNewRomanPSMT", "TimesNewRoman-Bold",
    "TimesNewRomanPS-BoldMT", "TimesNewRomanPS-ItalicMT",
    # CourierNew branch
    "CourierNew", "CourierNewPSMT", "CourierNew-Bold",
    "CourierNewPS-BoldItalicMT",
    # Symbol / Times alias edge cases
    "Symbol,Bold", "Times", "Times,Bold",
    # case-insensitive
    "helvetica", "ARIAL", "couriernew", "TIMESNEWROMAN",
    # unknowns
    "NoSuchFont-XYZ", "Wingdings", "", "Helvetica-Light",
]

# Inputs whose resolution differs ONLY because of the two documented
# divergences (case-folding + extended aliases). For these the oracle
# returns null while pypdfbox resolves to a canonical name. The test
# asserts pypdfbox resolves them but does NOT require parity.
_PY_EXTENSION_ONLY = {
    # case-folded canonical / alias
    "helvetica", "ARIAL", "couriernew", "TIMESNEWROMAN",
    # extended -PS / -MT / -Bold / -Italic aliases not in upstream's 24
    "Arial-Bold", "Arial-Italic",
    "TimesNewRomanPSMT", "TimesNewRoman-Bold", "TimesNewRomanPS-BoldMT",
    "TimesNewRomanPS-ItalicMT",
    "CourierNewPSMT", "CourierNew-Bold", "CourierNewPS-BoldItalicMT",
}

# Per-glyph width queries — must match the oracle byte-for-byte.
_GW_QUERIES = [
    ("Helvetica", "A"), ("Helvetica", "space"), ("Helvetica", "i"),
    ("Helvetica-Bold", "A"), ("Times-Roman", "A"), ("Times-Roman", "W"),
    ("Courier", "A"), ("Courier", "i"), ("Courier", "W"),
    ("Symbol", "alpha"), ("Symbol", "summation"), ("Symbol", "space"),
    ("ZapfDingbats", "a1"), ("ZapfDingbats", "a10"), ("ZapfDingbats", "space"),
    ("Helvetica", "thisGlyphDoesNotExist"),
    ("Arial", "A"), ("CourierNew", "i"),
]

_AFM_QUERIES = [
    "Helvetica", "Symbol", "ZapfDingbats", "Arial", "TimesNewRomanPSMT",
    "NoSuchFont-XYZ",
]


def _fmt(v: float) -> str:
    """Match the Java probe's ``String.format("%.4f", ...)`` with -0.0 collapse."""
    if v == 0.0:
        v = 0.0
    return f"{v:.4f}"


def _parse_oracle() -> dict[str, dict[str, object]]:
    """Run the probe and bucket its lines by record type."""
    lines = run_probe_text("Standard14FontFuzzProbe").splitlines()
    mapping: dict[str, tuple[str, str]] = {}
    names_size: int | None = None
    gw: dict[tuple[str, str], str] = {}
    afm: dict[str, str] = {}
    for line in lines:
        parts = line.split("\t")
        kind = parts[0]
        if kind == "MAP":
            mapping[parts[1]] = (parts[2], parts[3])
        elif kind == "NAMES":
            names_size = int(parts[1])
        elif kind == "GW":
            gw[(parts[1], parts[2])] = parts[3]
        elif kind == "AFM":
            afm[parts[1]] = parts[2]
    return {"map": mapping, "names": names_size, "gw": gw, "afm": afm}


@requires_oracle
def test_standard14_name_mapping_is_conservative_superset() -> None:
    """getMappedFontName / containsName: pypdfbox is a conservative superset.

    Wherever BOTH sides resolve a name they MUST resolve to the same
    canonical font, and wherever pypdfbox returns null the oracle MUST also
    return null. Inputs that pypdfbox resolves only because of its two
    documented extensions (case-folding + extended aliases) are exempted
    from the equality check but still asserted to resolve."""
    oracle = _parse_oracle()["map"]
    assert isinstance(oracle, dict)
    diffs: list[str] = []
    for q in _MAP_QUERIES:
        j_mapped, j_contains = oracle[q]
        p_mapped = Standard14Fonts.get_mapped_font_name(q)
        p_contains = Standard14Fonts.contains_name(q)
        p_mapped_str = p_mapped if p_mapped is not None else "null"
        p_contains_str = str(p_contains).lower()
        if q in _PY_EXTENSION_ONLY:
            # Documented divergence: upstream returns null, pypdfbox resolves.
            assert j_mapped == "null", f"oracle unexpectedly mapped {q!r}"
            assert p_mapped is not None, f"pypdfbox extension failed for {q!r}"
            continue
        if (p_mapped_str, p_contains_str) != (j_mapped, j_contains):
            diffs.append(
                f"  {q!r}: java=({j_mapped},{j_contains}) "
                f"py=({p_mapped_str},{p_contains_str})"
            )
    assert not diffs, "Standard14 name-mapping parity broken:\n" + "\n".join(diffs)


@requires_oracle
def test_standard14_names_size_is_documented_superset() -> None:
    """getNames(): upstream ships 38 (14 canonical + 24 aliases); pypdfbox's
    extended alias set is strictly larger. Pin both numbers so a future
    upstream re-sync (or an accidental alias drop) is caught."""
    oracle = _parse_oracle()["names"]
    assert oracle == 38, f"oracle Standard14 name count changed: {oracle}"
    py_size = len(Standard14Fonts.get_all_names())
    # Documented pypdfbox extension (see module docstring); strictly larger.
    assert py_size > oracle, f"pypdfbox name set unexpectedly small: {py_size}"
    assert py_size == 59, f"pypdfbox name count changed unexpectedly: {py_size}"


@requires_oracle
def test_standard14_per_glyph_widths_match_oracle() -> None:
    """getAFM(...).getCharacterWidth must match the oracle byte-for-byte for
    Latin / Symbol / ZapfDingbats glyphs, missing glyphs (-> 0), and aliases
    (which resolve to the same canonical AFM)."""
    oracle = _parse_oracle()["gw"]
    assert isinstance(oracle, dict)
    diffs: list[str] = []
    for font, glyph in _GW_QUERIES:
        afm = Standard14Fonts.get_afm(font)
        py = "NOAFM" if afm is None else _fmt(afm.get_glyph_width(glyph))
        j = oracle[(font, glyph)]
        if py != j:
            diffs.append(f"  ({font},{glyph}): java={j} py={py}")
    assert not diffs, "Standard14 per-glyph width parity broken:\n" + "\n".join(diffs)


@requires_oracle
def test_standard14_get_afm_presence_matches_oracle() -> None:
    """getAFM presence must match the oracle — including the wave-1559 fix
    making ``get_afm`` return ``None`` (not raise) for an unmapped name,
    mirroring upstream ``getAFM``'s null return. Note ``TimesNewRomanPSMT``
    is null upstream but present in pypdfbox (extended alias)."""
    oracle = _parse_oracle()["afm"]
    assert isinstance(oracle, dict)
    diffs: list[str] = []
    for q in _AFM_QUERIES:
        afm = Standard14Fonts.get_afm(q)
        py = "null" if afm is None else "present"
        j = oracle[q]
        if q == "TimesNewRomanPSMT":
            # Documented extended-alias divergence: upstream null, pypdfbox present.
            assert j == "null" and py == "present"
            continue
        if py != j:
            diffs.append(f"  {q!r}: java={j} py={py}")
    assert not diffs, "Standard14 getAFM presence parity broken:\n" + "\n".join(diffs)


# ---- self-contained value pins (run without the live oracle) --------------
# PDFBox-3.0.7-derived expected values so the surface stays pinned even when
# the jar/JDK is absent. Captured from the live oracle in wave 1559.


def test_standard14_per_glyph_widths_pinned_values() -> None:
    """AFM-derived per-glyph widths pinned to PDFBox-3.0.7 oracle values."""
    expected = {
        ("Helvetica", "A"): 667.0, ("Helvetica", "space"): 278.0,
        ("Helvetica", "i"): 222.0, ("Helvetica-Bold", "A"): 722.0,
        ("Times-Roman", "A"): 722.0, ("Times-Roman", "W"): 944.0,
        ("Courier", "A"): 600.0, ("Courier", "i"): 600.0,
        ("Courier", "W"): 600.0, ("Symbol", "alpha"): 631.0,
        ("Symbol", "summation"): 713.0, ("Symbol", "space"): 250.0,
        ("ZapfDingbats", "a1"): 974.0, ("ZapfDingbats", "a10"): 692.0,
        ("ZapfDingbats", "space"): 278.0,
        ("Helvetica", "thisGlyphDoesNotExist"): 0.0,
        ("Arial", "A"): 667.0, ("CourierNew", "i"): 600.0,
    }
    for (font, glyph), want in expected.items():
        afm = Standard14Fonts.get_afm(font)
        assert afm is not None, f"no AFM for {font!r}"
        assert afm.get_glyph_width(glyph) == want, f"{font}/{glyph}"


def test_standard14_get_afm_null_for_unmapped() -> None:
    """Wave-1559 fix: ``get_afm`` returns ``None`` (not raises) for an
    unmapped base font, mirroring upstream ``Standard14Fonts.getAFM``."""
    assert Standard14Fonts.get_afm("NoSuchFont-XYZ") is None
    assert Standard14Fonts.get_afm(None) is None
    assert Standard14Fonts.get_afm("Wingdings") is None
    # Aliases / canonical names still return their AFM.
    assert Standard14Fonts.get_afm("Arial") is not None
    assert Standard14Fonts.get_afm("Helvetica") is Standard14Fonts.get_afm("Arial")
