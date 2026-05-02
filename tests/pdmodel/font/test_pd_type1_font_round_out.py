"""Round-out tests for ``PDType1Font`` — Wave 199.

Covers the four small upstream gaps closed in this wave:

* Standard 14 ``BaseFont`` string constants (HELVETICA, HELVETICA_BOLD, ...)
  exposed at class level so callers can spell ``PDType1Font.HELVETICA``
  without reaching into ``Standard14Fonts``.
* ``get_path(name)`` ``.notdef`` short-circuit for non-embedded fonts
  (PDFBOX-2421) and routing through ``get_name_in_font`` so ligature
  fallbacks reach the program lookup.
* ``get_path_for_code(code)`` / ``get_normalized_path_for_code(code)``
  encoding-keyed path lookups.
* ``get_width_from_font(code)`` substitute-``.notdef`` sentinel
  (PDFBOX-1900, returns 250) and program-advance fallback.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.fontbox.type1.type1_font import Type1Font
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font


# ---------- helpers (mirror the in-tree minimal Type1 program) ----------


def _stub_type1_program(extra: dict | None = None) -> Type1Font:
    """Build a tiny in-memory Type 1 program with ``.notdef``, ``A`` and
    ``B``. The structure matches ``test_type1_cff_glyph._build_minimal_type1_program``.
    """
    program = Type1Font()

    class _Stub:
        def __init__(self, width: float, commands: list) -> None:
            self.width = width
            self._commands = commands

        def draw(self, pen) -> None:  # noqa: ANN001 — pen protocol
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
    if extra:
        for name, (width, commands) in extra.items():
            glyphs[name] = _Stub(width, commands)

    program._charstrings = glyphs
    program._font_matrix = [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    program._units_per_em = 1000
    return program


def _font_with_program(
    program: Type1Font | None,
    base_font: str = "MyEmbeddedType1",
    encoding: str | None = "WinAnsiEncoding",
) -> PDType1Font:
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), base_font)
    if encoding is not None:
        font_dict.set_item(
            COSName.get_pdf_name("Encoding"), COSName.get_pdf_name(encoding)
        )
    font = PDType1Font(font_dict)
    if program is not None:
        font.set_font_program(program)
    return font


# ---------- Standard 14 BaseFont constants ----------


def test_helvetica_family_constants() -> None:
    """Helvetica family constants match upstream FontName.getName()."""
    assert PDType1Font.HELVETICA == "Helvetica"
    assert PDType1Font.HELVETICA_BOLD == "Helvetica-Bold"
    assert PDType1Font.HELVETICA_OBLIQUE == "Helvetica-Oblique"
    assert PDType1Font.HELVETICA_BOLD_OBLIQUE == "Helvetica-BoldOblique"


def test_times_family_constants() -> None:
    """Times family constants match upstream FontName.getName()."""
    assert PDType1Font.TIMES_ROMAN == "Times-Roman"
    assert PDType1Font.TIMES_BOLD == "Times-Bold"
    assert PDType1Font.TIMES_ITALIC == "Times-Italic"
    assert PDType1Font.TIMES_BOLD_ITALIC == "Times-BoldItalic"


def test_courier_family_constants() -> None:
    """Courier family constants match upstream FontName.getName()."""
    assert PDType1Font.COURIER == "Courier"
    assert PDType1Font.COURIER_BOLD == "Courier-Bold"
    assert PDType1Font.COURIER_OBLIQUE == "Courier-Oblique"
    assert PDType1Font.COURIER_BOLD_OBLIQUE == "Courier-BoldOblique"


def test_symbol_and_dingbats_constants() -> None:
    """Symbol and ZapfDingbats constants match upstream FontName.getName()."""
    assert PDType1Font.SYMBOL == "Symbol"
    assert PDType1Font.ZAPF_DINGBATS == "ZapfDingbats"


def test_standard_14_constants_resolve_to_metrics() -> None:
    """Each canonical constant is recognised by ``get_standard_14_font_metrics``."""
    for name in (
        PDType1Font.HELVETICA,
        PDType1Font.HELVETICA_BOLD,
        PDType1Font.TIMES_ROMAN,
        PDType1Font.COURIER,
        PDType1Font.SYMBOL,
        PDType1Font.ZAPF_DINGBATS,
    ):
        font = PDType1Font()
        font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), name)
        assert font.get_standard_14_font_metrics() is not None


# ---------- SUBSTITUTE_NOTDEF_WIDTH constant ----------


def test_substitute_notdef_width_constant() -> None:
    """``SUBSTITUTE_NOTDEF_WIDTH`` is the 250.0 sentinel from PDFBOX-1900."""
    assert PDType1Font.SUBSTITUTE_NOTDEF_WIDTH == 250.0


# ---------- get_path(name) — .notdef short-circuit / get_name_in_font routing ----------


def test_get_path_notdef_returns_empty_for_non_embedded_font() -> None:
    """Acrobat does not draw ``.notdef`` for substituted Type 1 fonts
    (PDFBOX-2421). When the font has no /FontFile, ``.notdef`` always
    returns an empty path — even if a program with a ``.notdef`` glyph
    is injected."""
    program = _stub_type1_program()
    font = _font_with_program(program)
    # is_embedded is False (no /FontFile descriptor) so .notdef short-circuits.
    assert font.is_embedded() is False
    assert font.get_path(".notdef") == []


def test_get_path_named_glyph_returns_program_path() -> None:
    """``get_path(name)`` returns the embedded program's outline."""
    program = _stub_type1_program()
    font = _font_with_program(program)
    path = font.get_path("A")
    assert path[0] == ("moveto", 0.0, 0.0)
    assert path[-1] == ("closepath",)


