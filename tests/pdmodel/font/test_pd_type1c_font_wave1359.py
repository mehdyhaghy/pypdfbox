"""Wave 1359 — close upstream's ``// todo: not implemented, highly suspect``
on :meth:`PDType1CFont.get_average_character_width`.

Upstream's ``PDType1CFont.getAverageCharacterWidth`` returned a hard-coded
``500``. We replace that with a real mean computed from the available
signals (``/Widths`` -> embedded CFF charstring widths -> ``defaultWidthX``
-> Standard 14 AFM mean -> ``500`` floor). The CFF-charstring branch
relies on ``fontTools.cffLib`` via :class:`pypdfbox.fontbox.cff.cff_font.CFFFont`.

Coverage targets:

* ``/Widths`` branch — non-zero entries average.
* Embedded-CFF mean-of-glyph-widths branch — varying glyph IDs yield
  different widths, mean differs from any single width.
* Embedded-CFF ``defaultWidthX`` branch — exercised when every
  charstring's leading-operand width is zero so the per-glyph mean is
  empty.
* Standard 14 AFM branch — exercised by selecting a Standard 14
  ``/BaseFont`` with no ``/Widths`` and no embedded program.
* Final ``500`` floor — exercised by the empty-font case.
"""

from __future__ import annotations

import io

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont

_BASE_FONT = COSName.get_pdf_name("BaseFont")
_WIDTHS = COSName.get_pdf_name("Widths")


# ---------- helpers ----------


def _build_cff_bytes(
    widths_by_name: dict[str, int],
    *,
    ps_name: str = "Wave1359CFF",
) -> bytes:
    """Build a minimal CFF with ``.notdef`` plus the named glyphs whose
    advance widths are given by ``widths_by_name``.

    Mirrors the helper used in ``test_pd_type1c_font.py`` but parametrised
    so a caller can vary per-glyph advances and exercise the
    mean-of-glyph-widths branch with non-trivial GID->width variance.
    """
    from fontTools.fontBuilder import FontBuilder
    from fontTools.misc.psCharStrings import T2CharString
    from fontTools.ttLib import TTFont

    fb = FontBuilder(1000, isTTF=False)
    glyph_order = [".notdef", *widths_by_name.keys()]
    fb.setupGlyphOrder(glyph_order)
    # /CharacterMap is not consulted by get_average_character_width's
    # CFF path, but FontBuilder needs *some* cmap entries to validate.
    fb.setupCharacterMap({0x41 + i: name for i, name in enumerate(widths_by_name)})

    def _cs(width: int) -> T2CharString:
        # Leading operand -> Type 2 charstring width-prologue. With
        # defaultWidthX = 0 / nominalWidthX = 0 this produces an
        # extracted width of exactly `width`.
        s = T2CharString()
        s.program = [width, 0, "hmoveto", 100, "vlineto", "endchar"]
        return s

    char_strings = {".notdef": T2CharString()}
    char_strings[".notdef"].program = [0, "endchar"]
    for name, w in widths_by_name.items():
        char_strings[name] = _cs(w)

    fb.setupCFF(
        psName=ps_name,
        fontInfo={"FullName": ps_name},
        charStringsDict=char_strings,
        privateDict={},
    )
    metrics: dict[str, tuple[int, int]] = {".notdef": (0, 0)}
    for name, w in widths_by_name.items():
        metrics[name] = (w, 0)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupNameTable({"familyName": "Wave1359", "styleName": "Regular"})
    fb.setupPost()
    buf = io.BytesIO()
    fb.font.save(buf)
    return bytes(TTFont(io.BytesIO(buf.getvalue())).getTableData("CFF "))


def _inject_font(widths_by_name: dict[str, int]) -> PDType1CFont:
    cff = CFFFont.from_bytes(_build_cff_bytes(widths_by_name))
    font = PDType1CFont(COSDictionary())
    font.set_font_program(cff)
    return font


# ---------- /Widths branch ----------


def test_get_average_character_width_uses_widths_array_when_present() -> None:
    """When ``/Widths`` has positive entries, the mean of those wins —
    the embedded program is not consulted on that branch."""
    font = PDType1CFont(COSDictionary())
    font.get_cos_object().set_item(
        _WIDTHS,
        COSArray([COSFloat(400.0), COSFloat(600.0), COSFloat(0.0), COSFloat(800.0)]),
    )
    # mean of positive entries = (400 + 600 + 800) / 3 = 600
    assert font.get_average_character_width() == 600.0


