"""Live PDFBox differential parity for the pdmodel ``PDType1Font`` Standard-14
AFM-backed metric surface (wave 1529).

Distinct from the fontbox-level ``Type1Font*`` probes (which fingerprint PFB /
charstring parsing): this drives ``PDType1Font`` *dictionary* behaviour on
NON-embedded fonts (no ``/FontFile``) —

* ``get_width(code)``       — the full width-resolution cascade
                              (``/Widths`` window → Standard-14 AFM advance →
                              ``get_width_from_font``);
* ``get_width_from_font``   — the embedded-program / substitute advance;
* ``is_standard14()``       — name-based core detection (excludes a
                              ``/Differences`` overlay font);
* ``is_embedded()``         — false for every probed font here;
* ``get_encoding_typed()``  — class identity (built-in ``Type1Encoding`` vs a
                              named encoding vs ``DictionaryEncoding``);
* ``get_encoding_typed().get_name(code)`` — the code → glyph-name mapping.

The oracle output is produced by ``oracle/probes/PdType1FontFuzzProbe.java``;
the Python side builds the identical font dictionaries and reconstructs the same
tab-delimited line format.

Parity result (verified against PDFBox 3.0.7):

* ``get_width(code)`` matches **exactly** for every Standard-14 font — the AFM
  advance path (``getStandard14Width``) is the deterministic, realistic case and
  is fully aligned (a ``/Widths`` array still overrides the AFM identically).
* ``is_standard14`` / ``is_embedded`` / encoding-class / glyph-name all match.

Two systematic divergences, BOTH traced to a single deliberate architectural
choice and pinned both-sides below (not bugs):

  D1. ``get_width_from_font`` precision. Upstream ``PDType1Font.getWidthFromFont``
      reads the *machine-dependent substitute* FontBox program loaded by the
      ``FontMapper`` (e.g. Helvetica → a system Liberation/Arial face), so it
      returns the program's scaled advance (``666.9922`` for ``A``). pypdfbox
      keeps substitute-program resolution in the renderer (see DEFERRED.md
      wave 1488: "substitute-GID resolution in the renderer (documented
      divergence)") and instead returns the bundled Adobe AFM integer advance
      (``667.0``). The two agree on the *integer* magnitude; only the sub-unit
      remainder differs.

  D2. Unknown / non-Standard-14 non-embedded font. Upstream ``getWidth`` falls
      through to the same substitute program and reports its advances
      (``333.0078`` for a Helvetica-ish substitute), while pypdfbox has no
      substitute program and reports ``0.0`` (only the ``.notdef`` → 250
      sentinel from ``get_width_from_font`` survives).

Because both stem from the substitute-font path that pypdfbox intentionally
omits at the model layer, the test asserts exact parity on the aligned columns
and pins the divergent ``get_width_from_font`` column with a both-sides
expectation table so any *future* drift (e.g. ``get_width`` itself diverging for
a Standard-14 font) fails loudly.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
)
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from tests.oracle.harness import requires_oracle, run_probe_text

_TYPE = COSName.get_pdf_name("Type")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_FONT = COSName.get_pdf_name("Font")
_BASE_FONT = COSName.get_pdf_name("BaseFont")
_FIRST_CHAR = COSName.get_pdf_name("FirstChar")
_LAST_CHAR = COSName.get_pdf_name("LastChar")
_WIDTHS = COSName.get_pdf_name("Widths")
_FONT_DESC = COSName.get_pdf_name("FontDescriptor")
_FONT_NAME = COSName.get_pdf_name("FontName")
_ENCODING = COSName.get_pdf_name("Encoding")
_BASE_ENCODING = COSName.get_pdf_name("BaseEncoding")
_DIFFERENCES = COSName.get_pdf_name("Differences")

_CODES = [0, 32, 39, 65, 96, 97, 128, 141, 173, 200, 255]


def _fmt(v: float) -> str:
    if v == 0.0:
        v = 0.0
    return f"{v:.4f}"


def _base_dict(name: str) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _FONT)
    d.set_item(_SUBTYPE, COSName.get_pdf_name("Type1"))
    d.set_name(_BASE_FONT, name)
    return d


def _add_descriptor(d: COSDictionary, name: str) -> None:
    fd = COSDictionary()
    fd.set_item(_TYPE, COSName.get_pdf_name("FontDescriptor"))
    fd.set_name(_FONT_NAME, name)
    d.set_item(_FONT_DESC, fd)


def _std14(name: str) -> PDType1Font:
    d = _base_dict(name)
    _add_descriptor(d, name)
    return PDType1Font(d)


def _std14_enc(name: str, enc: COSName) -> PDType1Font:
    d = _base_dict(name)
    d.set_item(_ENCODING, enc)
    _add_descriptor(d, name)
    return PDType1Font(d)


def _helv_with_widths(
    first_char: int, last_char: int, widths: list[float]
) -> PDType1Font:
    d = _base_dict("Helvetica")
    d.set_int(_FIRST_CHAR, first_char)
    d.set_int(_LAST_CHAR, last_char)
    arr = COSArray()
    for w in widths:
        arr.add(COSFloat(w))
    d.set_item(_WIDTHS, arr)
    _add_descriptor(d, "Helvetica")
    return PDType1Font(d)


def _helv_diff() -> PDType1Font:
    d = _base_dict("Helvetica")
    enc = COSDictionary()
    enc.set_item(_TYPE, COSName.get_pdf_name("Encoding"))
    enc.set_item(_BASE_ENCODING, COSName.WIN_ANSI_ENCODING)
    diffs = COSArray()
    diffs.add(COSInteger.get(65))
    diffs.add(COSName.get_pdf_name("bullet"))
    diffs.add(COSInteger.get(97))
    diffs.add(COSName.get_pdf_name("dagger"))
    enc.set_item(_DIFFERENCES, diffs)
    d.set_item(_ENCODING, enc)
    _add_descriptor(d, "Helvetica")
    return PDType1Font(d)


def _bare(name: str) -> PDType1Font:
    return PDType1Font(_base_dict(name))


def _fonts() -> list[tuple[str, PDType1Font]]:
    """Mirror PdType1FontFuzzProbe.main's font list exactly."""
    return [
        ("helv_bare", _std14("Helvetica")),
        ("times_bare", _std14("Times-Roman")),
        ("symbol_bare", _std14("Symbol")),
        ("zapf_bare", _std14("ZapfDingbats")),
        ("courier_bo", _std14("Courier-BoldOblique")),
        ("helv_widths", _helv_with_widths(65, 68, [999.0, 888.0, 777.0, 666.0])),
        ("helv_short", _helv_with_widths(65, 90, [999.0, 888.0])),
        ("unknown", _bare("MadeUpFont-XYZ")),
        ("helv_winansi", _std14_enc("Helvetica", COSName.WIN_ANSI_ENCODING)),
        ("helv_macroman", _std14_enc("Helvetica", COSName.MAC_ROMAN_ENCODING)),
        ("helv_standard", _std14_enc("Helvetica", COSName.STANDARD_ENCODING)),
        ("helv_diff", _helv_diff()),
        ("helv_nodesc", _bare("Helvetica")),
    ]


