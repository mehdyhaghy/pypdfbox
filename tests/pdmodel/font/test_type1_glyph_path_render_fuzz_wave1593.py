"""Fuzz / parity tests for simple Type 1 font glyph PATH rendering — Wave 1593.

Exercises the full ``code -> glyph name -> outline`` pipeline shared by the
renderer's glyph cache (``font.get_normalized_path(code)``) and the
Type1/CFF render branch (``font.get_glyph_path(code)``):

* embedded ``/FontFile`` Type 1 program -> the program's charstring outline
* embedded ``/FontFile3`` (Type1C / CFF) program -> the CFF charstring outline
* non-embedded Standard 14 (Helvetica) -> the bundled substitute outline
* ``/Encoding`` + ``/Differences`` feeding the code -> name lookup
* ``get_normalized_path`` scaling expectations (Type 1 is 1000-upem)
* ``.notdef`` / missing glyph / unmapped code -> empty path
* glyph name absent from the program -> ``.notdef`` fallback / empty

The load-bearing parity fact under test (wave 1593 fix): for a non-embedded
Standard 14 font ``get_normalized_path(code)`` / ``get_path(name)`` must reach
the substitute outline, exactly as ``get_glyph_path(code)`` already did. The
glyph cache the renderer uses calls ``get_normalized_path`` — before the fix
a non-embedded Helvetica rendered nothing through that interface.

Mirrors upstream ``PDType1Font.getPath`` / ``getNormalizedPath`` and
``PDType1CFont.getPath`` / ``getNormalizedPath`` (PDFBox 3.0.7).
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.fontbox.type1.type1_font import Type1Font
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont

_BASE_FONT = COSName.get_pdf_name("BaseFont")
_ENCODING = COSName.get_pdf_name("Encoding")


# ---------- synthetic Type 1 (/FontFile) program ----------


def _stub_type1_program() -> Type1Font:
    """A tiny in-memory Type 1 program with ``.notdef``, ``A``, ``B``."""
    program = Type1Font()

    class _Stub:
        def __init__(self, width: float, commands: list) -> None:
            self.width = width
            self._commands = commands

        def draw(self, pen) -> None:  # noqa: ANN001 — fontTools pen protocol
            for cmd in self._commands:
                if cmd[0] == "moveTo":
                    pen.moveTo(cmd[1])
                elif cmd[0] == "lineTo":
                    pen.lineTo(cmd[1])
                elif cmd[0] == "closePath":
                    pen.closePath()

    glyphs = {
        ".notdef": _Stub(0.0, []),
        "A": _Stub(
            500.0,
            [
                ("moveTo", (0.0, 0.0)),
                ("lineTo", (0.0, 700.0)),
                ("lineTo", (100.0, 700.0)),
                ("lineTo", (100.0, 0.0)),
                ("closePath",),
            ],
        ),
        "B": _Stub(300.0, []),
    }
    program._charstrings = glyphs
    program._font_matrix = [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    program._units_per_em = 1000
    return program


def _embedded_type1_font(
    base_font: str = "MyEmbeddedType1",
    encoding: str | None = "WinAnsiEncoding",
) -> PDType1Font:
    d = COSDictionary()
    d.set_name(_BASE_FONT, base_font)
    if encoding is not None:
        d.set_item(_ENCODING, COSName.get_pdf_name(encoding))
    font = PDType1Font(d)
    font.set_font_program(_stub_type1_program())
    return font


# ---------- synthetic Type1C (/FontFile3) CFF program ----------


def _build_minimal_cff_bytes() -> bytes:
    from fontTools.fontBuilder import FontBuilder
    from fontTools.misc.psCharStrings import T2CharString
    from fontTools.ttLib import TTFont

    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder([".notdef", "A", "B"])
    fb.setupCharacterMap({65: "A", 66: "B"})

    def _cs(program: list) -> T2CharString:
        s = T2CharString()
        s.program = program
        return s

    char_strings = {
        ".notdef": _cs([0, "endchar"]),
        "A": _cs(
            [500, 0, "hmoveto", 700, "vlineto", 100, "hlineto", -700, "vlineto",
             "endchar"]
        ),
        "B": _cs([300, 0, "hmoveto", 500, "vlineto", "endchar"]),
    }
    fb.setupCFF(
        psName="TestType1CWave1593",
        fontInfo={"FullName": "Test Type1C Wave 1593"},
        charStringsDict=char_strings,
        privateDict={},
    )
    fb.setupHorizontalMetrics({".notdef": (0, 0), "A": (500, 0), "B": (300, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupOS2(
        sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200
    )
    fb.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    fb.setupPost()
    buf = io.BytesIO()
    fb.font.save(buf)
    return bytes(TTFont(io.BytesIO(buf.getvalue())).getTableData("CFF "))


def _embedded_cff_font(
    base_font: str = "MyEmbeddedType1C",
    encoding: str | None = "WinAnsiEncoding",
) -> PDType1CFont:
    cff = CFFFont.from_bytes(_build_minimal_cff_bytes())
    d = COSDictionary()
    d.set_name(_BASE_FONT, base_font)
    if encoding is not None:
        d.set_item(_ENCODING, COSName.get_pdf_name(encoding))
    font = PDType1CFont(d)
    font.set_font_program(cff)
    return font


# ---------- non-embedded Standard 14 (Helvetica) ----------


def _standard14_font(
    base_font: str = "Helvetica",
    encoding: str | None = "WinAnsiEncoding",
) -> PDType1Font:
    d = COSDictionary()
    d.set_name(_BASE_FONT, base_font)
    if encoding is not None:
        d.set_item(_ENCODING, COSName.get_pdf_name(encoding))
    return PDType1Font(d)


# ---------- helpers ----------


def _is_path_command_list(path) -> bool:  # noqa: ANN001
    if not isinstance(path, list):
        return False
    for cmd in path:
        if not isinstance(cmd, tuple) or not cmd:
            return False
        if cmd[0] not in ("moveto", "lineto", "curveto", "closepath"):
            return False
    return True


# ========== embedded Type 1 (/FontFile) ==========


def test_embedded_type1_glyph_path_for_code_A() -> None:
    """Code 65 (WinAnsi 'A') -> the program's non-empty 'A' outline."""
    font = _embedded_type1_font()
    path = font.get_glyph_path(65)
    assert path
    assert _is_path_command_list(path)