def test_get_path_missing_glyph_returns_empty() -> None:
    """``get_path`` returns ``[]`` when the program lacks the glyph."""
    program = _stub_type1_program()
    font = _font_with_program(program)
    assert font.get_path("ZZZ") == []


def test_get_path_routes_through_get_name_in_font_for_alt_names() -> None:
    """Ligature fallback: when ``ff`` is missing but ``f_f`` exists,
    ``get_path('ff')`` finds the path via ALT_NAMES remapping."""
    program = _stub_type1_program(
        extra={
            "f_f": (
                400.0,
                [
                    ("moveTo", (0.0, 0.0)),
                    ("lineTo", (200.0, 700.0)),
                    ("closePath",),
                ],
            )
        }
    )
    font = _font_with_program(program)
    # The program does not have "ff", but it does have "f_f".
    assert program.has_glyph("f_f")
    assert not program.has_glyph("ff")
    path = font.get_path("ff")
    # Path resolved via ALT_NAMES to f_f.
    assert path[0] == ("moveto", 0.0, 0.0)
    assert path[-1] == ("closepath",)


def test_get_path_no_program_returns_empty() -> None:
    """No injected program → ``get_path`` returns ``[]`` for any name."""
    assert PDType1Font().get_path("A") == []


# ---------- get_path_for_code(code) ----------


def test_get_path_for_code_uses_encoding() -> None:
    """``get_path_for_code(65)`` resolves through WinAnsi to ``A``."""
    program = _stub_type1_program()
    font = _font_with_program(program)
    path = font.get_path_for_code(65)
    assert path[0] == ("moveto", 0.0, 0.0)


def test_get_path_for_code_returns_empty_when_no_encoding() -> None:
    """No /Encoding → ``get_path_for_code`` returns ``[]``."""
    program = _stub_type1_program()
    font = _font_with_program(program, encoding=None)
    assert font.get_encoding_typed() is None
    assert font.get_path_for_code(65) == []


def test_get_path_for_code_returns_empty_for_unmapped_code() -> None:
    """Code that maps to ``.notdef`` returns ``[]`` (since not embedded)."""
    program = _stub_type1_program()
    font = _font_with_program(program)
    # Code 0x00 in WinAnsi → ".notdef" → short-circuits to [].
    assert font.get_path_for_code(0) == []


# ---------- get_normalized_path_for_code(code) ----------


def test_get_normalized_path_falls_back_to_notdef() -> None:
    """When a code maps to a glyph not present in the program, the
    normalized lookup falls back to ``.notdef``. For non-embedded fonts
    that fallback is itself ``[]`` (matches upstream's "no path drawn"
    behaviour for substituted Type 1 fonts)."""
    program = _stub_type1_program()
    font = _font_with_program(program)
    # Code 90 ('Z' in WinAnsi) — not in the stub program.
    assert font.get_path_for_code(90) == []
    assert font.get_normalized_path_for_code(90) == []


def test_get_normalized_path_returns_main_path_when_resolvable() -> None:
    """When the primary lookup succeeds, the normalized lookup returns
    that path verbatim (no .notdef fallback invoked)."""
    program = _stub_type1_program()
    font = _font_with_program(program)
    primary = font.get_path_for_code(65)
    normalized = font.get_normalized_path_for_code(65)
    assert primary == normalized
    assert primary  # non-empty


# ---------- get_width_from_font(code) ----------


def test_get_width_from_font_uses_program_advance() -> None:
    """For an injected program, ``get_width_from_font`` returns the
    program's advance — bypassing /Widths."""
    program = _stub_type1_program()
    font = _font_with_program(program)
    assert font.get_width_from_font(65) == 500.0  # 'A'
    assert font.get_width_from_font(66) == 300.0  # 'B'


def test_get_width_from_font_substitute_notdef_returns_250() -> None:
    """PDFBOX-1900: a substitute (non-embedded) font's ``.notdef`` advance
    is meaningless, so a fixed 250 sentinel is returned instead."""
    font = PDType1Font()
    # No descriptor → not embedded; no /Encoding, but code_to_name will
    # return ".notdef" through the encoding-null fallback.
    assert font.is_embedded() is False
    assert font.get_width_from_font(0) == PDType1Font.SUBSTITUTE_NOTDEF_WIDTH


def test_get_width_from_font_zero_when_no_program_and_not_standard_14() -> None:
    """Non-embedded, non-Standard-14 font with no program returns 0.0
    for codes that map to a real (non-notdef) glyph name."""
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "MyCustomFont")
    font_dict.set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    font = PDType1Font(font_dict)
    # Code 65 maps to 'A' (not notdef) — no program, no AFM → 0.0.
    assert font.get_width_from_font(65) == 0.0


def test_get_width_from_font_standard_14_falls_back_to_afm() -> None:
    """Standard 14 base font with no embedded program → AFM fallback."""
    font_dict = COSDictionary()
    font_dict.set_name(
        COSName.get_pdf_name("BaseFont"), PDType1Font.HELVETICA
    )
    font_dict.set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    font = PDType1Font(font_dict)
    # Helvetica 'A' AFM advance is 667 (well-known).
    assert font.get_width_from_font(65) > 0.0
