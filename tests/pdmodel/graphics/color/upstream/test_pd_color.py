"""Ported parity tests for ``PDColor`` constructor variants.

Translated from upstream Apache PDFBox (3.0.x) tests covering the three
``PDColor`` constructors:

- ``PDColor(float[], PDColorSpace)``
- ``PDColor(float[], COSName, PDColorSpace)``
- ``PDColor(COSArray, PDColorSpace)``

PDFBox's own JUnit suite for ``PDColor`` is small (the value class is
mostly exercised indirectly by content-stream and image tests); these
cases mirror the constructor invariants asserted by the upstream class
(component defensive copies, pattern-name preservation, COSArray
parsing) and the ``equals``/``hashCode`` semantics declared on the class.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern


def test_components_color_space_constructor() -> None:
    color = PDColor([1.0, 0.5, 0.25], PDDeviceRGB.INSTANCE)
    assert color.get_components() == [1.0, 0.5, 0.25]
    assert color.get_color_space() is PDDeviceRGB.INSTANCE
    assert color.get_pattern_name() is None


def test_components_pattern_color_space_constructor() -> None:
    name = COSName.get_pdf_name("P1")
    pattern_cs = PDPattern()
    color = PDColor([0.4, 0.6], name, pattern_cs)
    assert color.get_components() == [0.4, 0.6]
    assert color.get_pattern_name() is name
    assert color.get_color_space() is pattern_cs


def test_cos_array_constructor_no_pattern() -> None:
    array = COSArray()
    # Values exact in IEEE-754 float32 to survive COSFloat round-tripping.
    array.add(COSFloat(0.125))
    array.add(COSFloat(0.25))
    array.add(COSFloat(0.5))
    color = PDColor(array, PDDeviceRGB.INSTANCE)
    assert color.get_components() == [0.125, 0.25, 0.5]
    assert color.get_pattern_name() is None


def test_cos_array_constructor_with_pattern_name() -> None:
    # Uncolored tiling form: tint components against an underlying CS
    # (DeviceRGB → 3 tints) plus a pattern name. Match the underlying
    # arity so PDFBOX-4279's pad-to-N inside ``get_components()`` is a
    # no-op.
    from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern

    pattern_cs = PDPattern(PDDeviceRGB.INSTANCE)
    array = COSArray()
    array.add(COSFloat(0.5))
    array.add(COSFloat(0.25))
    array.add(COSFloat(0.75))
    name = COSName.get_pdf_name("P1")
    array.add(name)
    color = PDColor(array, pattern_cs)
    assert color.get_components() == [0.5, 0.25, 0.75]
    assert color.get_pattern_name() == name


def test_get_components_returns_a_copy() -> None:
    color = PDColor([0.5, 0.5, 0.5], PDDeviceRGB.INSTANCE)
    components = color.get_components()
    components[0] = 0.0
    # Original is unchanged.
    assert color.get_components() == [0.5, 0.5, 0.5]


def test_to_cos_array_round_trips_components() -> None:
    # Values exact in IEEE-754 float32 to survive COSFloat truncation.
    color = PDColor([0.125, 0.25, 0.5], PDDeviceRGB.INSTANCE)
    array = color.to_cos_array()
    rebuilt = PDColor(array, PDDeviceRGB.INSTANCE)
    assert rebuilt.get_components() == color.get_components()


def test_to_cos_array_includes_pattern_name() -> None:
    name = COSName.get_pdf_name("P1")
    color = PDColor([0.5, 0.5], name, PDPattern())
    array = color.to_cos_array()
    # Pattern name is the trailing entry in the COSArray.
    last = array.get_object(array.size() - 1)
    assert isinstance(last, COSName)
    assert last == name


def test_equals_and_hash_for_identical_values() -> None:
    a = PDColor([0.5, 0.5, 0.5], PDDeviceRGB.INSTANCE)
    b = PDColor([0.5, 0.5, 0.5], PDDeviceRGB.INSTANCE)
    assert a == b
    assert hash(a) == hash(b)


def test_equals_distinguishes_different_components() -> None:
    a = PDColor([0.5, 0.5, 0.5], PDDeviceRGB.INSTANCE)
    b = PDColor([0.6, 0.5, 0.5], PDDeviceRGB.INSTANCE)
    assert a != b


def test_equals_distinguishes_different_pattern_name() -> None:
    pattern_cs = PDPattern()
    a = PDColor([], COSName.get_pdf_name("P1"), pattern_cs)
    b = PDColor([], COSName.get_pdf_name("P2"), pattern_cs)
    assert a != b


def test_initial_color_for_device_gray_is_black() -> None:
    initial = PDDeviceGray.INSTANCE.get_initial_color()
    assert initial.get_components() == [0.0]
    assert initial.get_color_space() is PDDeviceGray.INSTANCE


# ---------- to_rgb / get_java_color (upstream parity) ----------


def test_to_rgb_returns_three_floats_in_unit_range() -> None:
    rgb = PDColor([0.5], PDDeviceGray.INSTANCE).to_rgb()
    assert isinstance(rgb, tuple)
    assert len(rgb) == 3
    for c in rgb:
        assert 0.0 <= c <= 1.0


def test_get_java_color_matches_to_rgb() -> None:
    # Upstream returns ``java.awt.Color``; we return a tuple of floats.
    color = PDColor([0.2, 0.4, 0.6], PDDeviceRGB.INSTANCE)
    assert color.get_java_color() == color.to_rgb()


# ---------- to_string (upstream PDColor.toString parity) ----------


def test_to_string_shape_matches_upstream() -> None:
    # Java's ``PDColor.toString()`` renders as
    # ``PDColor{components=[...], patternName=..., colorSpace=...}``
    # with a trailing ``.0`` on integral floats (Java
    # ``Float.toString``) and a leading space after commas
    # (``Arrays.toString``). We mirror both.
    color = PDColor([0.0, 1.0, 0.5], PDDeviceRGB.INSTANCE)
    s = color.to_string()
    assert s.startswith("PDColor{components=[0.0, 1.0, 0.5], ")
    assert "patternName=None" in s
    assert "colorSpace=" in s
    # str() delegates to to_string() — they must agree.
    assert str(color) == s


def test_to_string_includes_pattern_name() -> None:
    name = COSName.get_pdf_name("P1")
    color = PDColor([0.5, 0.25], name, PDPattern())
    s = color.to_string()
    assert "components=[0.5, 0.25]" in s
    # COSName renders as its own __str__; we just need it referenced.
    assert "patternName=" in s
    assert "P1" in s


# ---------- init_components (upstream PDColor.initComponents parity) ----------


def test_init_components_from_cos_array_replaces_components() -> None:
    color = PDColor([0.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
    array = COSArray()
    array.add(COSFloat(0.125))
    array.add(COSFloat(0.25))
    array.add(COSFloat(0.5))
    color.init_components(array)
    assert color.get_components() == [0.125, 0.25, 0.5]


def test_init_components_skips_trailing_pattern_name() -> None:
    # Upstream private helper ``initComponents`` runs over an array sized
    # (length-1) when the trailing entry is a pattern name; here we
    # delegate to the parser, which already excludes the trailing name.
    # Use a Pattern color space so ``get_components`` returns the raw
    # internal list without padding to the cs arity.
    color = PDColor([0.0, 0.0], COSName.get_pdf_name("P1"), PDPattern())
    array = COSArray()
    array.add(COSFloat(0.5))
    array.add(COSFloat(0.25))
    array.add(COSName.get_pdf_name("P2"))
    color.init_components(array)
    assert color.get_components() == [0.5, 0.25]