def _line(key: str, font: PDType1Font, code: int) -> tuple[str, str, str]:
    """Return (width, width_from_font, glyph_name) cells for one code."""
    try:
        width = _fmt(font.get_width(code))
    except Exception:
        width = "WERR"
    try:
        wff = _fmt(font.get_width_from_font(code))
    except Exception:
        wff = "WFFERR"
    try:
        enc = font.get_encoding_typed()
        glyph = enc.get_name(code) if enc is not None else "NOENC"
    except Exception:
        glyph = "GERR"
    return width, wff, glyph


def _parse_java() -> dict[tuple[str, str, int | None], list[str]]:
    """Parse the Java probe output into {(kind, key, code): cells}."""
    rows: dict[tuple[str, str, int | None], list[str]] = {}
    for raw in run_probe_text("PdType1FontFuzzProbe").splitlines():
        parts = raw.split("\t")
        if parts[0] == "FONT":
            rows[("FONT", parts[1], None)] = parts[2:]
        elif parts[0] == "W":
            rows[("W", parts[1], int(parts[2]))] = parts[3:]
    return rows


# D1/D2 — the only codes whose ``get_width_from_font`` (and, for the unknown
# font, ``get_width``) differ because upstream consults the machine-dependent
# substitute program pypdfbox omits at the model layer. Pinned both-sides.
# Keyed (key, code) -> (java_width, java_wff, py_width, py_wff).
_SUBSTITUTE_DIVERGENCES: set[tuple[str, int]] = {
    # Standard-14 fonts: get_width matches; only get_width_from_font differs
    # (Java reads the substitute program's sub-unit advance, pypdfbox the AFM
    # integer). Every non-.notdef, non-space code with a fractional substitute
    # advance lands here.
    ("helv_bare", 32), ("helv_bare", 39), ("helv_bare", 65),
    ("helv_bare", 96), ("helv_bare", 97), ("helv_bare", 173),
    ("helv_bare", 200),
    ("times_bare", 39), ("times_bare", 65), ("times_bare", 96),
    ("times_bare", 97), ("times_bare", 173), ("times_bare", 200),
    ("symbol_bare", 39), ("symbol_bare", 65), ("symbol_bare", 97),
    ("symbol_bare", 173), ("symbol_bare", 200),
    ("zapf_bare", 32), ("zapf_bare", 39), ("zapf_bare", 65),
    ("zapf_bare", 96), ("zapf_bare", 97), ("zapf_bare", 128),
    ("zapf_bare", 141), ("zapf_bare", 173), ("zapf_bare", 200),
    ("courier_bo", 32), ("courier_bo", 39), ("courier_bo", 65),
    ("courier_bo", 96), ("courier_bo", 97), ("courier_bo", 173),
    ("courier_bo", 200),
    ("helv_widths", 32), ("helv_widths", 39), ("helv_widths", 65),
    ("helv_widths", 96), ("helv_widths", 97), ("helv_widths", 173),
    ("helv_widths", 200),
    ("helv_short", 32), ("helv_short", 39), ("helv_short", 65),
    ("helv_short", 96), ("helv_short", 97), ("helv_short", 173),
    ("helv_short", 200),
    ("helv_winansi", 32), ("helv_winansi", 39), ("helv_winansi", 65),
    ("helv_winansi", 96), ("helv_winansi", 97), ("helv_winansi", 128),
    ("helv_winansi", 141), ("helv_winansi", 173), ("helv_winansi", 200),
    ("helv_macroman", 32), ("helv_macroman", 39), ("helv_macroman", 65),
    ("helv_macroman", 96), ("helv_macroman", 97), ("helv_macroman", 128),
    ("helv_macroman", 200), ("helv_macroman", 255),
    ("helv_standard", 32), ("helv_standard", 39), ("helv_standard", 65),
    ("helv_standard", 96), ("helv_standard", 97), ("helv_standard", 173),
    ("helv_standard", 200),
    ("helv_diff", 32), ("helv_diff", 39), ("helv_diff", 65),
    ("helv_diff", 96), ("helv_diff", 97), ("helv_diff", 128),
    ("helv_diff", 141), ("helv_diff", 173), ("helv_diff", 200),
    ("helv_nodesc", 32), ("helv_nodesc", 39), ("helv_nodesc", 65),
    ("helv_nodesc", 96), ("helv_nodesc", 97), ("helv_nodesc", 173),
    ("helv_nodesc", 200),
    # D2 — unknown non-Standard-14 font: BOTH get_width and get_width_from_font
    # diverge (Java substitute advance vs pypdfbox 0.0) for the mapped codes.
    ("unknown", 32), ("unknown", 39), ("unknown", 65),
    ("unknown", 96), ("unknown", 97), ("unknown", 173),
    ("unknown", 200),
}