def test_embedded_type1_get_path_by_name() -> None:
    """``get_path('A')`` returns the embedded program's outline directly."""
    font = _embedded_type1_font()
    assert font.get_path("A")


def test_embedded_type1_normalized_path_matches_code_path() -> None:
    font = _embedded_type1_font()
    assert font.get_normalized_path(65) == font.get_path_for_code(65)


def test_embedded_type1_empty_glyph_returns_empty_path() -> None:
    """'B' has no outline commands in the stub -> empty path."""
    font = _embedded_type1_font()
    # 'B' is WinAnsi code 66.
    assert font.get_glyph_path(66) == []


def test_embedded_type1_missing_glyph_name_returns_empty() -> None:
    font = _embedded_type1_font()
    assert font.get_path("ZZZnope") == []


def test_embedded_type1_notdef_name_embedded_not_short_circuited() -> None:
    """For an *embedded* font ``.notdef`` is not suppressed — it goes to
    the program, which returns the (empty) ``.notdef`` outline here."""
    font = _embedded_type1_font()
    font._t1 = font.get_font_program()  # force is_embedded heuristic off
    # No descriptor -> is_embedded() False, so .notdef short-circuits.
    assert font.get_path(".notdef") == []


def test_embedded_type1_unmapped_code_returns_empty() -> None:
    """A code with no WinAnsi mapping (0) -> empty path."""
    font = _embedded_type1_font()
    assert font.get_glyph_path(0) == []


def test_embedded_type1_no_dict_encoding_resolves_via_builtin() -> None:
    """No dict /Encoding -> ``get_encoding_typed`` falls through to the
    program's built-in encoding (StandardEncoding), so code 65 still
    resolves to 'A' and draws the program outline."""
    font = _embedded_type1_font(encoding=None)
    assert font.get_path_for_code(65)


