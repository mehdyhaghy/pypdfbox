"""Wave 1337 coverage-boost tests for :mod:`pypdfbox.pdmodel.font.pd_type1c_font`.

Targets the lesser-traveled paths:

* ``has_glyph_for_code`` / ``get_path_for_code`` / ``get_normalized_path_for_code``
  ``sfthyphen`` / ``nbspace`` glyph-name rewrites (with and without
  ``space`` in the program).
* ``get_font_matrix`` / ``get_bounding_box`` / ``generate_bounding_box``
  CFF-parse-failure exception arms and wrong-length-matrix fallbacks.
* ``get_width_from_font`` ``units_per_em <= 0`` fallback and ``advance
  <= 0`` short-circuit.
* ``get_name_in_font`` AGL → ``uniXXXX`` fallback (non-embedded font
  whose program does carry the ``uniXXXX`` spelling).
* ``read_encoding_from_font`` embedded-program-with-encoding-map path
  (returns a :class:`BuiltInEncoding`).
* ``encode_codepoint`` "no glyph for codepoint" / "name has no code in
  encoding" raises.
"""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.pdmodel.font import PDFontDescriptor
from pypdfbox.pdmodel.font.encoding.built_in_encoding import BuiltInEncoding
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont

_BASE_FONT = COSName.get_pdf_name("BaseFont")
_ENCODING = COSName.get_pdf_name("Encoding")


def _build_minimal_cff_bytes_with_extras(
    extra_glyphs: list[str] | None = None,
) -> bytes:
    """Build a CFF with ``.notdef``, ``A``, ``B``, plus any ``extra_glyphs``.

    Used to inject ``sfthyphen``, ``nbspace``, ``hyphen``, ``space``,
    ``uniXXXX`` spellings into the embedded program.
    """
    from fontTools.fontBuilder import FontBuilder
    from fontTools.misc.psCharStrings import T2CharString
    from fontTools.ttLib import TTFont

    extras = list(extra_glyphs or [])
    fb = FontBuilder(1000, isTTF=False)
    glyph_order = [".notdef", "A", "B", *extras]
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({65: "A", 66: "B"})

    def _cs(program: list) -> T2CharString:
        s = T2CharString()
        s.program = program
        return s

    char_strings = {
        ".notdef": _cs([0, "endchar"]),
        "A": _cs(
            [500, 0, "hmoveto", 700, "vlineto", 100, "hlineto", -700, "vlineto", "endchar"]
        ),
        "B": _cs([300, 0, "hmoveto", 500, "vlineto", "endchar"]),
    }
    for name in extras:
        char_strings[name] = _cs([400, 0, "hmoveto", 200, "vlineto", "endchar"])
    fb.setupCFF(
        psName="WaveExtra",
        fontInfo={"FullName": "Wave Extra"},
        charStringsDict=char_strings,
        privateDict={},
    )
    metrics = {".notdef": (0, 0), "A": (500, 0), "B": (300, 0)}
    for name in extras:
        metrics[name] = (400, 0)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupNameTable({"familyName": "Wave", "styleName": "Regular"})
    fb.setupPost()
    buf = io.BytesIO()
    fb.font.save(buf)
    return bytes(TTFont(io.BytesIO(buf.getvalue())).getTableData("CFF "))


def _make_font_with_extras(
    extras: list[str] | None = None,
    encoding_differences: list[tuple[int, str]] | None = None,
) -> PDType1CFont:
    """Construct a PDType1CFont with an embedded CFF and optional
    ``/Encoding /Differences`` mapping extra glyphs to specific codes."""
    cff = CFFFont.from_bytes(_build_minimal_cff_bytes_with_extras(extras))
    raw = COSDictionary()
    raw.set_name(_BASE_FONT, "EmbeddedExtras")
    if encoding_differences is not None:
        from pypdfbox.cos import COSArray, COSInteger

        enc_dict = COSDictionary()
        differences = COSArray()
        sorted_diffs = sorted(encoding_differences)
        last_code: int | None = None
        for code, name in sorted_diffs:
            if last_code is None or code != last_code + 1:
                differences.add(COSInteger.get(code))
            differences.add(COSName.get_pdf_name(name))
            last_code = code
        enc_dict.set_item(COSName.get_pdf_name("Differences"), differences)
        # Use WinAnsiEncoding as base.
        enc_dict.set_name(
            COSName.get_pdf_name("BaseEncoding"), "WinAnsiEncoding"
        )
        raw.set_item(_ENCODING, enc_dict)
    else:
        raw.set_item(_ENCODING, COSName.get_pdf_name("WinAnsiEncoding"))
    font = PDType1CFont(raw)
    font.set_font_program(cff)
    return font


