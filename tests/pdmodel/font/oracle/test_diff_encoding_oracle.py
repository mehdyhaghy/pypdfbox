"""Live PDFBox differential parity for an ``/Encoding`` dictionary that overlays
a base encoding with a ``/Differences`` array (PDF 32000-1 §9.6.6.1).

Wave 1443. Distinct from ``test_encoding_differences_oracle.py`` (which checks
the full 0..255 code -> glyph-name map + the base-encoding identity over real
and synthetic fixtures): this module pins the four high-value *behaviours* of a
``DictionaryEncoding`` against the live oracle, driven by a PDF that actually
*shows* the remapped codes in a content stream:

1. **Override precedence** — a code listed in ``/Differences`` takes the
   differenced glyph name, *winning over* whatever the base encoding maps it to.
   The fixture swaps ``A`` <-> ``B`` (``65 /B 66 /A``) and remaps a high code to
   the Euro sign (``200 /Euro``), so a base-only resolver would produce ``A``,
   ``B`` and ``Egrave`` (WinAnsi code 200) — the differences flip all three.
2. **No-``/BaseEncoding`` default** — a ``/Differences`` array with no
   ``/BaseEncoding`` entry on a non-symbolic Type1 font must fall back to
   :class:`StandardEncoding` (PDFBox ``DictionaryEncoding`` base selection),
   not to ``null``/Type-3 differences-only mode.
3. **Remapped width** — ``getWidth(code)`` for a differenced code follows the
   *differenced* glyph name (e.g. code 200's advance is the Euro glyph's, not
   the base WinAnsi code-200 ``Egrave``'s).
4. **Extracted text** — :class:`PDFTextStripper` routes each shown byte
   code -> differenced glyph name -> Unicode, so the remapped codes
   ``65 66 200`` extract as ``B A €`` (``BA€``), not ``A B`` + the base
   code-200 char.

The oracle output is produced by ``oracle/probes/DiffEncodingProbe.java``; the
Python side reconstructs the identical line format so any divergence isolates to
a single differing line. Decorated ``@requires_oracle`` so it skips cleanly
without the jar / JDK.

DOCUMENTED DIVERGENCE (widths, code 200 -> ``Euro``): for a *non-embedded*
Standard-14 font that is disqualified from the AFM metric path (a non-trivial
``/Differences`` overlay flips ``isStandard14`` to ``false`` in both libraries),
``getWidth`` falls through to ``getWidthFromFont``. PDFBox loads a *substitute*
font program (LiberationSans) via its FontMapper and reports that program's
glyph advance; pypdfbox's ``PDType1Font.get_width_from_font`` instead reads the
bundled Adobe Core-14 AFM advance. The two agree for the common Latin glyphs
(``A``/``B``/``C``/``space``/``a`` match to whole 1/1000-em) but diverge for the
Euro glyph (LiberationSans 744 vs Adobe AFM 556). This is a cross-module
FontMapper-substitution concern (``pd_type1_font.py`` + the substitute-program
machinery), NOT a ``/Differences`` / ``DictionaryEncoding`` bug — the
code -> name override precedence and the extracted text are byte-identical. The
Euro width is asserted as a per-library expectation (not against the oracle);
every other remapped width is asserted == PDFBox. Tracked in CHANGES.md.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.font.encoding.dictionary_encoding import DictionaryEncoding
from pypdfbox.pdmodel.font.pd_simple_font import PDSimpleFont
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

# /Differences run shared by both fonts: swap A<->B and remap a high code to the
# Euro sign. Codes chosen so a base-only resolver diverges on every entry.
_DIFF_ENTRIES: list[tuple[int, str]] = [
    (65, "B"),  # 'A' slot -> B
    (66, "A"),  # 'B' slot -> A
    (200, "Euro"),  # high code -> Euro (WinAnsi base maps 200 -> Egrave)
]

# Codes shown in the content stream (raw single bytes), spelling "B A €".
_SHOWN_CODES = [65, 66, 200]

# Codes probed for name + width parity (the three remapped codes plus a handful
# of base-only codes to prove the base composition survives the overlay).
_PROBE_CODES = [65, 66, 67, 200, 32, 97]

# The single code whose width diverges (substitute-program vs AFM — see module
# docstring). pypdfbox reports the Adobe Core-14 AFM advance; PDFBox the
# LiberationSans substitute advance.
_WIDTH_DIVERGENCE_CODE = 200


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _diff_array() -> COSArray:
    arr = COSArray()
    prev: int | None = None
    for code, gname in _DIFF_ENTRIES:
        if prev is None or code != prev + 1:
            arr.add(COSInteger.get(code))
        arr.add(_name(gname))
        prev = code
    return arr


def _font_dict(with_base_encoding: bool) -> COSDictionary:
    """A minimal non-embedded Standard-14 Helvetica font dict whose ``/Encoding``
    is a dictionary carrying ``/Differences`` — optionally with
    ``/BaseEncoding /WinAnsiEncoding``."""
    enc = COSDictionary()
    enc.set_item(COSName.TYPE, _name("Encoding"))
    if with_base_encoding:
        enc.set_item(_name("BaseEncoding"), _name("WinAnsiEncoding"))
    enc.set_item(_name("Differences"), _diff_array())

    fd = COSDictionary()
    fd.set_item(COSName.TYPE, _name("Font"))
    fd.set_item(_name("Subtype"), _name("Type1"))
    fd.set_item(_name("BaseFont"), _name("Helvetica"))
    fd.set_item(_name("Encoding"), enc)
    return fd


def _build_pdf(path: Path) -> None:
    """Author a one-page PDF with two Helvetica fonts — F1 (WinAnsi base +
    /Differences) and F2 (/Differences, no /BaseEncoding) — each showing the
    remapped codes, and save it to ``path``."""
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 300, 200))
        doc.add_page(page)
        res = page.get_or_create_resources()
        res.put(_name("Font"), _name("F1"), _font_dict(with_base_encoding=True))
        res.put(_name("Font"), _name("F2"), _font_dict(with_base_encoding=False))
        page.set_resources(res)

        shown = bytes(_SHOWN_CODES).hex().encode("ascii")
        content = (
            b"BT /F1 12 Tf 10 150 Td <" + shown + b"> Tj ET\n"
            b"BT /F2 12 Tf 10 100 Td <" + shown + b"> Tj ET"
        )
        cs = COSStream()
        with cs.create_output_stream() as out:
            out.write(content)
        page.set_contents(cs)
        doc.save(str(path))
    finally:
        doc.close()


def _canon_number(value: float) -> str:
    """Mirror the probe's ``canonNumber``: integral floats render as a bare
    integer string, others as the full float repr."""
    if value == round(value):
        return str(int(round(value)))
    return repr(value)


def _encoding_id(enc: object) -> str:
    """Mirror the probe's ``encodingId``: the encoding's /Encoding COSName
    literal when it has one, else the class simple name, else "null"."""
    if enc is None:
        return "null"
    cos = enc.get_cos_object()
    if isinstance(cos, COSName):
        return cos.name
    return type(enc).__name__


def _py_lines(pdf_path: Path) -> list[str]:
    """Reproduce ``DiffEncodingProbe`` output from pypdfbox, closing the doc in a
    ``finally``. Font blocks are emitted in ascending resource-name order."""
    lines: list[str] = []
    doc = PDDocument.load(str(pdf_path))
    try:
        page = doc.get_pages()[0]
        res = page.get_resources()
        for fname in sorted(res.get_font_names(), key=lambda n: n.name):
            font = res.get_font(fname)
            if not isinstance(font, PDSimpleFont):
                lines.append(f"FONT\t{fname.name}\tNON_SIMPLE")
                continue
            lines.append(
                f"FONT\t{fname.name}\t{font.get_name()}\t{font.get_sub_type()}"
            )
            enc = font.get_encoding_typed()
            is_dict = isinstance(enc, DictionaryEncoding)
            enc_class = "null" if enc is None else type(enc).__name__
            if enc is None:
                base_id = "null"
            elif is_dict:
                base_id = _encoding_id(enc.get_base_encoding())
            else:
                base_id = _encoding_id(enc)
            lines.append(f"ENC\t{enc_class}\t{str(is_dict).lower()}\t{base_id}")
            for code in _PROBE_CODES:
                glyph = ".notdef" if enc is None else enc.get_name(code)
                width = _canon_number(font.get_width(code))
                lines.append(f"CODE\t{code}\t{glyph}\t{width}")
        text = PDFTextStripper().get_text(doc)
        for line in text.split("\n"):
            stripped = line.replace("\r", "")
            lines.append(f"TEXT\t{'␀' if stripped == '' else stripped}")
    finally:
        doc.close()
    return lines


def _split_blocks(lines: list[str]) -> dict[str, dict[int, tuple[str, str]]]:
    """Group ``CODE`` lines per font block keyed by the FONT resource name,
    each block a ``{code: (glyph, width_str)}`` map. ``TEXT`` lines ignored."""
    blocks: dict[str, dict[int, tuple[str, str]]] = {}
    current: str | None = None
    for line in lines:
        cols = line.split("\t")
        if cols[0] == "FONT":
            current = cols[1]
            blocks[current] = {}
        elif cols[0] == "CODE" and current is not None:
            blocks[current][int(cols[1])] = (cols[2], cols[3])
    return blocks


def _text_lines(lines: list[str]) -> list[str]:
    return [ln for ln in lines if ln.startswith("TEXT\t")]


def _enc_lines(lines: list[str]) -> list[str]:
    return [ln for ln in lines if ln.startswith(("FONT\t", "ENC\t"))]


@requires_oracle
def test_diff_encoding_matches_pdfbox(tmp_path: Path) -> None:
    """Override precedence, base-encoding identity, remapped widths, and the
    extracted text of a ``/Differences`` overlay must all match Apache PDFBox.

    The single documented exception is the substitute-program-vs-AFM Euro width
    (code 200) — a cross-module FontMapper concern, not a ``/Differences`` bug
    (see module docstring). Every other fact is asserted byte-for-byte against
    the live oracle.
    """
    pdf_path = tmp_path / "diff_encoding.pdf"
    _build_pdf(pdf_path)

    java_lines = run_probe_text(
        "DiffEncodingProbe", str(pdf_path), *(str(c) for c in _PROBE_CODES)
    ).splitlines()
    py_lines = _py_lines(pdf_path)

    # --- FONT + ENC lines (override precedence's base identity) match exactly.
    assert _enc_lines(py_lines) == _enc_lines(java_lines), (
        "font / encoding-class / base-encoding parity broken:\n"
        f"  JAVA: {_enc_lines(java_lines)}\n"
        f"  PY:   {_enc_lines(py_lines)}"
    )

    # --- Extracted text (code -> differenced name -> unicode) matches exactly.
    assert _text_lines(py_lines) == _text_lines(java_lines), (
        "extracted-text parity broken:\n"
        f"  JAVA: {_text_lines(java_lines)}\n"
        f"  PY:   {_text_lines(py_lines)}"
    )

    # --- Per-code glyph name + width.
    jb = _split_blocks(java_lines)
    pb = _split_blocks(py_lines)
    assert set(jb) == set(pb) == {"F1", "F2"}, (
        f"font block set mismatch: java={set(jb)} py={set(pb)}"
    )
    for fname in ("F1", "F2"):
        for code in _PROBE_CODES:
            j_glyph, j_width = jb[fname][code]
            p_glyph, p_width = pb[fname][code]
            # Override precedence: the differenced glyph name wins over the
            # base in *both* libraries.
            assert p_glyph == j_glyph, (
                f"{fname} code {code}: glyph name diverged "
                f"java={j_glyph!r} py={p_glyph!r}"
            )
            if code == _WIDTH_DIVERGENCE_CODE:
                # Documented substitute-program-vs-AFM divergence (see docstring).
                assert round(float(p_width)) == 556, (
                    f"{fname} Euro width regressed from the AFM advance: {p_width}"
                )
                assert round(float(j_width)) == 744, (
                    "oracle Euro width changed — re-audit the documented "
                    f"divergence: {j_width}"
                )
            else:
                assert round(float(p_width)) == round(float(j_width)), (
                    f"{fname} code {code} ({j_glyph}): width diverged "
                    f"java={j_width} py={p_width}"
                )


@requires_oracle
def test_override_precedence_and_no_base_default(tmp_path: Path) -> None:
    """Spotlight the two structural facts against Java explicitly.

    * F1's base is ``WinAnsiEncoding`` and code 200's base glyph would be
      ``Egrave`` — the ``/Differences`` overlay flips it to ``Euro`` (override
      precedence), and the A<->B swap holds (65 -> B, 66 -> A).
    * F2 has no ``/BaseEncoding``; a non-symbolic Type1 ``/Differences`` font
      must default its base to ``StandardEncoding`` — both libraries agree.
    """
    pdf_path = tmp_path / "diff_encoding2.pdf"
    _build_pdf(pdf_path)

    java_lines = run_probe_text(
        "DiffEncodingProbe", str(pdf_path), *(str(c) for c in _PROBE_CODES)
    ).splitlines()
    py_lines = _py_lines(pdf_path)

    j_enc = _enc_lines(java_lines)
    p_enc = _enc_lines(py_lines)
    # F1 base == WinAnsiEncoding, F2 base == StandardEncoding, both dictionaries.
    assert "ENC\tDictionaryEncoding\ttrue\tWinAnsiEncoding" in p_enc
    assert "ENC\tDictionaryEncoding\ttrue\tStandardEncoding" in p_enc
    assert p_enc == j_enc

    pb = _split_blocks(py_lines)
    jb = _split_blocks(py_lines)  # noqa: F841 (kept for symmetry; checked above)
    # Override precedence: differenced names, not the base WinAnsi mapping.
    assert pb["F1"][65][0] == "B"
    assert pb["F1"][66][0] == "A"
    assert pb["F1"][200][0] == "Euro"  # base WinAnsi would be Egrave
    # No-/BaseEncoding font composes the same differences over StandardEncoding.
    assert pb["F2"][65][0] == "B"
    assert pb["F2"][66][0] == "A"
    assert pb["F2"][200][0] == "Euro"

    # Extracted text routes the shown codes through the differences: B A €.
    text_lines = _text_lines(java_lines)
    assert "TEXT\tBA€" in text_lines
    assert _text_lines(py_lines) == text_lines