@requires_oracle
def test_pd_type1_font_aligned_columns_match_pdfbox() -> None:
    """``is_standard14`` / ``is_embedded`` / encoding-class / glyph-name and
    the deterministic ``get_width`` (Standard-14 AFM) path all match PDFBox
    exactly; only the substitute-program ``get_width_from_font`` column is
    allowed to differ (and is pinned separately)."""
    java = _parse_java()
    fonts = _fonts()
    # FONT-header parity: isStandard14, isEmbedded, encodingClass.
    for key, font in fonts:
        jhdr = java[("FONT", key, None)]
        s14 = "true" if font.is_standard14() else "false"
        emb = "true" if font.is_embedded() else "false"
        enc = font.get_encoding_typed()
        ec = type(enc).__name__ if enc is not None else "null"
        assert [s14, emb, ec] == jhdr, (
            f"FONT header mismatch for {key}: py={[s14, emb, ec]} java={jhdr}"
        )
    # Per-code parity on the aligned columns.
    diffs: list[str] = []
    for key, font in fonts:
        for code in _CODES:
            jw, jwff, jglyph = java[("W", key, code)]
            pw, pwff, pglyph = _line(key, font, code)
            # Glyph name always matches.
            if pglyph != jglyph:
                diffs.append(
                    f"{key}[{code}] glyph: py={pglyph!r} java={jglyph!r}"
                )
            if (key, code) in _SUBSTITUTE_DIVERGENCES:
                continue
            # Aligned codes: get_width AND get_width_from_font both match.
            if pw != jw:
                diffs.append(f"{key}[{code}] width: py={pw} java={jw}")
            if pwff != jwff:
                diffs.append(
                    f"{key}[{code}] width_from_font: py={pwff} java={jwff}"
                )
    assert not diffs, "PDType1Font parity broken:\n" + "\n".join(diffs)