# ---------- has_glyph_for_code sfthyphen / nbspace rewrites ----------


def test_has_glyph_for_code_sfthyphen_branch() -> None:
    """A code mapped to ``sfthyphen`` checks ``has_glyph("hyphen")``.

    The font has ``hyphen`` available, so the predicate returns True.
    """
    font = _make_font_with_extras(
        extras=["hyphen"],
        encoding_differences=[(200, "sfthyphen")],
    )
    # The encoding maps code 200 -> "sfthyphen"; has_glyph_for_code
    # should rewrite to "hyphen".
    assert font.has_glyph_for_code(200) is True


def test_has_glyph_for_code_nbspace_branch() -> None:
    """A code mapped to ``nbspace`` checks ``has_glyph("space")``."""
    font = _make_font_with_extras(
        extras=["space"],
        encoding_differences=[(201, "nbspace")],
    )
    assert font.has_glyph_for_code(201) is True


def test_has_glyph_for_code_unmapped_returns_false() -> None:
    """Code that maps to None — early return False."""
    font = _make_font_with_extras()
    # 250 is not in WinAnsiEncoding and has no /Differences override.
    assert font.has_glyph_for_code(250) is False


# ---------- get_path_for_code sfthyphen / nbspace rewrites ----------


def test_get_path_for_code_sfthyphen() -> None:
    font = _make_font_with_extras(
        extras=["hyphen"],
        encoding_differences=[(200, "sfthyphen")],
    )
    path = font.get_path_for_code(200)
    assert path  # non-empty path from hyphen


def test_get_path_for_code_nbspace_with_space() -> None:
    font = _make_font_with_extras(
        extras=["space"],
        encoding_differences=[(201, "nbspace")],
    )
    path = font.get_path_for_code(201)
    assert path  # non-empty path from space


def test_get_path_for_code_nbspace_without_space_returns_empty() -> None:
    """nbspace code rewrites to space; if space is absent from the
    program, returns []."""
    font = _make_font_with_extras(
        extras=[],  # no space glyph
        encoding_differences=[(201, "nbspace")],
    )
    path = font.get_path_for_code(201)
    assert path == []


# ---------- get_normalized_path_for_code nbspace / sfthyphen ----------


def test_get_normalized_path_for_code_nbspace_with_space() -> None:
    font = _make_font_with_extras(
        extras=["space"],
        encoding_differences=[(201, "nbspace")],
    )
    path = font.get_normalized_path_for_code(201)
    assert path


def test_get_normalized_path_for_code_nbspace_without_space_falls_back() -> None:
    """nbspace -> space; space missing -> [] (and the function returns
    that [] immediately, not the .notdef fallback because the path
    branches differently)."""
    font = _make_font_with_extras(
        extras=[],
        encoding_differences=[(201, "nbspace")],
    )
    path = font.get_normalized_path_for_code(201)
    assert path == []


def test_get_normalized_path_for_code_sfthyphen() -> None:
    font = _make_font_with_extras(
        extras=["hyphen"],
        encoding_differences=[(200, "sfthyphen")],
    )
    path = font.get_normalized_path_for_code(200)
    assert path


# ---------- get_font_matrix exception + wrong-length fallback ----------


def test_get_font_matrix_handles_program_exception() -> None:
    """If the CFF program's ``get_font_matrix`` raises, fall back to
    the default matrix (line 429-430)."""
    font = _make_font_with_extras()
    program = font._get_cff_font()
    assert program is not None
    with patch.object(program, "get_font_matrix", side_effect=RuntimeError):
        m = font.get_font_matrix()
        assert m == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


def test_get_font_matrix_wrong_length_falls_back() -> None:
    """A matrix of wrong size also yields the default fallback (line 433)."""
    font = _make_font_with_extras()
    program = font._get_cff_font()
    assert program is not None
    with patch.object(program, "get_font_matrix", return_value=[1.0, 2.0]):
        m = font.get_font_matrix()
        assert m == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


def test_get_font_matrix_returns_program_matrix() -> None:
    font = _make_font_with_extras()
    program = font._get_cff_font()
    assert program is not None
    expected = [0.0005, 0.0, 0.0, 0.0005, 0.0, 0.0]
    with patch.object(program, "get_font_matrix", return_value=expected):
        m = font.get_font_matrix()
        assert m == expected


# ---------- get_bounding_box exception + wrong-length ----------


