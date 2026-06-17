"""Fuzz + parity tests for simple-font glyph width resolution (wave 1594).

Hammers ``PDFont.get_width`` / ``PDSimpleFont.get_standard14_width`` /
``PDSimpleFont.has_explicit_width`` / ``PDFont.get_average_font_width``
against the exact upstream PDFBox ``PDFont.getWidth(int)`` resolution
ladder (PDFont.java lines 256-311):

1. ``/Widths[code - /FirstChar]`` when ``code`` is inside
   ``[FirstChar, LastChar]`` *and* the offset is in range — a null /Widths
   slot reads back as ``0f``.
2. else the ``/FontDescriptor`` ``/MissingWidth`` (default ``0``) — but
   only when the dict carries ``/Widths`` or ``/MissingWidth``.
3. else, for a Standard 14 font, the AFM width
   (``PDSimpleFont.getStandard14Width``).
4. else the embedded program advance (``getWidthFromFont``).

These are hand-written API tests (synthetic font dictionaries); the
upstream behaviour they pin is documented inline per case.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_null import COSNull
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _make_simple_font(
    *,
    base_font: str = "MyCustomFont",
    first_char: int | None = None,
    last_char: int | None = None,
    widths: list[int | float | None] | None = None,
    missing_width: int | float | None = None,
    with_descriptor: bool = False,
) -> PDType1Font:
    """Build a synthetic non-embedded /Type1 simple font dictionary.

    A non-Standard-14 ``base_font`` keeps the AFM tier inert so the test
    isolates the dictionary-driven ladder; ``base_font`` may be a
    Standard 14 name to exercise the AFM tier instead.
    """
    d = COSDictionary()
    d.set_item(_name("Type"), _name("Font"))
    d.set_item(_name("Subtype"), _name("Type1"))
    d.set_item(_name("BaseFont"), _name(base_font))
    if first_char is not None:
        d.set_int(_name("FirstChar"), first_char)
    if last_char is not None:
        d.set_int(_name("LastChar"), last_char)
    if widths is not None:
        arr = COSArray()
        for w in widths:
            if w is None:
                arr.add(COSNull.NULL)
            elif isinstance(w, int):
                arr.add(COSInteger.get(w))
            else:
                arr.add(COSFloat(float(w)))
        d.set_item(_name("Widths"), arr)
    if with_descriptor or missing_width is not None:
        fd = COSDictionary()
        fd.set_item(_name("Type"), _name("FontDescriptor"))
        fd.set_item(_name("FontName"), _name(base_font))
        if missing_width is not None:
            fd.set_item(_name("MissingWidth"), COSFloat(float(missing_width)))
        d.set_item(_name("FontDescriptor"), fd)
    return PDType1Font(d)


# ---------------------------------------------------------------------------
# Tier 1: /Widths[code - FirstChar] inside [FirstChar, LastChar]
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (65, 100.0),  # FirstChar itself -> index 0
        (66, 200.0),  # index 1
        (67, 300.0),  # index 2
        (68, 400.0),  # LastChar -> last index (inclusive bound)
    ],
)
def test_width_inside_range_uses_widths_array(code: int, expected: float) -> None:
    # /Widths[code - FirstChar] for code in [FirstChar, LastChar].
    f = _make_simple_font(
        first_char=65, last_char=68, widths=[100, 200, 300, 400]
    )
    assert f.get_width(code) == expected


def test_first_char_offset_arithmetic_is_not_off_by_one() -> None:
    # idx = code - FirstChar. FirstChar=10 -> code 10 is index 0, NOT index
    # 10. An off-by-one here would shift every glyph one slot.
    f = _make_simple_font(first_char=10, last_char=13, widths=[11, 22, 33, 44])
    assert f.get_width(10) == 11.0
    assert f.get_width(11) == 22.0
    assert f.get_width(13) == 44.0


@pytest.mark.parametrize("first_char", [0, 1, 32, 65, 128, 200, 255])
def test_first_char_offset_various_origins(first_char: int) -> None:
    # The first /Widths entry always maps to /FirstChar regardless of origin.
    f = _make_simple_font(
        first_char=first_char,
        last_char=first_char + 2,
        widths=[501, 502, 503],
    )
    assert f.get_width(first_char) == 501.0
    assert f.get_width(first_char + 1) == 502.0
    assert f.get_width(first_char + 2) == 503.0


# ---------------------------------------------------------------------------
# A /Widths entry of 0 is a VALID width, not "missing".
# ---------------------------------------------------------------------------


def test_zero_width_entry_is_valid_not_missing() -> None:
    # Upstream: widths.get(idx) == 0 is returned as-is; /MissingWidth is only
    # consulted when the code is OUT of range, never for an in-range 0.
    f = _make_simple_font(
        first_char=65,
        last_char=67,
        widths=[0, 0, 0],
        missing_width=999,
    )
    assert f.get_width(65) == 0.0
    assert f.get_width(66) == 0.0
    assert f.get_width(67) == 0.0
    # out of range -> MissingWidth
    assert f.get_width(70) == 999.0


def test_zero_width_entry_has_explicit_width_true() -> None:
    # has_explicit_width must distinguish a present 0 from a default width.
    f = _make_simple_font(first_char=65, last_char=66, widths=[0, 0])
    assert f.has_explicit_width(65) is True
    assert f.has_explicit_width(66) is True


# ---------------------------------------------------------------------------
# A null /Widths slot reads back as 0.0 (upstream: if (width==null) width=0f).
# ---------------------------------------------------------------------------


def test_null_widths_slot_reads_zero() -> None:
    f = _make_simple_font(
        first_char=65, last_char=67, widths=[100, None, 300]
    )
    assert f.get_width(65) == 100.0
    assert f.get_width(66) == 0.0  # null entry -> 0f
    assert f.get_width(67) == 300.0
    # but it is still "explicit" because the slot exists in range
    assert f.has_explicit_width(66) is True


def test_get_widths_preserves_null_as_none_in_place() -> None:
    # Length preserved so later indices stay aligned with /FirstChar.
    f = _make_simple_font(
        first_char=0, last_char=3, widths=[10, None, 30, None]
    )
    assert f.get_widths() == [10.0, None, 30.0, None]


# ---------------------------------------------------------------------------
# Tier 2: out-of-range code -> /MissingWidth (default 0).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", [0, 64, 69, 100, 255])
def test_out_of_range_uses_missing_width(code: int) -> None:
    # code outside [FirstChar=65, LastChar=68] -> descriptor /MissingWidth.
    f = _make_simple_font(
        first_char=65, last_char=68, widths=[1, 2, 3, 4], missing_width=321
    )
    assert f.get_width(code) == 321.0


def test_missing_width_default_is_zero_when_descriptor_lacks_it() -> None:
    # Descriptor present but no /MissingWidth -> getFloat default 0.
    f = _make_simple_font(
        first_char=65, last_char=66, widths=[10, 20], with_descriptor=True
    )
    assert f.get_width(200) == 0.0


def test_missing_width_on_font_dict_triggers_dict_branch_without_widths() -> None:
    # Upstream getWidth enters the dict branch when the FONT dictionary
    # (not the descriptor) carries /Widths OR /MissingWidth
    # (PDFont.java line 272: dict.containsKey(MISSING_WIDTH)). With
    # /MissingWidth on the font dict and no /Widths, every code falls to
    # the descriptor's /MissingWidth.
    d = COSDictionary()
    d.set_item(_name("Type"), _name("Font"))
    d.set_item(_name("Subtype"), _name("Type1"))
    d.set_item(_name("BaseFont"), _name("MyCustomFont"))
    # /MissingWidth on the font dict itself -> branch entry trigger.
    d.set_item(_name("MissingWidth"), COSFloat(540.0))
    fd = COSDictionary()
    fd.set_item(_name("Type"), _name("FontDescriptor"))
    fd.set_item(_name("FontName"), _name("MyCustomFont"))
    fd.set_item(_name("MissingWidth"), COSFloat(540.0))
    d.set_item(_name("FontDescriptor"), fd)
    f = PDType1Font(d)
    assert f.get_width(0) == 540.0
    assert f.get_width(65) == 540.0
    assert f.get_width(255) == 540.0


def test_missing_width_only_on_descriptor_does_not_trigger_dict_branch() -> None:
    # /MissingWidth living ONLY on the /FontDescriptor (the canonical spot)
    # and no /Widths -> upstream's font-dict containsKey(MISSING_WIDTH) is
    # FALSE, so the dict branch is skipped entirely and resolution falls to
    # the embedded-program tier (here the non-embedded .notdef substitute,
    # 250). Pins that the trigger is the FONT dict, not the descriptor.
    f = _make_simple_font(missing_width=540)
    assert f.get_width(0) == 250.0  # not 540 -> branch not entered


def test_below_first_char_uses_missing_width() -> None:
    # code < FirstChar (idx would be negative) -> MissingWidth, never a
    # wrap-around into the tail of /Widths.
    f = _make_simple_font(
        first_char=70, last_char=72, widths=[7, 8, 9], missing_width=42
    )
    assert f.get_width(69) == 42.0
    assert f.get_width(0) == 42.0


def test_just_past_last_char_uses_missing_width() -> None:
    # LastChar is inclusive; LastChar+1 is the first out-of-range code.
    f = _make_simple_font(
        first_char=65, last_char=67, widths=[100, 200, 300], missing_width=88
    )
    assert f.get_width(67) == 300.0  # inclusive
    assert f.get_width(68) == 88.0  # just past -> MissingWidth


def test_widths_array_shorter_than_range_falls_to_missing_width() -> None:
    # LastChar declares 65..70 but only 2 /Widths entries exist. Codes whose
    # idx >= len(widths) fall through to /MissingWidth (upstream idx < siz).
    f = _make_simple_font(
        first_char=65, last_char=70, widths=[111, 222], missing_width=900
    )
    assert f.get_width(65) == 111.0
    assert f.get_width(66) == 222.0
    assert f.get_width(67) == 900.0  # idx 2 >= len(widths)=2
    assert f.has_explicit_width(67) is False


# ---------------------------------------------------------------------------
# Tier 3: Standard 14 font with no /Widths -> AFM width.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("font_name", "code", "expected"),
    [
        (PDType1Font.HELVETICA, 32, 278.0),  # space
        (PDType1Font.HELVETICA, 65, 667.0),  # A
        (PDType1Font.HELVETICA, 87, 944.0),  # W
        (PDType1Font.HELVETICA, 105, 222.0),  # i
        ("Times-Roman", 32, 250.0),  # Times space
        ("Times-Roman", 65, 722.0),  # Times A
        ("Courier", 32, 600.0),  # Courier fixed pitch
        ("Courier", 65, 600.0),
    ],
)
def test_standard14_no_widths_uses_afm(
    font_name: str, code: int, expected: float
) -> None:
    f = PDType1Font.standard14(font_name)
    assert f.is_standard14() is True
    assert f.get_width(code) == expected


def test_standard14_get_standard14_width_matches_get_width() -> None:
    f = PDType1Font.standard14(PDType1Font.HELVETICA)
    for code in (32, 65, 90, 97, 122):
        assert f.get_standard14_width(code) == f.get_width(code)


def test_standard14_notdef_returns_250() -> None:
    # Adobe AFMs omit .notdef; Acrobat uses 250 (PDFBOX-2334). Code 0 in
    # WinAnsi resolves to .notdef for Helvetica.
    f = PDType1Font.standard14(PDType1Font.HELVETICA)
    assert f.get_standard14_width(0) == 250.0


def test_standard14_widths_array_overrides_afm() -> None:
    # When a Standard 14 dict ALSO carries /Widths, the dictionary tier wins
    # (Acrobat / PDFBOX-427): AFM is tier 3, dict is tier 1.
    f = _make_simple_font(
        base_font="Helvetica",
        first_char=65,
        last_char=65,
        widths=[1234],
    )
    assert f.is_standard14() is True
    assert f.get_width(65) == 1234.0  # dict wins, not the AFM 667


def test_standard14_afm_loadable() -> None:
    f = PDType1Font.standard14(PDType1Font.HELVETICA)
    afm = f.get_standard14_afm()
    assert afm is not None
    assert afm.get_character_width("space") == 278.0


# ---------------------------------------------------------------------------
# has_explicit_width: present /Widths entry vs default.
# ---------------------------------------------------------------------------


def test_has_explicit_width_in_range_true_out_of_range_false() -> None:
    f = _make_simple_font(
        first_char=65, last_char=67, widths=[100, 200, 300], missing_width=50
    )
    assert f.has_explicit_width(65) is True
    assert f.has_explicit_width(66) is True
    assert f.has_explicit_width(67) is True
    # below first char
    assert f.has_explicit_width(64) is False
    # above last entry
    assert f.has_explicit_width(68) is False


def test_has_explicit_width_false_without_widths_array() -> None:
    # /MissingWidth alone does NOT make a width "explicit".
    f = _make_simple_font(missing_width=400)
    assert f.has_explicit_width(65) is False


def test_has_explicit_width_standard14_no_widths_false() -> None:
    # A Standard 14 font with AFM-only widths has no explicit /Widths.
    f = PDType1Font.standard14(PDType1Font.HELVETICA)
    assert f.has_explicit_width(65) is False
    assert f.has_explicit_width(32) is False


def test_has_explicit_width_uses_widths_length_not_last_char() -> None:
    # has_explicit_width bounds on len(/Widths), independent of /LastChar.
    # LastChar lies (says 5) but only 2 entries exist.
    f = _make_simple_font(first_char=65, last_char=70, widths=[10, 20])
    assert f.has_explicit_width(65) is True
    assert f.has_explicit_width(66) is True
    assert f.has_explicit_width(67) is False  # idx 2 >= len 2


# ---------------------------------------------------------------------------
# Average font width.
# ---------------------------------------------------------------------------


def test_average_font_width_skips_zero_entries() -> None:
    # Zero-width slots (notdef) are skipped so they don't drag the mean.
    f = _make_simple_font(first_char=0, last_char=3, widths=[100, 0, 200, 0])
    assert f.get_average_font_width() == 150.0  # (100+200)/2


def test_average_font_width_no_widths_is_zero() -> None:
    f = _make_simple_font(base_font="MyCustomFont")
    assert f.get_average_font_width() == 0.0


def test_average_font_width_all_zero_is_zero() -> None:
    f = _make_simple_font(first_char=0, last_char=2, widths=[0, 0, 0])
    assert f.get_average_font_width() == 0.0


def test_average_font_width_ignores_null_entries() -> None:
    f = _make_simple_font(first_char=0, last_char=3, widths=[300, None, 100, None])
    assert f.get_average_font_width() == 200.0  # (300+100)/2


# ---------------------------------------------------------------------------
# Caching: get_width memoizes per code (upstream codeToWidthMap).
# ---------------------------------------------------------------------------


def test_get_width_is_cached_per_code() -> None:
    f = _make_simple_font(first_char=65, last_char=65, widths=[123])
    first = f.get_width(65)
    second = f.get_width(65)
    assert first == second == 123.0


def test_widths_with_float_entries() -> None:
    f = _make_simple_font(
        first_char=65, last_char=67, widths=[100.5, 200.25, 300.75]
    )
    assert f.get_width(65) == 100.5
    assert f.get_width(66) == 200.25
    assert f.get_width(67) == 300.75


# ---------------------------------------------------------------------------
# Missing /FirstChar (default -1) edge.
# ---------------------------------------------------------------------------


def test_missing_first_char_defaults_to_minus_one() -> None:
    # No /FirstChar -> get_int default -1. With /Widths present and a
    # descriptor, code 0 has idx = 0 - (-1) = 1; code 0 <= LastChar but
    # idx may land oddly — verify it stays in the documented ladder and a
    # high code falls to MissingWidth rather than crashing.
    d = COSDictionary()
    d.set_item(_name("Type"), _name("Font"))
    d.set_item(_name("Subtype"), _name("Type1"))
    d.set_item(_name("BaseFont"), _name("MyCustomFont"))
    d.set_int(_name("LastChar"), 5)
    d.set_item(_name("Widths"), COSArray([COSInteger.get(10), COSInteger.get(20)]))
    fd = COSDictionary()
    fd.set_item(_name("MissingWidth"), COSFloat(77.0))
    d.set_item(_name("FontDescriptor"), fd)
    f = PDType1Font(d)
    # code 100 well out of range -> MissingWidth
    assert f.get_width(100) == 77.0


def test_standard14_space_constant_278() -> None:
    # Pin the canonical Helvetica space advance the surface brief names.
    f = PDType1Font.standard14(PDType1Font.HELVETICA)
    assert f.get_width(32) == 278.0
    assert Standard14Fonts.get_afm("Helvetica").get_character_width("space") == 278.0
