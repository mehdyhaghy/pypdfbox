"""Parity tests for ``PDType1Font`` upstream-named accessors.

Companion to :mod:`tests.pdmodel.font.test_pd_simple_font_parity`. These
exercise the surface that ``org.apache.pdfbox.pdmodel.font.PDType1Font``
exposes on top of ``PDSimpleFont`` — the alias accessors
(``getBaseFont`` / ``getFontProgram`` / ``getGlyphNameForCode`` /
``getPath``), the embed/damage probes, the displacement helper, the
average-width fallback, and the Standard 14 AFM lookup.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.font import PDFontDescriptor, PDType1Font
from pypdfbox.pdmodel.font.afm_loader import AfmMetrics

_BASE_FONT = COSName.get_pdf_name("BaseFont")
_ENCODING = COSName.get_pdf_name("Encoding")
_DIFFERENCES = COSName.get_pdf_name("Differences")
_FIRST_CHAR = COSName.get_pdf_name("FirstChar")
_LAST_CHAR = COSName.get_pdf_name("LastChar")
_WIDTHS = COSName.get_pdf_name("Widths")


# ---------- get_name / get_base_font alias ----------


def test_get_name_returns_base_font_value() -> None:
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    assert font.get_name() == "Helvetica"


def test_get_base_font_aliases_get_name() -> None:
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Times-BoldItalic")
    assert font.get_base_font() == "Times-BoldItalic"
    assert font.get_base_font() == font.get_name()


def test_get_base_font_none_when_absent() -> None:
    assert PDType1Font().get_base_font() is None


# ---------- is_embedded ----------


def test_is_embedded_false_when_no_descriptor() -> None:
    assert PDType1Font().is_embedded() is False


def test_is_embedded_false_when_descriptor_has_no_font_file() -> None:
    font = PDType1Font()
    font.set_font_descriptor(PDFontDescriptor())
    assert font.is_embedded() is False


def test_is_embedded_true_when_font_file_present() -> None:
    font = PDType1Font()
    fd = PDFontDescriptor()
    # An empty COSStream is enough — is_embedded only checks for presence.
    fd.set_font_file(COSStream())
    font.set_font_descriptor(fd)
    assert font.is_embedded() is True


def test_is_embedded_true_when_font_file3_present() -> None:
    font = PDType1Font()
    fd = PDFontDescriptor()
    fd.set_font_file3(COSStream())
    font.set_font_descriptor(fd)
    assert font.is_embedded() is True


# ---------- is_damaged ----------


def test_is_damaged_false_when_not_embedded() -> None:
    # No /FontFile = nothing to parse, nothing to be damaged.
    assert PDType1Font().is_damaged() is False


def test_is_damaged_true_when_font_file_unparseable() -> None:
    font = PDType1Font()
    fd = PDFontDescriptor()
    bogus = COSStream()
    bogus.set_data(b"not a valid Type 1 PostScript program")
    fd.set_font_file(bogus)
    font.set_font_descriptor(fd)
    assert font.is_damaged() is True


# ---------- get_glyph_name_for_code with /Differences ----------


def test_get_glyph_name_for_code_via_differences() -> None:
    """A /Differences overlay on WinAnsiEncoding should map a custom code
    to the differences-supplied glyph name."""
    enc = COSDictionary()
    enc.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Encoding"))
    enc.set_item(
        COSName.get_pdf_name("BaseEncoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    # Code 65 ("A" in WinAnsi) overridden to "Lslash".
    diffs = COSArray([COSInteger.get(65), COSName.get_pdf_name("Lslash")])
    enc.set_item(_DIFFERENCES, diffs)

    font = PDType1Font()
    font.get_cos_object().set_item(_ENCODING, enc)

    assert font.get_glyph_name_for_code(65) == "Lslash"
    # An untouched WinAnsi code should still resolve via the base encoding.
    assert font.get_glyph_name_for_code(66) == "B"


def test_get_glyph_name_for_code_returns_none_for_unmapped() -> None:
    # No /Encoding at all → every code is unmapped.
    assert PDType1Font().get_glyph_name_for_code(65) is None


# ---------- get_displacement ----------


def test_get_displacement_returns_width_over_1000_horizontal() -> None:
    """For a horizontal simple font the displacement vector is
    (width/1000, 0). Use a /Widths-supplied advance so we don't depend
    on AFM lookup paths."""
    font = PDType1Font()
    cos = font.get_cos_object()
    cos.set_int(_FIRST_CHAR, 65)
    cos.set_int(_LAST_CHAR, 65)
    cos.set_item(_WIDTHS, COSArray([COSInteger.get(750)]))

    dx, dy = font.get_displacement(65)
    assert dx == 0.75
    assert dy == 0.0


def test_get_displacement_zero_for_unmapped_code_with_no_metrics() -> None:
    # No /Widths, no /BaseFont → get_glyph_width returns 0.0 → (0, 0).
    dx, dy = PDType1Font().get_displacement(65)
    assert dx == 0.0
    assert dy == 0.0


# ---------- get_standard_14_font_metrics ----------


def test_get_standard_14_font_metrics_for_helvetica() -> None:
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    afm = font.get_standard_14_font_metrics()
    assert afm is not None
    assert isinstance(afm, AfmMetrics)
    assert afm.get_font_name() == "Helvetica"
    # Sanity: average width should be a positive number for a real font.
    assert afm.get_average_width() > 0.0


def test_get_standard_14_font_metrics_for_alias() -> None:
    """Aliases (Arial → Helvetica) round-trip through the same lookup."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "ArialMT")
    afm = font.get_standard_14_font_metrics()
    assert afm is not None
    assert afm.get_font_name() == "Helvetica"