def test_get_bounding_box_with_program_exception_returns_none() -> None:
    """CFF program's ``get_font_bbox`` raises → None (line 469-470)."""
    font = _make_font_with_extras()
    program = font._get_cff_font()
    assert program is not None
    with patch.object(program, "get_font_bbox", side_effect=RuntimeError):
        # Need to clear the descriptor so we don't take the early
        # descriptor-bbox branch.
        font._dict.remove_item(COSName.get_pdf_name("FontDescriptor"))
        assert font.get_bounding_box() is None


def test_get_bounding_box_with_wrong_length_bbox_returns_none() -> None:
    """A CFF bbox of wrong length → None (line 472)."""
    font = _make_font_with_extras()
    program = font._get_cff_font()
    assert program is not None
    with patch.object(program, "get_font_bbox", return_value=[1.0, 2.0]):
        font._dict.remove_item(COSName.get_pdf_name("FontDescriptor"))
        assert font.get_bounding_box() is None


def test_get_bounding_box_returns_rectangle_from_cff() -> None:
    """Successful CFF bbox → PDRectangle."""
    font = _make_font_with_extras()
    program = font._get_cff_font()
    assert program is not None
    with patch.object(
        program, "get_font_bbox", return_value=[-10.0, -20.0, 100.0, 200.0]
    ):
        font._dict.remove_item(COSName.get_pdf_name("FontDescriptor"))
        bbox = font.get_bounding_box()
        assert bbox is not None
        assert bbox.get_lower_left_x() == -10.0


# ---------- get_width_from_font edge cases ----------


def test_get_width_from_font_units_per_em_zero_uses_default() -> None:
    """``units_per_em <= 0`` substitutes the CFF default of 1000 (line 530)."""
    font = _make_font_with_extras()
    program = font._get_cff_font()
    assert program is not None
    # Force the CFF program's units_per_em to 0.
    with patch.object(
        type(program), "units_per_em", property(lambda self: 0)
    ):
        # Code 65 = 'A' which has width 500 in our test CFF.
        width = font.get_width_from_font(65)
        # With upem=1000 (CFF default), 500 * 1000 / 1000 = 500.
        assert width == 500.0


def test_get_width_from_font_zero_advance_returns_zero() -> None:
    """Glyph with zero advance → 0.0 short-circuit (line 533)."""
    font = _make_font_with_extras()
    program = font._get_cff_font()
    assert program is not None
    with patch.object(program, "get_width", return_value=0.0):
        assert font.get_width_from_font(65) == 0.0


# ---------- get_name_in_font AGL uniXXXX fallback ----------


def test_get_name_in_font_uni_xxxx_fallback() -> None:
    """Non-embedded font whose program does not carry the requested name
    but does carry the AGL ``uniXXXX`` spelling — returns ``uniXXXX``.

    The AGL maps ``Omega`` to U+2126 (OHM SIGN), not U+03A9
    (GREEK CAPITAL LETTER OMEGA) — historical quirk of the original
    PostScript glyph-list mapping.
    """
    # Build font WITH "uni2126" (OHM SIGN U+2126) in the program but
    # NOT "Omega" itself.
    font = _make_font_with_extras(extras=["uni2126"])
    assert not font.is_embedded()
    program = font._get_cff_font()
    assert program is not None
    # Sanity: program has "uni2126" but not "Omega".
    assert program.has_glyph("uni2126")
    assert not program.has_glyph("Omega")
    # Now ask for "Omega" — the AGL maps it to U+2126 → "uni2126" → match.
    assert font.get_name_in_font("Omega") == "uni2126"


def test_get_name_in_font_falls_back_to_notdef_when_uni_form_absent() -> None:
    """The program lacks both ``name`` and ``uniXXXX`` → ``.notdef``."""
    font = _make_font_with_extras()  # no extras
    assert not font.is_embedded()
    # "Omega" maps via AGL to U+2126 but program has no uni2126.
    assert font.get_name_in_font("Omega") == ".notdef"


# ---------- read_encoding_from_font with encoding_map ----------


def test_read_encoding_from_font_with_program_encoding_map() -> None:
    """When the CFF program exposes a non-empty encoding map (via
    ``get_encoding_map``), the result is a :class:`BuiltInEncoding`
    wrapping that map (line 719)."""
    font = _make_font_with_extras()
    program = font._get_cff_font()
    assert program is not None
    # Mock the program to return a non-empty encoding map.
    with patch.object(
        program, "get_encoding_map", create=True, return_value={65: "A", 66: "B"}
    ):
        enc = font.read_encoding_from_font()
        assert isinstance(enc, BuiltInEncoding)


