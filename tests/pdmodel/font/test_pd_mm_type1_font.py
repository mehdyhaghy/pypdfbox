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

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.fontbox.type1.type1_font import Type1Font
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
