"""Live PDFBox differential fuzz for FontMapperImpl name-normalization.

Wave 1560 (agent C). Complements ``test_font_substitute_oracle.py`` (which
pins the ``getFallbackFontName`` flag matrix and a fixed ``getSubstitutes``
query list) by attacking three host-INDEPENDENT facets of
``org.apache.pdfbox.pdmodel.font.FontMapperImpl`` that the older probe does
not exercise:

1. ``getPostScriptNames(String)`` — the verbatim + hyphen-stripped alt-spelling
   set used to build the name index. Pure string transform, host-independent.

2. ``getSubstitutes(String)`` — aggressive normalization edge cases (comma
   aliases for every canonical family, leading/trailing/internal whitespace,
   mixed/upper case, empty string, names normalizing to the same key). The
   returned list is the static constructor table — host-independent.

3. ``getFallbackFontName(PDFontDescriptor)`` — the
   ``toLowerCase().contains("bold"|"black"|"heavy")`` bold heuristic across
   case variants and substring positions, including the false-positive guard
   ("notbold" STILL matches because "bold" is a substring — this is the exact
   upstream contract, pinned to document it).

The Java side is ``oracle/probes/FontMapperFuzzProbe.java``. The Python side
reconstructs every line from pypdfbox and asserts an exact textual match. All
asserted facets are PostScript-name strings + flag-driven family names, never
glyph outlines or host-font binaries, so the comparison is deterministic
everywhere the oracle runs.

Parity outcome: pypdfbox matches Apache PDFBox on every line — the
name-normalization (``replace(" ", "").lower()``), the hyphen-stripped PSN
set, and the bold-name heuristic are all faithful ports. No divergence found.
"""

from __future__ import annotations

from pypdfbox.pdmodel.font.font_mapper_impl import FontMapperImpl
from tests.oracle.harness import requires_oracle, run_probe_text

# Descriptor flag bits (mirror PDFontDescriptor's private constants).
_FLAG_FIXED_PITCH = 1
_FLAG_SERIF = 2
_FLAG_ITALIC = 64

_PSN_QUERIES = [
    "Arial",
    "Arial-Black",
    "Arial-BoldMT",
    "ArialMT",
    "Times-Roman",
    "Courier-BoldOblique",
    "A-B-C",
    "NoHyphenHere",
    "",
    "-",
    "Foo-",
    "-Bar",
]

_SUBST_QUERIES = [
    "CourierNew,Bold", "CourierNew,Italic", "CourierNew,BoldItalic",
    "Times,Bold", "Times,Italic", "Times,BoldItalic",
    "Symbol,Bold", "Symbol,Italic", "Symbol,BoldItalic",
    " Arial", "Arial ", "  Arial  ", "Ar ial", "Times New Roman",
    "Courier New", "Times Roman",
    "ARIAL", "arial", "ArIaL", "TIMESNEWROMAN", "timesnewroman",
    "", "   ", "TotallyUnknownFont",
    "Times", "Symbol", "ZapfDingbats",
]

_HEURISTIC_NAMES = [
    "ArialBOLD", "arialbold", "ArialBold", "UltraBlackText",
    "heavyweight", "FooBlackItalic", "SemiBold", "notbold",
    "BOLD", "Black", "Heavy", "Regular", "Light", "Thin",
    "Bold Condensed", "Extra-Heavy", "", "Plain",
]

_STYLE_LABELS = ["sans", "serif", "fixed", "sansItalic"]
_STYLE_FLAGS = [0, _FLAG_SERIF, _FLAG_FIXED_PITCH, _FLAG_ITALIC]


def _py_fallback_name(flags: int, font_name: str | None) -> str:
    """Reproduce FontMapperImpl.getFallbackFontName via a stub descriptor.

    The production method consults only ``is_fixed_pitch`` / ``is_serif`` /
    ``is_italic`` / ``get_font_name``, so a duck-typed stub suffices.
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
    """Reconstruct FontMapperFuzzProbe's stdout from pypdfbox line-for-line."""
    lines: list[str] = []
    mapper = FontMapperImpl()

    # ---- surface 1: getPostScriptNames ----
    for q in _PSN_QUERIES:
        sorted_names = sorted(FontMapperImpl.get_post_script_names(q))
        lines.append(f"PSN\t{q}\t{','.join(sorted_names)}")

    # ---- surface 2: getSubstitutes fuzz ----
    for q in _SUBST_QUERIES:
        subs = ",".join(mapper.get_substitutes(q))
        lines.append(f"SUBST\t{q}\t{subs}")

    # ---- surface 3: getFallbackFontName bold-heuristic fuzz ----
    for nm in _HEURISTIC_NAMES:
        for label, flags in zip(_STYLE_LABELS, _STYLE_FLAGS, strict=True):
            tag = "empty" if nm == "" else nm.replace(" ", "_")
            name = _py_fallback_name(flags, nm)
            lines.append(f"FALLBACK\t{label}_n{tag}\t{name}")

    return "\n".join(lines) + "\n"