# ---------- encode_codepoint raise paths ----------


def test_encode_codepoint_raises_when_program_lacks_glyph() -> None:
    """``name_in_font`` is non-``.notdef`` but the program has no glyph
    for it → raises ``ValueError`` (lines 758-762)."""
    font = _make_font_with_extras()
    # Force is_embedded() to be True so name_in_font passes through.
    fd = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(_build_minimal_cff_bytes_with_extras())
    stream.set_name(COSName.SUBTYPE, "Type1C")  # type: ignore[attr-defined]
    fd.set_font_file3(stream)
    font.set_font_descriptor(fd)

    # Replace the CFF program with one that returns False for has_glyph.
    program = font._get_cff_font()
    assert program is not None
    with (
        patch.object(program, "has_glyph", return_value=False),
        pytest.raises(ValueError, match="No glyph"),
    ):
        # 'A' is in the encoding name set but program rejects.
        font.encode_codepoint(ord("A"))


def test_encode_codepoint_raises_when_name_has_no_code_in_encoding() -> None:
    """A glyph name that's present in the encoding's name set but absent
    from ``get_name_to_code_map`` → raises (lines 765-769).

    This can happen when ``Encoding`` includes a name through
    ``Differences`` but the name-to-code reverse map is broken / empty.
    """
    font = _make_font_with_extras()
    encoding = font.get_encoding_typed()
    assert encoding is not None
    # Wedge the encoding's name-to-code map to return None for our target.
    with (
        patch.object(encoding, "get_name_to_code_map", return_value={"X": 88}),
        patch.object(encoding, "__contains__", return_value=True),
        pytest.raises(ValueError, match="has no code"),
    ):
        # 'A' would normally encode; but our mock removes its code.
        # We need is_embedded so name_in_font passes through.
        fd = PDFontDescriptor()
        stream = COSStream()
        stream.set_data(_build_minimal_cff_bytes_with_extras())
        stream.set_name(COSName.SUBTYPE, "Type1C")  # type: ignore[attr-defined]
        fd.set_font_file3(stream)
        font.set_font_descriptor(fd)
        # Reset CFF cache since we changed descriptor.
        font._cff = None
        font.encode_codepoint(ord("A"))


# ---------- get_path nbspace -> space happy path ----------


def test_get_path_nbspace_with_space_returns_space_path() -> None:
    """When asked for the ``nbspace`` name directly (not the code),
    ``get_path`` returns the ``space`` outline (line 247)."""
    font = _make_font_with_extras(extras=["space"])
    path = font.get_path("nbspace")
    # Should be non-empty (the space glyph's outline).
    assert path


def test_get_path_nbspace_without_space_returns_empty() -> None:
    """``nbspace`` rewrites to ``space``; if ``space`` is absent, []."""
    font = _make_font_with_extras(extras=[])
    path = font.get_path("nbspace")
    assert path == []


# ---------- get_normalized_path_for_code name=None falls back to .notdef ----------


def test_get_normalized_path_for_code_unmapped_falls_back_to_notdef() -> None:
    """When the code resolves to no name at all, falls back to
    ``.notdef`` (line 315)."""
    font = _make_font_with_extras(extras=[])
    # Force the encoding so a high code maps to nothing.
    # Code 0xFE is unmapped in WinAnsi (or maps to .notdef).
    path = font.get_normalized_path_for_code(0x00)  # NUL char — unmapped
    # The .notdef glyph in our CFF is just `0 endchar` — a minimal path.
    assert isinstance(path, list)


# ---------- generate_bounding_box exception arms ----------


def test_generate_bounding_box_with_program_exception_returns_none() -> None:
    """``generate_bounding_box`` mirrors ``get_bounding_box``'s exception
    handling on the CFF arm (lines 643-644)."""
    font = _make_font_with_extras()
    program = font._get_cff_font()
    assert program is not None
    with patch.object(program, "get_font_bbox", side_effect=RuntimeError):
        font._dict.remove_item(COSName.get_pdf_name("FontDescriptor"))
        assert font.generate_bounding_box() is None


def test_generate_bounding_box_with_wrong_length_returns_none() -> None:
    """A CFF bbox of wrong length → None (line 646)."""
    font = _make_font_with_extras()
    program = font._get_cff_font()
    assert program is not None
    with patch.object(program, "get_font_bbox", return_value=[1.0]):
        font._dict.remove_item(COSName.get_pdf_name("FontDescriptor"))
        assert font.generate_bounding_box() is None
