from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.pdmodel.font import PDFontDescriptor, PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_font_descriptor import FLAG_SYMBOLIC

# Re-use the only TTF fixture currently shipped with the repo so the
# parity tests do not need to bundle a second copy.
_TTF_FIXTURE = (
    Path(__file__).parent.parent.parent
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _ttf_bytes() -> bytes:
    return _TTF_FIXTURE.read_bytes()


def _load_ttf() -> TrueTypeFont:
    return TrueTypeFont.from_bytes(_ttf_bytes())


def _font_with_embedded_ttf(*, symbolic: bool = False) -> PDTrueTypeFont:
    """Build a PDTrueTypeFont whose ``/FontFile2`` is the Liberation Sans
    fixture. ``symbolic=True`` flips bit 3 of ``/Flags`` so we exercise
    the symbolic ``code → gid`` shortcut."""
    font = PDTrueTypeFont()
    fd = PDFontDescriptor()
    if symbolic:
        fd.set_flags(FLAG_SYMBOLIC)
    stream = COSStream()
    stream.set_raw_data(_ttf_bytes())
    fd.set_font_file2(stream)
    font.set_font_descriptor(fd)
    # Inject the parsed TTF directly so tests don't pay parse overhead
    # twice — and so set_true_type_font's wiring is exercised too.
    font.set_true_type_font(_load_ttf())
    return font


# ---------- /BaseFont round-trip (get_name + get_base_font) ----------


def test_get_name_reads_base_font() -> None:
    font = PDTrueTypeFont()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "MyTrueTypeFont")
    assert font.get_name() == "MyTrueTypeFont"


def test_get_base_font_aliases_get_name() -> None:
    font = PDTrueTypeFont()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica-Bold")
    assert font.get_base_font() == "Helvetica-Bold"
    assert font.get_base_font() == font.get_name()


def test_get_name_none_when_base_font_absent() -> None:
    assert PDTrueTypeFont().get_name() is None
    assert PDTrueTypeFont().get_base_font() is None


# ---------- is_embedded ----------


def test_is_embedded_true_when_font_file2_present() -> None:
    font = PDTrueTypeFont()
    fd = PDFontDescriptor()
    fd.set_font_file2(COSStream())
    font.set_font_descriptor(fd)
    assert font.is_embedded() is True


def test_is_embedded_false_when_no_descriptor() -> None:
    assert PDTrueTypeFont().is_embedded() is False


def test_is_embedded_false_when_descriptor_lacks_font_file() -> None:
    font = PDTrueTypeFont()
    font.set_font_descriptor(PDFontDescriptor())
    assert font.is_embedded() is False


# ---------- is_damaged ----------


def test_is_damaged_default_false() -> None:
    assert PDTrueTypeFont().is_damaged() is False


# ---------- get_displacement ----------


def test_get_displacement_horizontal_only() -> None:
    """Displacement of a simple font is always ``(width/1000, 0)``."""
    font = _font_with_embedded_ttf()
    code = ord("A")
    width = font.get_glyph_width(code)
    tx, ty = font.get_displacement(code)
    assert ty == 0.0
    assert tx == width / 1000.0


def test_get_displacement_unknown_code_zero() -> None:
    """No /Widths and no embedded TTF → displacement is (0, 0)."""
    tx, ty = PDTrueTypeFont().get_displacement(ord("A"))
    assert (tx, ty) == (0.0, 0.0)


# ---------- code_to_gid ----------


def test_code_to_gid_symbolic_returns_code_when_no_ttf() -> None:
    """Symbolic font + no embedded TTF: the code IS the GID."""
    font = PDTrueTypeFont()
    fd = PDFontDescriptor()
    fd.set_flags(FLAG_SYMBOLIC)
    font.set_font_descriptor(fd)
    assert font.code_to_gid(42) == 42


def test_code_to_gid_nonsymbolic_zero_when_no_ttf() -> None:
    """Nonsymbolic font + no embedded TTF: nothing to consult → 0."""
    font = PDTrueTypeFont()
    font.set_font_descriptor(PDFontDescriptor())
    assert font.code_to_gid(42) == 0


def test_code_to_gid_symbolic_with_ttf_uses_cmap() -> None:
    """Symbolic font + embedded TTF: routes through the cmap directly
    (no encoding lookup). ASCII 'A' must resolve to a non-zero glyph
    in Liberation Sans."""
    font = _font_with_embedded_ttf(symbolic=True)
    assert font.code_to_gid(ord("A")) > 0


