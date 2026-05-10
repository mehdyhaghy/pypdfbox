"""Ported from upstream PDFBox tests for ``BlendMode``.

PDFBox's blend-mode logic does not ship with a dedicated JUnit test class —
the algorithms are exercised indirectly through ``TestBlendMode`` in
``pdfbox/src/test/java/org/apache/pdfbox/rendering`` (which renders sample
PDFs through ``BlendComposite`` and compares to reference rasters; ports of
those rendering tests live in ``tests/rendering``). The few API-level
expectations that *are* documented in the upstream Javadoc / changelog
appear below as a small, focused parity suite so the dispatch surface
matches PDFBox's ``BlendMode.getInstance``:

* ``getInstance(null)`` → ``Normal``
* ``getInstance(COSName.MULTIPLY)`` → ``Multiply``
* ``getInstance(COSArray of names)`` → first recognised mode in the array
* unrecognised names → ``Normal`` fallback
* ``Compatible`` (Adobe synonym noted in §11.6.5.2) → ``Normal``
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.graphics.blend_mode import BlendMode


def test_get_instance_null():
    # Java: assertSame(BlendMode.NORMAL, BlendMode.getInstance(null));
    assert BlendMode.get_instance(None) is BlendMode.NORMAL


def test_get_instance_normal_name():
    assert (
        BlendMode.get_instance(COSName.get_pdf_name("Normal"))
        is BlendMode.NORMAL
    )


def test_get_instance_compatible_aliases_normal():
    # PDF 32000-1 §11.6.5.2 footnote — Adobe maps Compatible → Normal.
    assert (
        BlendMode.get_instance(COSName.get_pdf_name("Compatible"))
        is BlendMode.NORMAL
    )


def test_get_instance_each_standard_separable_mode():
    for name, expected in (
        ("Multiply", BlendMode.MULTIPLY),
        ("Screen", BlendMode.SCREEN),
        ("Overlay", BlendMode.OVERLAY),
        ("Darken", BlendMode.DARKEN),
        ("Lighten", BlendMode.LIGHTEN),
        ("ColorDodge", BlendMode.COLOR_DODGE),
        ("ColorBurn", BlendMode.COLOR_BURN),
        ("HardLight", BlendMode.HARD_LIGHT),
        ("SoftLight", BlendMode.SOFT_LIGHT),
        ("Difference", BlendMode.DIFFERENCE),
        ("Exclusion", BlendMode.EXCLUSION),
    ):
        assert (
            BlendMode.get_instance(COSName.get_pdf_name(name)) is expected
        )


def test_get_instance_each_standard_non_separable_mode():
    for name, expected in (
        ("Hue", BlendMode.HUE),
        ("Saturation", BlendMode.SATURATION),
        ("Color", BlendMode.COLOR),
        ("Luminosity", BlendMode.LUMINOSITY),
    ):
        assert (
            BlendMode.get_instance(COSName.get_pdf_name(name)) is expected
        )


def test_get_instance_unknown_name_falls_back_to_normal():
    assert (
        BlendMode.get_instance(COSName.get_pdf_name("BogusMode"))
        is BlendMode.NORMAL
    )


def test_get_instance_array_first_recognised():
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Frobnicate"))
    arr.add(COSName.get_pdf_name("Multiply"))
    arr.add(COSName.get_pdf_name("Screen"))
    assert BlendMode.get_instance(arr) is BlendMode.MULTIPLY


def test_get_instance_array_no_match_returns_normal():
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Bogus1"))
    arr.add(COSName.get_pdf_name("Bogus2"))
    assert BlendMode.get_instance(arr) is BlendMode.NORMAL


def test_separable_modes_are_separable():
    for mode in (
        BlendMode.NORMAL,
        BlendMode.MULTIPLY,
        BlendMode.SCREEN,
        BlendMode.OVERLAY,
        BlendMode.DARKEN,
        BlendMode.LIGHTEN,
        BlendMode.COLOR_DODGE,
        BlendMode.COLOR_BURN,
        BlendMode.HARD_LIGHT,
        BlendMode.SOFT_LIGHT,
        BlendMode.DIFFERENCE,
        BlendMode.EXCLUSION,
    ):
        assert mode.is_separable()


def test_non_separable_modes_are_not_separable():
    for mode in (
        BlendMode.HUE,
        BlendMode.SATURATION,
        BlendMode.COLOR,
        BlendMode.LUMINOSITY,
    ):
        assert not mode.is_separable()


# ---------------------------------------------------------------------------
# Parity for the upstream private static helpers (BlendMode.java lines
# 165, 281, 286, 352, 391). These are package-private in Java, but mirror
# the math used by ``BlendComposite`` so we exercise them directly.
# ---------------------------------------------------------------------------


def test_get255_value_clamps_at_one():
    # Java: ``val >= 1.0 ? 255 : val * 255.0`` -> Math.floor -> int.
    assert BlendMode.get255_value(1.0) == 255
    assert BlendMode.get255_value(1.5) == 255


def test_get255_value_floors_intermediate():
    # 0.5 * 255 = 127.5 -> floor -> 127 (matches Java's ``(int) Math.floor``).
    assert BlendMode.get255_value(0.5) == 127
    assert BlendMode.get255_value(0.0) == 0
    # Slight drift from 1.0 still floors deterministically (here Python's
    # ``254/255 * 255`` rounds back to exactly 254.0, mirroring Java doubles).
    assert BlendMode.get255_value(254 / 255) == 254
    # 0.25 -> 63.75 -> floor -> 63.
    assert BlendMode.get255_value(0.25) == 63


def test_to_string_separable():
    # Upstream: ``BlendMode{name=Multiply, isSeparable=true}``.
    assert (
        BlendMode.MULTIPLY.to_string()
        == "BlendMode{name=Multiply, isSeparable=true}"
    )


def test_to_string_non_separable():
    assert (
        BlendMode.HUE.to_string()
        == "BlendMode{name=Hue, isSeparable=false}"
    )


def test_create_blend_mode_map_contains_all_standard_names():
    m = BlendMode.create_blend_mode_map()
    # Upstream constructs a HashMap with capacity 13 but inserts 17 entries
    # (Normal, Compatible, 11 separable + 4 non-separable + Color).
    assert len(m) == 17
    assert m[COSName.get_pdf_name("Normal")] is BlendMode.NORMAL
    # ``Compatible`` is an explicit synonym for ``Normal`` (PDF 32000-1
    # §11.6.5.2 footnote — Adobe-recognised legacy name).
    assert m[COSName.get_pdf_name("Compatible")] is BlendMode.NORMAL
    assert m[COSName.get_pdf_name("Multiply")] is BlendMode.MULTIPLY
    assert m[COSName.get_pdf_name("Luminosity")] is BlendMode.LUMINOSITY


def test_get_saturation_rgb_zero_saturation_backdrop():
    # Backdrop has zero saturation -> result fills with backdrop green.
    result = [0.0, 0.0, 0.0]
    BlendMode.get_saturation_rgb((1.0, 0.0, 0.0), (0.5, 0.5, 0.5), result)
    expected = BlendMode.get255_value(0.5) / 255.0
    assert result == [expected, expected, expected]


def test_get_saturation_rgb_returns_inplace():
    # Spec / upstream: result list is written in place; function returns None.
    result = [0.0, 0.0, 0.0]
    out = BlendMode.get_saturation_rgb(
        (1.0, 0.0, 0.0), (0.4, 0.6, 0.2), result
    )
    assert out is None
    # Three components, all in [0, 1].
    assert len(result) == 3
    for v in result:
        assert 0.0 <= v <= 1.0


def test_get_luminosity_rgb_returns_inplace():
    result = [0.0, 0.0, 0.0]
    out = BlendMode.get_luminosity_rgb(
        (0.7, 0.2, 0.5), (0.1, 0.9, 0.3), result
    )
    assert out is None
    assert len(result) == 3
    for v in result:
        assert 0.0 <= v <= 1.0


def test_get_luminosity_rgb_matches_integer_arithmetic():
    # Pin the exact integer-arithmetic output for a known input so any drift
    # from the upstream Java algorithm shows up as a test failure rather
    # than silently changing rasters.
    result = [0.0, 0.0, 0.0]
    BlendMode.get_luminosity_rgb(
        (0.5, 0.5, 0.5), (0.2, 0.4, 0.6), result
    )
    # get255_value: 0.5 -> 127, 0.2 -> 51, 0.4 -> 102, 0.6 -> 153.
    # delta = ((127-51)*77 + (127-102)*151 + (127-153)*28 + 0x80) >> 8
    #       = (5852 + 3775 - 728 + 128) >> 8 = 9027 >> 8 = 35.
    # r=86, g=137, b=188 — none has the 0x100 bit, so no clipping branch.
    assert result == [86 / 255.0, 137 / 255.0, 188 / 255.0]