def test_get_standard_14_font_metrics_none_for_non_standard() -> None:
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "MyCustomFont")
    assert font.get_standard_14_font_metrics() is None


def test_get_standard_14_font_metrics_none_when_base_font_absent() -> None:
    assert PDType1Font().get_standard_14_font_metrics() is None


# ---------- get_average_font_width fallback ----------


def test_get_average_font_width_uses_widths_when_present() -> None:
    font = PDType1Font()
    cos = font.get_cos_object()
    cos.set_name(_BASE_FONT, "Helvetica")  # would have an AFM mean
    cos.set_int(_FIRST_CHAR, 32)
    cos.set_int(_LAST_CHAR, 34)
    cos.set_item(
        _WIDTHS,
        COSArray(
            [COSInteger.get(100), COSInteger.get(200), COSInteger.get(300)]
        ),
    )
    # /Widths wins over AFM — mean of [100, 200, 300] = 200.
    assert font.get_average_font_width() == 200.0


def test_get_average_font_width_falls_back_to_afm_for_standard_14() -> None:
    """No /Widths present → fall back to the bundled AFM mean."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    afm_mean = font.get_standard_14_font_metrics().get_average_width()  # type: ignore[union-attr]
    assert font.get_average_font_width() == afm_mean
    assert afm_mean > 0.0


def test_get_average_font_width_zero_when_no_widths_and_no_afm() -> None:
    assert PDType1Font().get_average_font_width() == 0.0


# ---------- get_font_program / get_path aliases ----------


def test_get_font_program_none_when_not_embedded() -> None:
    assert PDType1Font().get_font_program() is None


def test_get_path_returns_empty_when_no_embedded_program() -> None:
    # No /FontFile → no program → no path. We don't need to round-trip a
    # real Type 1 fixture here (test_type1_cff_glyph covers that path);
    # we just need to confirm the alias is wired and falls through to []
    # when the program is absent.
    assert PDType1Font().get_path("A") == []


# ---------- ALT_NAMES / PFB_START_MARKER constants ----------


def test_alt_names_constant_exposes_upstream_table() -> None:
    """``PDType1Font.ALT_NAMES`` mirrors the upstream Java ``ALT_NAMES``
    map (ligature-component fallbacks)."""
    table = PDType1Font.ALT_NAMES
    assert table["ff"] == "f_f"
    assert table["ffi"] == "f_f_i"
    assert table["ffl"] == "f_f_l"
    assert table["fi"] == "f_i"
    assert table["fl"] == "f_l"
    assert table["st"] == "s_t"
    assert table["IJ"] == "I_J"
    assert table["ij"] == "i_j"
    # Misspelled entry from ArialMT — load-bearing for substitution.
    assert table["ellipsis"] == "elipsis"


def test_pfb_start_marker_constant() -> None:
    """``PDType1Font.PFB_START_MARKER`` matches upstream's 0x80
    detector for PFB-wrapped /FontFile streams."""
    assert PDType1Font.PFB_START_MARKER == 0x80


# ---------- code_to_name / get_name_in_font ----------


def test_code_to_name_via_encoding() -> None:
    """``code_to_name`` runs the typed /Encoding lookup and then falls
    through ``get_name_in_font``. With no embedded program the name
    is returned unchanged."""
    enc = COSDictionary()
    enc.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Encoding"))
    enc.set_item(
        COSName.get_pdf_name("BaseEncoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    diffs = COSArray([COSInteger.get(65), COSName.get_pdf_name("Lslash")])
    enc.set_item(_DIFFERENCES, diffs)

    font = PDType1Font()
    font.get_cos_object().set_item(_ENCODING, enc)

    # Code 65 -> /Differences-supplied "Lslash"; with no embedded program
    # the name passes through get_name_in_font unchanged.
    assert font.code_to_name(65) == "Lslash"


def test_code_to_name_returns_notdef_when_no_encoding() -> None:
    # Upstream falls back to ".notdef" when the font has no /Encoding.
    assert PDType1Font().code_to_name(65) == ".notdef"


def test_get_name_in_font_passthrough_without_program() -> None:
    """When the font has no embedded program, ``get_name_in_font``
    returns the input unchanged — there's nothing to remap against."""
    font = PDType1Font()
    assert font.get_name_in_font("A") == "A"
    assert font.get_name_in_font("ff") == "ff"


