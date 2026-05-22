from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.fontbox.type1.type1_font import Type1Font
from pypdfbox.pdmodel.font import PDFontDescriptor, PDType1Font


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


class _StubCharString:
    def __init__(self, width: float, commands: list[tuple]) -> None:
        self.width = width
        self._commands = commands

    def draw(self, pen) -> None:  # noqa: ANN001 - fontTools pen protocol
        for command in self._commands:
            op = command[0]
            if op == "moveTo":
                pen.moveTo(command[1])
            elif op == "lineTo":
                pen.lineTo(command[1])
            elif op == "curveTo":
                pen.curveTo(command[1], command[2], command[3])
            elif op == "closePath":
                pen.closePath()


def _type1_program() -> Type1Font:
    program = Type1Font()
    program._charstrings = {
        ".notdef": _StubCharString(0.0, []),
        "A": _StubCharString(
            500.0,
            [
                ("moveTo", (0.0, -20.0)),
                ("lineTo", (0.0, 700.0)),
                ("lineTo", (120.0, 700.0)),
                ("closePath",),
            ],
        ),
        "f_f": _StubCharString(320.0, [("moveTo", (1.0, 2.0))]),
        "elipsis": _StubCharString(250.0, [("moveTo", (3.0, 4.0))]),
        "curveglyph": _StubCharString(
            600.0,
            [
                ("moveTo", (10.0, -50.0)),
                ("curveTo", (20.0, 40.0), (30.0, 800.0), (40.0, 300.0)),
            ],
        ),
    }
    program._font_matrix = [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    program._units_per_em = 1000
    return program


def _font_with_program(program: Type1Font | None = None) -> PDType1Font:
    font = PDType1Font()
    font.get_cos_object().set_name(_name("BaseFont"), "SyntheticType1")
    font.get_cos_object().set_item(_name("Encoding"), _name("WinAnsiEncoding"))
    font.set_font_program(program or _type1_program())
    return font


def _differences_encoding(code: int, glyph_name: str) -> COSDictionary:
    encoding = COSDictionary()
    encoding.set_item(_name("Type"), _name("Encoding"))
    encoding.set_item(_name("BaseEncoding"), _name("WinAnsiEncoding"))
    encoding.set_item(
        _name("Differences"),
        COSArray([COSInteger.get(code), _name(glyph_name)]),
    )
    return encoding


def test_get_name_in_font_uses_ligature_alt_name_for_substitute_program() -> None:
    font = _font_with_program()

    assert font.get_name_in_font("ff") == "f_f"
    assert font.has_glyph("ff") is True
    assert font.get_width_from_font(0x00) == PDType1Font.SUBSTITUTE_NOTDEF_WIDTH


def test_get_name_in_font_uses_arial_ellipsis_misspelling() -> None:
    font = _font_with_program()

    assert font.get_name_in_font("ellipsis") == "elipsis"
    assert font.has_glyph("ellipsis") is True
    assert font.get_path("ellipsis") == [("moveto", 3.0, 4.0)]


def test_get_name_in_font_returns_notdef_when_program_lacks_candidates() -> None:
    font = _font_with_program()

    assert font.get_name_in_font("missingGlyph") == ".notdef"
    assert font.has_glyph("missingGlyph") is False
    assert font.get_path("missingGlyph") == []


def test_embedded_font_trusts_requested_glyph_name_before_alt_lookup() -> None:
    font = _font_with_program()
    descriptor = PDFontDescriptor()
    descriptor.set_font_file(COSStream())
    font.set_font_descriptor(descriptor)

    assert font.is_embedded() is True
    assert font.get_name_in_font("ff") == "ff"
    assert font.has_glyph("ff") is False


def test_get_path_for_code_and_normalized_path_use_encoding_fallback() -> None:
    font = _font_with_program()
    font.get_cos_object().set_item(_name("Encoding"), _differences_encoding(65, "A"))

    assert font.get_path_for_code(65)[0] == ("moveto", 0.0, -20.0)
    assert font.get_normalized_path_for_code(65)[-1] == ("closepath",)
    assert font.get_path_for_code(66) == []
    assert font.get_normalized_path_for_code(66) == []


def test_get_height_extracts_line_and_curve_y_coordinates() -> None:
    font = _font_with_program()
    font.get_cos_object().set_item(
        _name("Encoding"),
        _differences_encoding(65, "curveglyph"),
    )

    assert font.get_height(65) == 850.0


def test_get_height_returns_zero_for_empty_path_and_unmapped_code() -> None:
    font = _font_with_program()
    font.get_cos_object().set_item(_name("Encoding"), _differences_encoding(65, "B"))

    assert font.get_height(65) == 0.0
    assert font.get_height(0) == 0.0


def test_program_width_ignores_non_positive_units_per_em() -> None:
    program = _type1_program()
    program._units_per_em = 0
    font = _font_with_program(program)

    assert font.get_glyph_width(65) == 0.0


def test_get_type1_font_caches_absent_descriptor_as_failed_lookup() -> None:
    font = PDType1Font()

    assert font.get_type1_font() is None
    assert font._t1 is False
    assert font.get_font_program() is None


def test_read_code_walks_buffer_and_terminates_at_eof() -> None:
    font = PDType1Font()
    data = b"\x00\xff"

    assert font.read_code(data, 0) == (0, 1)
    assert font.read_code(data, 1) == (0xFF, 1)
    # Past end of buffer returns (0, 0) — the caller terminates.
    assert font.read_code(data, 2) == (0, 0)