# ========== embedded Type1C (/FontFile3, CFF) ==========


def test_embedded_cff_glyph_path_for_code_A() -> None:
    font = _embedded_cff_font()
    path = font.get_glyph_path(65)
    assert path
    assert _is_path_command_list(path)


def test_embedded_cff_get_path_by_name() -> None:
    font = _embedded_cff_font()
    assert font.get_path("A")


def test_embedded_cff_normalized_path_for_code() -> None:
    font = _embedded_cff_font()
    assert font.get_normalized_path(65) == font.get_path_for_code(65)


def test_embedded_cff_missing_glyph_name_returns_empty() -> None:
    font = _embedded_cff_font()
    assert font.get_path("ZZZnope") == []


def test_embedded_cff_notdef_empty_outline() -> None:
    """The CFF ``.notdef`` charstring is the empty ``endchar`` -> []."""
    font = _embedded_cff_font()
    # Embedded (program injected but no descriptor -> not is_embedded);
    # .notdef short-circuits to [].
    assert font.get_path(".notdef") == []


def test_embedded_cff_unmapped_code_returns_empty() -> None:
    font = _embedded_cff_font()
    assert font.get_glyph_path(0) == []


def test_embedded_cff_sfthyphen_rewrites_to_hyphen() -> None:
    """``sfthyphen`` is re-spelled to ``hyphen`` before the lookup. The
    stub CFF lacks both, so the result is empty — but the rewrite must
    not raise."""
    font = _embedded_cff_font()
    assert font.get_path("sfthyphen") == []


def test_embedded_cff_nbspace_without_space_glyph_empty() -> None:
    font = _embedded_cff_font()
    assert font.get_path("nbspace") == []


def test_embedded_cff_code_to_gid_roundtrip() -> None:
    font = _embedded_cff_font()
    # 'A' is GID 1 in the charset [.notdef, A, B].
    assert font.code_to_gid(65) == 1
    assert font.code_to_gid(66) == 2


# ========== non-embedded Standard 14 (Helvetica) substitute ==========


def test_standard14_glyph_path_uses_substitute() -> None:
    font = _standard14_font()
    assert not font.is_embedded()
    assert font.get_glyph_path(65)  # substitute 'A'


def test_standard14_normalized_path_uses_substitute() -> None:
    """Wave 1593: the glyph-cache interface (``get_normalized_path``)
    must reach the substitute outline for a non-embedded Standard 14
    font — previously returned [] (no glyph rendered)."""
    font = _standard14_font()
    path = font.get_normalized_path(65)
    assert path
    assert _is_path_command_list(path)


def test_standard14_get_path_by_name_uses_substitute() -> None:
    """Wave 1593: ``get_path('A')`` on a non-embedded Helvetica draws
    the substitute outline, mirroring upstream's ``genericFont`` branch."""
    font = _standard14_font()
    assert font.get_path("A")


def test_standard14_get_path_for_code_uses_substitute() -> None:
    font = _standard14_font()
    assert font.get_path_for_code(65)


def test_standard14_glyph_path_consistency_across_interfaces() -> None:
    """All three code-keyed entry points agree for a non-embedded core."""
    font = _standard14_font()
    via_glyph = font.get_glyph_path(65)
    via_norm = font.get_normalized_path(65)
    via_for_code = font.get_path_for_code(65)
    assert via_glyph and via_norm and via_for_code
    assert via_norm == via_for_code


def test_standard14_notdef_name_returns_empty() -> None:
    font = _standard14_font()
    assert font.get_path(".notdef") == []