@requires_oracle
def test_font_mapper_name_normalization_matches_pdfbox() -> None:
    """FontMapperImpl PSN / substitute-normalization / bold heuristic must
    match Apache PDFBox exactly (host-independent facets).
    """
    jl = run_probe_text("FontMapperFuzzProbe").splitlines()
    pl = _py_probe_output().splitlines()
    assert len(jl) == len(pl), f"line-count mismatch: java={len(jl)} py={len(pl)}"
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(jl, pl, strict=True))
        if j != p
    ]
    assert not diffs, "font mapper parity broken:\n" + "\n".join(diffs[:40])


def test_post_script_names_hyphen_stripping() -> None:
    """getPostScriptNames returns verbatim + hyphen-stripped form (host-free).

    Self-contained against PDFBox-3.0.7-derived expected values so the facet
    stays pinned even when the live oracle is unavailable.
    """
    assert FontMapperImpl.get_post_script_names("Arial-Black") == {
        "Arial-Black",
        "ArialBlack",
    }
    # No hyphen -> a singleton set.
    assert FontMapperImpl.get_post_script_names("ArialMT") == {"ArialMT"}
    # Multiple hyphens all collapse in the stripped spelling.
    assert FontMapperImpl.get_post_script_names("A-B-C") == {"A-B-C", "ABC"}


def test_substitutes_whitespace_and_case_normalization() -> None:
    """getSubstitutes strips ALL spaces and lowercases the key (host-free).

    Pins the PDFBox-3.0.7 contract: ``"Ar ial"`` and ``"  Arial  "`` both
    resolve to Arial's (Helvetica) substitute list, and an unregistered key
    returns the empty list.
    """
    mapper = FontMapperImpl()
    arial = mapper.get_substitutes("Arial")
    assert arial  # non-empty (Helvetica substitutes via the alias loop)
    assert mapper.get_substitutes("Ar ial") == arial
    assert mapper.get_substitutes("  Arial  ") == arial
    assert mapper.get_substitutes("ARIAL") == arial
    # "Courier New" -> key "couriernew" is a registered alias.
    assert mapper.get_substitutes("Courier New") == mapper.get_substitutes(
        "CourierNew"
    )
    # "Times Roman" -> key "timesroman" is NOT registered (only "Times" is).
    assert mapper.get_substitutes("Times Roman") == []
    assert mapper.get_substitutes("") == []
    assert mapper.get_substitutes("TotallyUnknownFont") == []


def test_fallback_bold_heuristic_substring_contract() -> None:
    """The bold heuristic is a plain lowercase substring test (host-free).

    Pins the exact PDFBox-3.0.7 contract, including its false positives:
    ``"notbold"`` and ``"SemiBold"`` are treated as bold because ``"bold"``
    is a substring; ``"black"`` / ``"heavy"`` likewise.
    """
    # Substring matches -> bold variant chosen.
    assert _py_fallback_name(0, "notbold") == "Helvetica-Bold"
    assert _py_fallback_name(0, "SemiBold") == "Helvetica-Bold"
    assert _py_fallback_name(0, "ArialBOLD") == "Helvetica-Bold"
    assert _py_fallback_name(0, "UltraBlackText") == "Helvetica-Bold"
    assert _py_fallback_name(0, "heavyweight") == "Helvetica-Bold"
    # No bold/black/heavy substring -> regular variant.
    assert _py_fallback_name(0, "Regular") == "Helvetica"
    assert _py_fallback_name(0, "Light") == "Helvetica"
    # Style flags compose with the bold heuristic.
    assert _py_fallback_name(_FLAG_ITALIC, "Bold Condensed") == "Helvetica-BoldOblique"
    assert _py_fallback_name(_FLAG_SERIF, "Extra-Heavy") == "Times-Bold"
    assert _py_fallback_name(_FLAG_FIXED_PITCH, "Plain") == "Courier"