@requires_oracle
def test_pd_type1_font_get_width_standard14_matches_pdfbox() -> None:
    """The deterministic contract: ``get_width(code)`` matches PDFBox exactly
    for every *Standard-14* font (the AFM advance path), regardless of whether
    the divergent substitute column differs. This is the column that actually
    drives text layout, so it must never drift."""
    java = _parse_java()
    diffs: list[str] = []
    for key, font in _fonts():
        # Skip the non-Standard-14 fonts: their get_width goes through the
        # substitute-program path (D2), pinned both-sides separately.
        # ``unknown`` (made-up name) and ``helv_diff`` (/Differences overlay,
        # which PDSimpleFont.is_standard14 excludes) are the two.
        if not font.is_standard14():
            continue
        for code in _CODES:
            jw = java[("W", key, code)][0]
            pw = _fmt(font.get_width(code))
            if pw != jw:
                diffs.append(f"{key}[{code}] get_width: py={pw} java={jw}")
    assert not diffs, "Standard-14 get_width parity broken:\n" + "\n".join(diffs)


@requires_oracle
def test_pd_type1_font_substitute_divergence_pinned() -> None:
    """Pin D1/D2 BOTH-sides for the substitute-program codes.

    pypdfbox's ``get_width_from_font`` is *deterministic*: the Standard-14 AFM
    integer advance for the resolved glyph (or ``0.0`` when the AFM lacks the
    glyph, e.g. ``sfthyphen`` / ``Euro`` under some encodings, and for the
    unknown non-Standard-14 font that has no AFM at all). Java instead reports
    the machine-dependent substitute FontBox program's advance.

    This test asserts (a) the pypdfbox value equals what the bundled AFM yields
    and (b) the two sides genuinely differ — so the divergence is real and
    confined to the substitute path, and any *future* drift that accidentally
    aligned (or further mis-aligned) them fails loudly.
    """
    from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

    java = _parse_java()
    for key, font in _fonts():
        for code in _CODES:
            if (key, code) not in _SUBSTITUTE_DIVERGENCES:
                continue
            jwff = java[("W", key, code)][1]
            pwff = _fmt(font.get_width_from_font(code))
            # The pypdfbox side must equal its deterministic AFM-derived value.
            name = font.code_to_name(code)
            base = font.get_name() or ""
            if not Standard14Fonts.contains_name(base) or name == ".notdef":
                expected = "0.0000"
            else:
                expected = _fmt(
                    float(Standard14Fonts.get_glyph_width(base, name))
                )
            assert pwff == expected, (
                f"{key}[{code}] width_from_font not deterministic: "
                f"py={pwff} expected-AFM={expected}"
            )
            # And the substitute side really does differ (the pinned divergence).
            assert pwff != jwff, (
                f"{key}[{code}] expected substitute divergence but py==java=={pwff}"
            )


def test_is_standard14_excludes_differences_overlay() -> None:
    """Regression pin (no oracle): a Standard-14 base font with a non-trivial
    ``/Differences`` overlay is NOT ``is_standard14`` (PDSimpleFont rule), so
    ``get_width`` falls through to ``get_width_from_font`` rather than the AFM
    path — matching upstream's ``helv_diff`` line."""
    font = _helv_diff()
    assert not font.is_standard14()
    assert not font.is_embedded()
    # bullet at code 65 via /Differences over WinAnsi base.
    enc = font.get_encoding_typed()
    assert enc is not None
    assert enc.get_name(65) == "bullet"
    assert enc.get_name(97) == "dagger"
    # A plain Standard-14 Helvetica (no /Differences) IS standard14.
    assert _std14("Helvetica").is_standard14()


def test_widths_array_overrides_afm() -> None:
    """Regression pin (no oracle): an explicit ``/Widths`` entry wins over the
    Standard-14 AFM advance for in-window codes, while out-of-window codes fall
    through to the AFM-driven ``get_width_from_font`` (matching upstream)."""
    font = _helv_with_widths(65, 68, [999.0, 888.0, 777.0, 666.0])
    assert font.is_standard14()
    # In-window: /Widths wins.
    assert font.get_width(65) == 999.0
    assert font.get_width(68) == 666.0
    # Out-of-window code 97 ('a'): no /Widths slot → 0.0 (no /MissingWidth and
    # the dict carries a /Widths array so the descriptor branch returns its
    # MissingWidth default of 0.0). Matches Java's 0.0000.
    assert font.get_width(97) == 0.0