# ---------- get_true_type_font ----------


def test_get_true_type_font_returns_injected_program() -> None:
    """``set_true_type_font`` injection round-trips through the public
    accessor. Mirrors PDFBox where ``getTrueTypeFont`` exposes the
    parsed program."""
    ttf = _load_ttf()
    font = PDTrueTypeFont()
    font.set_true_type_font(ttf)
    assert font.get_true_type_font() is ttf


def test_get_true_type_font_none_when_not_embedded() -> None:
    assert PDTrueTypeFont().get_true_type_font() is None


# ---------- get_glyph_name_for_code ----------


def test_get_glyph_name_for_code_returns_none_without_encoding() -> None:
    assert PDTrueTypeFont().get_glyph_name_for_code(65) is None


def test_get_glyph_name_for_code_via_winansi() -> None:
    """A nonsymbolic TrueType with /Encoding /WinAnsiEncoding maps code
    65 to the glyph name "A"."""
    font = PDTrueTypeFont()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    assert font.get_glyph_name_for_code(65) == "A"


# ---------- get_path / get_glyph_path ----------


def test_get_path_returns_recorded_segments() -> None:
    font = _font_with_embedded_ttf()
    path = font.get_path("A")
    assert path, "expected at least one segment for glyph 'A'"
    assert path[0][0] == "moveTo"


def test_get_path_unknown_glyph_returns_empty() -> None:
    font = _font_with_embedded_ttf()
    assert font.get_path("definitely-not-a-real-glyph") == []


def test_get_glyph_path_via_winansi_encoding() -> None:
    font = _font_with_embedded_ttf()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    path = font.get_glyph_path(ord("A"))
    assert path, "expected a glyph path for ASCII 'A' under WinAnsi"


def test_get_glyph_path_no_program_empty() -> None:
    assert PDTrueTypeFont().get_glyph_path(65) == []


# ---------- get_height ----------


def test_get_height_from_glyf_table() -> None:
    """Liberation Sans 'A' has a positive bounding-box height."""
    font = _font_with_embedded_ttf()
    height = font.get_height(ord("A"))
    assert height > 0.0


def test_get_height_zero_when_no_program() -> None:
    assert PDTrueTypeFont().get_height(65) == 0.0


# ---------- get_average_font_width (inherited) ----------


def test_get_average_font_width_ignores_zero_widths() -> None:
    """Inherited from PDSimpleFont but exercised on a TrueType for
    parity. Mean is over positive entries only."""
    from pypdfbox.cos import COSArray, COSInteger

    font = PDTrueTypeFont()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Widths"),
        COSArray(
            [
                COSInteger.get(0),
                COSInteger.get(500),
                COSInteger.get(1000),
                COSInteger.get(0),
            ]
        ),
    )
    assert font.get_average_font_width() == 750.0


def test_get_average_font_width_zero_when_widths_absent() -> None:
    assert PDTrueTypeFont().get_average_font_width() == 0.0


# ---------- is_symbolic (inherited) ----------


def test_is_symbolic_false_without_descriptor() -> None:
    assert PDTrueTypeFont().is_symbolic() is False


def test_is_symbolic_true_when_flags_bit_set() -> None:
    font = PDTrueTypeFont()
    fd = PDFontDescriptor()
    fd.set_flags(FLAG_SYMBOLIC)
    font.set_font_descriptor(fd)
    assert font.is_symbolic() is True


# ---------- subtype guard ----------


def test_default_subtype_is_truetype() -> None:
    font = PDTrueTypeFont()
    assert (
        font.get_cos_object().get_name(COSName.get_pdf_name("Subtype")) == "TrueType"
    )


# ---------- COSDictionary round-trip via parser path ----------


def test_round_trip_via_raw_dict() -> None:
    """Mirrors the parser path: build a /Type /Font /Subtype /TrueType dict
    by hand and wrap it. Every accessor must read what was written."""
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "TrueType")  # type: ignore[attr-defined]
    raw.set_name(COSName.get_pdf_name("BaseFont"), "ABCDEF+LiberationSans")
    font = PDTrueTypeFont(raw)
    assert font.get_name() == "ABCDEF+LiberationSans"
    assert font.get_base_font() == "ABCDEF+LiberationSans"
    assert font.is_subset() is True
    assert font.is_embedded() is False
