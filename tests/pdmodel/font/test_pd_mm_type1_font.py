"""Hand-written tests for :class:`PDMMType1Font`.

PDMMType1Font is a *marker subclass* of :class:`PDType1Font` — it exists
purely to distinguish ``/Subtype /MMType1`` font dictionaries from regular
``/Subtype /Type1`` ones during factory dispatch (PDF 32000-1 §9.6.2.3).
The class adds no behaviour of its own; everything is inherited from
``PDType1Font``. These tests pin down that contract and exercise the
inherited surface area through the MM subclass to catch any future
accidental override.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.fontbox.type1.type1_font import Type1Font
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_mm_type1_font import PDMMType1Font
from pypdfbox.pdmodel.font.pd_simple_font import PDSimpleFont
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

_BASEFONT = COSName.get_pdf_name("BaseFont")
_ENCODING = COSName.get_pdf_name("Encoding")
_FIRSTCHAR = COSName.get_pdf_name("FirstChar")
_LASTCHAR = COSName.get_pdf_name("LastChar")
_WIDTHS = COSName.get_pdf_name("Widths")
_WIN_ANSI = COSName.get_pdf_name("WinAnsiEncoding")


# ---------- helpers ----------


def _stub_type1_program() -> Type1Font:
    """Build a stub :class:`Type1Font` carrying advance widths for
    ``A`` (500) and ``B`` (300). No outlines — we only exercise the
    width path here.
    """
    program = Type1Font()

    class _StubCharString:
        def __init__(self, width: float) -> None:
            self.width = width

        def draw(self, pen) -> None:  # noqa: ANN001
            return None

    program._charstrings = {
        ".notdef": _StubCharString(0.0),
        "A": _StubCharString(500.0),
        "B": _StubCharString(300.0),
    }
    program._font_matrix = [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    program._units_per_em = 1000
    return program


def _bare_mm_font(base_font: str = "MyMM") -> PDMMType1Font:
    raw = COSDictionary()
    raw.set_name(_BASEFONT, base_font)
    raw.set_item(_ENCODING, _WIN_ANSI)
    return PDMMType1Font(raw)


# ---------- subtype + inheritance ----------


def test_sub_type_constant_is_mm_type1() -> None:
    assert PDMMType1Font.SUB_TYPE == "MMType1"


def test_default_constructor_writes_subtype_to_dict() -> None:
    font = PDMMType1Font()
    cos = font.get_cos_object()
    assert cos.get_name(COSName.SUBTYPE) == "MMType1"  # type: ignore[attr-defined]
    assert cos.get_name(COSName.TYPE) == "Font"  # type: ignore[attr-defined]


def test_get_subtype_returns_mm_type1() -> None:
    font = PDMMType1Font()
    assert font.get_subtype() == "MMType1"


def test_inherits_from_pd_type1_font() -> None:
    assert issubclass(PDMMType1Font, PDType1Font)


def test_inherits_from_pd_simple_font_via_type1() -> None:
    """PDMMType1Font should still be a PDSimpleFont — the MRO must
    preserve the upstream hierarchy chain
    PDMMType1Font -> PDType1Font -> PDSimpleFont -> PDFont.
    """
    assert issubclass(PDMMType1Font, PDSimpleFont)


def test_does_not_define_extra_methods_beyond_type1() -> None:
    """Marker-subclass guard: PDMMType1Font must not introduce its own
    methods. Anything the upstream Java class wouldn't have is a sign
    we've drifted from the marker contract.
    """
    own = {
        name
        for name in vars(PDMMType1Font)
        if not name.startswith("_") and callable(getattr(PDMMType1Font, name))
    }
    assert own == set(), f"PDMMType1Font defines extra methods: {sorted(own)}"


# ---------- preserved-from-Type1 surface ----------


def test_constructor_accepts_existing_dict_without_overwriting_subtype() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "MMType1")  # type: ignore[attr-defined]
    raw.set_name(_BASEFONT, "MyriadMM")
    font = PDMMType1Font(raw)
    assert font.get_cos_object() is raw
    assert font.get_subtype() == "MMType1"
    assert font.get_name() == "MyriadMM"


def test_get_base_font_inherited_from_type1() -> None:
    font = _bare_mm_font("MyriadMM_366_BD_700_TT_400_")
    # PDType1Font.get_base_font is an alias for get_name.
    assert font.get_base_font() == "MyriadMM_366_BD_700_TT_400_"


def test_get_glyph_width_uses_inherited_program_lookup() -> None:
    font = _bare_mm_font()
    font.set_font_program(_stub_type1_program())
    assert font.get_glyph_width(65) == 500.0  # 'A'
    assert font.get_glyph_width(66) == 300.0  # 'B'


def test_widths_array_overrides_program_widths_for_mm() -> None:
    """The same /Widths-wins-over-program rule from PDType1Font applies."""
    raw = COSDictionary()
    raw.set_name(_BASEFONT, "MyMM")
    raw.set_item(_ENCODING, _WIN_ANSI)
    raw.set_int(_FIRSTCHAR, 65)
    raw.set_int(_LASTCHAR, 65)
    widths = COSArray()
    widths.add(COSInteger(777))
    raw.set_item(_WIDTHS, widths)
    font = PDMMType1Font(raw)
    font.set_font_program(_stub_type1_program())
    assert font.get_glyph_width(65) == 777.0  # /Widths wins
    assert font.get_glyph_width(66) == 300.0  # program fallback


def test_no_program_no_widths_returns_zero() -> None:
    font = _bare_mm_font()
    assert font.get_glyph_width(65) == 0.0


def test_get_glyph_path_no_program_returns_empty() -> None:
    font = _bare_mm_font()
    assert font.get_glyph_path(65) == []


def test_is_embedded_false_without_descriptor() -> None:
    font = _bare_mm_font()
    assert font.is_embedded() is False


def test_is_damaged_false_without_descriptor() -> None:
    font = _bare_mm_font()
    assert font.is_damaged() is False


def test_get_displacement_horizontal_writing_mode() -> None:
    font = _bare_mm_font()
    font.set_font_program(_stub_type1_program())
    dx, dy = font.get_displacement(65)
    assert dx == pytest.approx(0.5)  # 500 / 1000
    assert dy == 0.0


def test_set_font_program_none_clears_cache() -> None:
    font = _bare_mm_font()
    font.set_font_program(_stub_type1_program())
    assert font.get_glyph_width(65) == 500.0
    font.set_font_program(None)
    assert font.get_glyph_width(65) == 0.0


# ---------- wave 1306: /Subtype /MMType1 + /FontFile delegation ----------
#
# These tests pin the upstream-parity contract that the CHANGES.md note
# updated in wave 1306 records: PDMMType1Font is a marker subclass and
# the embedded ``/FontFile`` is parsed via the Type 1 path. PDFBox does
# NOT interpolate multiple-master design axes either — it delegates to
# ``PDType1Font`` for ``getWidth`` and ``getPath`` (see
# ``PDMMType1Font.java`` upstream, which only forwards both constructors
# to ``super``). The "deferred" language in CHANGES.md was misleading;
# pypdfbox matches upstream behavior bit for bit.


def _path_outlined_type1_program() -> Type1Font:
    """Build a stub :class:`Type1Font` whose charstrings expose a real
    outline (one ``moveto`` + one ``lineto`` + ``closepath``) so we can
    pin ``get_glyph_path`` returns the Type 1 outline, not just ``[]``.
    """
    program = Type1Font()

    class _OutlinedCharString:
        def __init__(self, width: float, commands: list[tuple]) -> None:
            self.width = width
            self._commands = commands

        def draw(self, pen) -> None:  # noqa: ANN001
            for cmd in self._commands:
                op = cmd[0]
                if op == "moveto":
                    pen.moveTo((cmd[1], cmd[2]))
                elif op == "lineto":
                    pen.lineTo((cmd[1], cmd[2]))
                elif op == "closepath":
                    pen.closePath()

    program._charstrings = {
        ".notdef": _OutlinedCharString(0.0, []),
        "A": _OutlinedCharString(
            500.0,
            [
                ("moveto", 0.0, 0.0),
                ("lineto", 500.0, 0.0),
                ("lineto", 500.0, 700.0),
                ("lineto", 0.0, 700.0),
                ("closepath",),
            ],
        ),
    }
    program._font_matrix = [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    program._units_per_em = 1000
    return program


def _mm_font_with_font_file_descriptor() -> PDMMType1Font:
    """Build a PDMMType1Font whose dict declares ``/Subtype /MMType1``
    and carries a ``/FontDescriptor`` with a real ``/FontFile`` stream
    entry — mirroring the on-disk shape of a multiple-master PDF font
    object per PDF 32000-1 §9.6.2.3 + §9.8.

    The /FontFile body is a placeholder (one byte) — the parsed program
    is injected via :meth:`set_font_program` so the test doesn't depend
    on a real Type 1 binary fixture. This still exercises the marker
    subclass contract: construction with the MM dict shape succeeds and
    the inherited Type 1 lookup path returns widths + outlines unchanged.
    """
    # /FontFile stream — declared but its parsed contents are stubbed out
    # via set_font_program so we can pin glyph data deterministically.
    font_file_stream = COSStream()
    with font_file_stream.create_output_stream() as out:
        out.write(b"\x00")
    font_file_pd = PDStream(font_file_stream)

    descriptor = PDFontDescriptor()
    descriptor.set_font_file(font_file_pd)
    descriptor.set_font_name("MyriadMM_366_BD_700_TT_400_")

    raw = COSDictionary()
    raw.set_name(COSName.TYPE, "Font")  # type: ignore[attr-defined]
    raw.set_name(COSName.SUBTYPE, "MMType1")  # type: ignore[attr-defined]
    raw.set_name(_BASEFONT, "MyriadMM_366_BD_700_TT_400_")
    raw.set_item(_ENCODING, _WIN_ANSI)
    raw.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )

    return PDMMType1Font(raw)


def test_constructed_from_mmtype1_dict_with_font_file_descriptor() -> None:
    """Building a PDMMType1Font from a dict with ``/Subtype /MMType1``
    plus a ``/FontDescriptor`` carrying a ``/FontFile`` stream succeeds
    and exposes the descriptor through the inherited PDFont path."""
    font = _mm_font_with_font_file_descriptor()
    assert font.get_subtype() == "MMType1"
    assert font.get_name() == "MyriadMM_366_BD_700_TT_400_"
    descriptor = font.get_font_descriptor()
    assert descriptor is not None
    # /FontFile is the Type 1 slot — PDFBox routes MMType1 through the
    # same descriptor key, no MM-specific stream slot exists.
    assert descriptor.has_font_file() is True
    assert descriptor.get_font_file() is not None


def test_get_glyph_width_delegates_to_type1_path() -> None:
    """``get_glyph_width(code)`` on a PDMMType1Font with an attached
    Type 1 program returns the program's advance width — confirming the
    marker subclass forwards to :meth:`PDType1Font.get_glyph_width`
    without any MM-specific design-vector interpolation (upstream parity:
    Java ``PDMMType1Font`` has no ``getWidth`` override)."""
    font = _mm_font_with_font_file_descriptor()
    font.set_font_program(_path_outlined_type1_program())
    # 'A' = 0x41 = 65 → encoded via WinAnsi → "A" in the program.
    assert font.get_glyph_width(65) == 500.0


def test_get_glyph_path_delegates_to_type1_path() -> None:
    """``get_glyph_path(code)`` on a PDMMType1Font returns the Type 1
    outline for the encoding-resolved glyph name. No MM design-vector
    interpolation is performed — matches upstream PDFBox which has no
    ``getPath`` override on ``PDMMType1Font``."""
    font = _mm_font_with_font_file_descriptor()
    font.set_font_program(_path_outlined_type1_program())
    path = font.get_glyph_path(65)  # WinAnsi 0x41 → "A"
    # The stub's "A" charstring draws a 500x700 box.
    assert path != []
    # First op is a moveto at the origin; last op closes the subpath.
    assert path[0][0] == "moveto"
    assert path[-1][0] == "closepath"
    # Pin the full command stream for regression coverage.
    expected_ops = ["moveto", "lineto", "lineto", "lineto", "closepath"]
    assert [cmd[0] for cmd in path] == expected_ops