# ---------- has_glyph(name) / has_glyph_for_code(code) ----------


def test_has_glyph_for_code_via_encoding() -> None:
    """``has_glyph_for_code`` is encoding-based: it returns True iff
    the typed /Encoding maps the code to anything but .notdef."""
    enc = COSDictionary()
    enc.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Encoding"))
    enc.set_item(
        COSName.get_pdf_name("BaseEncoding"), COSName.get_pdf_name("WinAnsiEncoding")
    )
    font = PDType1Font()
    font.get_cos_object().set_item(_ENCODING, enc)
    # 65 == "A" in WinAnsi.
    assert font.has_glyph_for_code(65) is True
    # 0 falls in the .notdef block.
    assert font.has_glyph_for_code(0) is False


def test_has_glyph_for_code_false_when_no_encoding() -> None:
    assert PDType1Font().has_glyph_for_code(65) is False


def test_has_glyph_false_when_no_program() -> None:
    """Without an embedded program we can't confirm glyph presence —
    ``has_glyph`` reports False rather than guessing."""
    assert PDType1Font().has_glyph("A") is False


# ---------- read_code ----------


def test_read_code_reads_single_byte_walking_offsets() -> None:
    font = PDType1Font()
    data = b"\x41\x42\x43"
    assert font.read_code(data, 0) == (0x41, 1)
    assert font.read_code(data, 1) == (0x42, 1)
    assert font.read_code(data, 2) == (0x43, 1)


def test_read_code_past_end_returns_zero_zero() -> None:
    font = PDType1Font()
    assert font.read_code(b"") == (0, 0)
    assert font.read_code(b"\x00", 1) == (0, 0)


def test_read_code_accepts_bytes_argument() -> None:
    """``read_code`` walks a bytes buffer at the given offset and
    returns ``(code, consumed)``."""
    font = PDType1Font()
    assert font.read_code(b"\x7f") == (0x7F, 1)
    assert font.read_code(b"") == (0, 0)


# ---------- get_type1_font alias ----------


def test_get_type1_font_none_when_not_embedded() -> None:
    """``get_type1_font`` mirrors upstream's ``getType1Font`` accessor —
    returns ``None`` when no /FontFile is present."""
    assert PDType1Font().get_type1_font() is None


def test_get_type1_font_matches_get_font_program_alias() -> None:
    """Both accessors delegate to the same lazy parser. With no
    embedded program both should agree on ``None``."""
    font = PDType1Font()
    assert font.get_type1_font() is font.get_font_program()
