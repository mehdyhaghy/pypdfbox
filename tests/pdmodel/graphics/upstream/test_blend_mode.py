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
