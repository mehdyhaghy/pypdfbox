"""Upstream-anchored tests for :class:`PDSeparation`.

Apache PDFBox 3.0 does not ship a dedicated ``PDSeparationTest.java``;
the class is exercised indirectly through the parser/renderer integration
tests. The cases below mirror the **upstream Java doc-comment contract**
on ``org.apache.pdfbox.pdmodel.graphics.color.PDSeparation`` (the
class-level Javadoc and per-method comments) so that future re-syncs
against an actual ``PDSeparationTest.java`` (if/when upstream adds one)
have a stable starting point with minimal translation.

Each test is annotated with the upstream behaviour it pins.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.common.function import PDFunction
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation


def _type2(c0: list[float], c1: list[float]) -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", COSArray.of_cos_floats([0.0, 1.0]))
    d.set_item("C0", COSArray.of_cos_floats(c0))
    d.set_item("C1", COSArray.of_cos_floats(c1))
    d.set_item("N", COSFloat(1.0))
    return d


def _build(colorant: str, alternate: str, tint: COSDictionary) -> PDSeparation:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name(colorant))
    arr.add(COSName.get_pdf_name(alternate))
    arr.add(tint)
    return PDSeparation(arr)


def test_get_name_pins_separation_constant() -> None:
    """Upstream: ``getName() { return COSName.SEPARATION.getName(); }``"""
    assert PDSeparation().get_name() == "Separation"


def test_get_number_of_components_is_one() -> None:
    """Upstream: ``getNumberOfComponents()`` returns ``1``."""
    assert PDSeparation().get_number_of_components() == 1


def test_initial_color_is_full_tint() -> None:
    """Upstream: ``initialColor = new PDColor(new float[] { 1 }, this)``."""
    initial = PDSeparation().get_initial_color()
    assert initial.get_components() == [1.0]


def test_default_decode_returns_zero_one() -> None:
    """Upstream: ``getDefaultDecode()`` returns ``new float[] { 0, 1 }``."""
    assert PDSeparation().get_default_decode(8) == [0.0, 1.0]


def test_get_colorant_name_reads_array_index_1() -> None:
    """Upstream constants: ``COLORANT_NAMES = 1``."""
    cs = _build("PANTONE 185 C", "DeviceCMYK", _type2([0.0], [1.0]))
    assert cs.get_colorant_name() == "PANTONE 185 C"


def test_set_colorant_name_writes_array_index_1() -> None:
    """Upstream: ``setColorantName(name) { array.set(1, COSName.getPDFName(name)); }``"""
    cs = PDSeparation()
    cs.set_colorant_name("Spot1")
    arr = cs.get_cos_object()
    assert isinstance(arr, COSArray)
    assert arr.get_name(1) == "Spot1"


def test_get_alternate_color_space_reads_array_index_2() -> None:
    """Upstream constants: ``ALTERNATE_CS = 2``."""
    cs = _build("X", "DeviceRGB", _type2([0.0, 0.0, 0.0], [1.0, 0.0, 0.0]))
    alt = cs.get_alternate_color_space()
    assert alt is not None
    assert alt.get_name() == "DeviceRGB"


def test_get_tint_transform_returns_pd_function() -> None:
    """Upstream: ``getTintTransform()`` lazily initializes via
    ``PDFunction.create(array.getObject(TINT_TRANSFORM))`` and returns
    the typed function."""
    cs = _build("X", "DeviceRGB", _type2([0.0, 0.0, 0.0], [1.0, 0.0, 0.0]))
    fn = cs.get_tint_transform()
    assert isinstance(fn, PDFunction)
    assert fn.get_function_type() == 2


def test_to_rgb_pipes_through_tint_transform_then_alternate() -> None:
    """Upstream ``toRGB(value)``::

        float[] altColor = tintTransform.eval(value);
        return alternateColorSpace.toRGB(altColor);

    Translated to Python: input tint -> alt-CS coords -> RGB. Pin the
    end-to-end at a tint of 1.0 over a CMYK alternate.
    """
    cs = _build("SpotRed", "DeviceCMYK", _type2([0.0, 0.0, 0.0, 0.0], [0.0, 1.0, 1.0, 0.0]))
    rgb = cs.to_rgb([1.0])
    assert rgb is not None
    r, g, b = rgb
    assert abs(r - 1.0) < 1e-6
    assert abs(g - 0.0) < 1e-6
    assert abs(b - 0.0) < 1e-6


def test_tint_transform_helper_scales_to_0_255() -> None:
    """Upstream ``tintTransform(samples, alt)`` (PDSeparation.java line
    246): mutate ``samples`` from 0..255 to 0..1, eval the tint, scale
    each output back to 0..255 and write into ``alt``.
    """
    cs = _build("X", "DeviceCMYK", _type2([0.0, 0.0, 0.0, 0.0], [0.0, 1.0, 1.0, 0.0]))
    samples = [255.0]  # max tint in 8-bit raster space
    alt = [0, 0, 0, 0]
    cs.tint_transform(samples, alt)
    # tint_transform scales samples in-place to 0..1 first
    assert samples[0] == 1.0
    # Type 2 N=1: result is C1 = (0, 1, 1, 0); scaled to (0, 255, 255, 0)
    assert alt == [0, 255, 255, 0]


def test_to_rgb_image_renders_separation_to_rgb() -> None:
    """Upstream ``toRGBImage(WritableRaster)`` (PDSeparation.java line
    159) — full-tint pixel renders to red over the SpotRed/CMYK
    separation.
    """
    cs = _build("SpotRed", "DeviceCMYK", _type2([0.0, 0.0, 0.0, 0.0], [0.0, 1.0, 1.0, 0.0]))
    image = cs.to_rgb_image(b"\xff", 1, 1)
    assert image.size == (1, 1)
    assert image.mode == "RGB"
    assert image.getpixel((0, 0)) == (255, 0, 0)


def test_to_raw_image_returns_grayscale_pillow_image() -> None:
    """Upstream ``toRawImage`` (PDSeparation.java line 258) wraps the
    raster with ``ColorSpace.CS_GRAY`` — single-band tint ramp.
    """
    cs = _build("X", "DeviceCMYK", _type2([0.0], [1.0]))
    image = cs.to_raw_image(b"\x00\x80\xff", 3, 1)
    assert image.size == (3, 1)
    assert image.mode == "L"
    assert image.getpixel((0, 0)) == 0
    assert image.getpixel((1, 0)) == 0x80
    assert image.getpixel((2, 0)) == 0xFF


def test_to_string_includes_colorant_alternate_and_tint() -> None:
    """Upstream ``toString`` (PDSeparation.java line 317):
    ``Separation{"<colorant>" <alt name> <tint>}``.
    """
    cs = _build("PANTONE 185 C", "DeviceRGB", _type2([0.0, 0.0, 0.0], [1.0, 0.0, 0.0]))
    rendered = cs.to_string()
    assert rendered.startswith('Separation{"PANTONE 185 C" DeviceRGB ')
    assert rendered.endswith("}")