def test_standard14_differences_overrides_name_lookup() -> None:
    """A /Differences encoding remapping code 65 -> 'B' draws the 'B'
    substitute glyph, not 'A'."""
    from pypdfbox.cos import COSArray, COSInteger

    d = COSDictionary()
    d.set_name(_BASE_FONT, "Helvetica")
    enc = COSDictionary()
    enc.set_item(COSName.get_pdf_name("BaseEncoding"),
                 COSName.get_pdf_name("WinAnsiEncoding"))
    diffs = COSArray()
    diffs.add(COSInteger.get(65))
    diffs.add(COSName.get_pdf_name("B"))
    enc.set_item(COSName.get_pdf_name("Differences"), diffs)
    d.set_item(_ENCODING, enc)
    font = PDType1Font(d)
    assert font.code_to_name(65) in ("B", "b")  # differences applied
    # The substitute path for the remapped name is non-empty.
    assert font.get_glyph_path(65)


def test_standard14_symbol_uses_substitute() -> None:
    """A non-embedded Symbol font draws via its own substitute."""
    d = COSDictionary()
    d.set_name(_BASE_FONT, "Symbol")
    font = PDType1Font(d)
    # Symbol code 0x61 -> 'alpha' in SymbolEncoding.
    assert font.get_glyph_path(0x61)


def test_standard14_no_encoding_falls_through_to_default() -> None:
    """No /Encoding at all -> family default StandardEncoding still
    resolves a glyph name for the substitute path."""
    font = _standard14_font(encoding=None)
    assert font.get_glyph_path(65)  # StandardEncoding maps 65 -> 'A'


# ========== non-Standard-14, non-embedded -> always empty ==========


def test_non_standard14_non_embedded_glyph_path_empty() -> None:
    font = _standard14_font(base_font="TotallyCustomFont")
    assert font.get_glyph_path(65) == []


def test_non_standard14_non_embedded_get_path_empty() -> None:
    font = _standard14_font(base_font="TotallyCustomFont")
    assert font.get_path("A") == []


def test_non_standard14_non_embedded_normalized_path_empty() -> None:
    font = _standard14_font(base_font="TotallyCustomFont")
    assert font.get_normalized_path(65) == []


# ========== 1000-upem scaling expectations ==========


def test_type1_font_matrix_is_1000_upem_default() -> None:
    """Type 1 fonts default to the 1000-upem matrix [0.001 0 0 0.001 0 0]."""
    font = _standard14_font()
    matrix = font.get_font_matrix()
    assert matrix == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


def test_embedded_type1_units_per_em_is_1000() -> None:
    font = _embedded_type1_font()
    assert font.get_font_program().units_per_em == 1000


def test_embedded_cff_units_per_em_is_1000() -> None:
    font = _embedded_cff_font()
    assert font.get_units_per_em() == 1000


def test_embedded_type1_outline_coords_in_font_units() -> None:
    """The stub 'A' is drawn in 1000-upem font units; the recorded
    coordinates must be the raw font-unit values (0..700), not pre-scaled
    text-space values."""
    font = _embedded_type1_font()
    path = font.get_glyph_path(65)
    ys = [c[2] for c in path if c[0] in ("moveto", "lineto")]
    assert max(ys) == 700.0  # raw font unit, not 0.7


# ========== fuzz sweep over the WinAnsi code range ==========


@pytest.mark.parametrize("code", list(range(0, 256, 11)))
def test_standard14_path_sweep_never_raises(code: int) -> None:
    """Every code in a coarse sweep yields a valid (possibly empty)
    command list for a non-embedded Helvetica — no exceptions, and the
    glyph-cache and render interfaces agree on emptiness."""
    font = _standard14_font()
    norm = font.get_normalized_path(code)
    glyph = font.get_glyph_path(code)
    assert _is_path_command_list(norm)
    assert _is_path_command_list(glyph)


@pytest.mark.parametrize("code", list(range(0, 256, 17)))
def test_embedded_type1_path_sweep_never_raises(code: int) -> None:
    font = _embedded_type1_font()
    assert _is_path_command_list(font.get_glyph_path(code))
    assert _is_path_command_list(font.get_normalized_path(code))


@pytest.mark.parametrize("code", list(range(0, 256, 17)))
def test_embedded_cff_path_sweep_never_raises(code: int) -> None:
    font = _embedded_cff_font()
    assert _is_path_command_list(font.get_glyph_path(code))
    assert _is_path_command_list(font.get_normalized_path(code))