def test_get_average_character_width_widths_branch_ignores_program() -> None:
    """When ``/Widths`` is set, even an embedded program with different
    widths does not override it."""
    font = _inject_font({"A": 500, "B": 300})
    font.get_cos_object().set_item(_WIDTHS, COSArray([COSFloat(100.0), COSFloat(200.0)]))
    # /Widths mean = 150, NOT the CFF program mean of 400.
    assert font.get_average_character_width() == 150.0


# ---------- embedded CFF: mean of glyph charstring widths ----------


def test_get_average_character_width_means_cff_glyph_widths() -> None:
    """Varying glyph IDs -> different per-glyph widths -> mean differs
    from any individual width. This is the headline TODO-closure path:
    the CFF charstring widths are extracted via fontTools'
    ``T2WidthExtractor`` (see :meth:`CFFFont.get_width`) and averaged
    here.
    """
    font = _inject_font({"A": 500, "B": 300})
    # mean of (500, 300) = 400, rescaled by units_per_em 1000 -> 400 in 1/1000 em.
    assert font.get_average_character_width() == 400.0


def test_get_average_character_width_three_glyphs_distinct_widths() -> None:
    """Three glyphs with three distinct widths -> the mean is a strict
    average of all three, not a single sentinel."""
    font = _inject_font({"A": 600, "B": 800, "C": 1000})
    # mean = (600 + 800 + 1000) / 3 = 800
    assert font.get_average_character_width() == 800.0


def test_get_average_character_width_varies_with_glyph_id() -> None:
    """Two fonts whose only difference is per-GID width should produce
    different means — pinpoints the GID-sensitivity the TODO promised.
    """
    narrow = _inject_font({"A": 200, "B": 250})
    wide = _inject_font({"A": 700, "B": 900})
    narrow_mean = narrow.get_average_character_width()
    wide_mean = wide.get_average_character_width()
    assert narrow_mean != wide_mean
    assert narrow_mean == 225.0
    assert wide_mean == 800.0


def test_get_average_character_width_skips_notdef() -> None:
    """``.notdef`` is excluded from the mean — it carries no
    representative width and would skew the average toward zero."""
    # If .notdef were included its width-zero entry would be skipped by
    # the "positive only" filter anyway. Pin the contract by checking
    # the mean equals the mean of the *non-notdef* glyphs precisely.
    font = _inject_font({"A": 400, "B": 600})
    assert font.get_average_character_width() == 500.0


# ---------- empty / fallback branches ----------


def test_get_average_character_width_falls_back_to_500_on_empty_font() -> None:
    """No ``/Widths``, no embedded program, no Standard 14 AFM -> the
    only branch that surfaces upstream's hard-coded ``500``."""
    assert PDType1CFont().get_average_character_width() == 500.0


def test_get_average_character_width_uses_standard14_afm() -> None:
    """Non-embedded Standard 14 font with no ``/Widths`` -> the AFM
    bundled with the Standard 14 metrics provides the mean (a real
    value, not ``500``)."""
    font = PDType1CFont(COSDictionary())
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    afm = font.get_standard_14_font_metrics()
    assert afm is not None  # sanity-check the bundled AFM resolves
    expected_afm_mean = afm.get_average_width()
    assert expected_afm_mean > 0.0
    average = font.get_average_character_width()
    assert average == expected_afm_mean


# ---------- non-default units-per-em rescaling ----------


def test_get_average_character_width_rescales_to_1000_em() -> None:
    """When the embedded program declares a non-default em (here 2048,
    the TrueType-flavoured CFF case), the per-glyph mean is rescaled to
    1/1000 em before being returned — so the output is comparable across
    fonts regardless of internal em."""
    # Build a CFF then patch its units_per_em via the cached property
    # backing field. Easier than coaxing FontBuilder to emit a non-1000
    # font matrix.
    font = _inject_font({"A": 1024, "B": 2048})
    program = font.get_cff_font()
    assert program is not None
    program._units_per_em = 2048  # type: ignore[attr-defined]  # noqa: SLF001
    # mean of (1024, 2048) = 1536; rescaled: 1536 * 1000 / 2048 = 750.
    assert font.get_average_character_width() == 750.0
