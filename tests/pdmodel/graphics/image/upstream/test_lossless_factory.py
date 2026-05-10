"""Ported upstream tests from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/image/LosslessFactoryTest.java``.

Translated from JUnit 5 to pytest per CLAUDE.md §"Test Porting
Conventions". The upstream test class is keyed on
``java.awt.image.BufferedImage`` types (``TYPE_BYTE_GRAY``,
``TYPE_INT_ARGB`` …) and validates the PDImageXObject metadata after
``LosslessFactory.createFromImage``. The Python port keeps the
metadata assertions intact and substitutes Pillow image construction
for the AWT type system.

Skipped upstream tests (require rendering-cluster work or fixtures
not yet imported):

- ``testCreateLosslessFromImageRGB`` — relies on
  ``ValidateXImage.checkIdent`` which compares decoded pixel rasters
  via the upstream rendering reader; the metadata-only equivalents
  live in the hand-written test module.
- ``testCreateLosslessFromImageINT_ARGB`` /
  ``testCreateLosslessFromImage4BYTE_ABGR`` — call
  ``ximage.getOpaqueImage`` and ``ximage.getImage`` (rendering
  pipeline) and compare to ``BufferedImage`` rasters.
- ``testCreateLosslessFromImageBITMASK_INT_ARGB`` /
  ``testCreateLosslessFromImageBITMASK4BYTE_ABGR`` — ``Transparency.BITMASK``
  is an AWT-specific concept; PIL has no equivalent at the BufferedImage
  level. The 1-bit / smask split is exercised in the hand-written
  ``P``-mode transparency test instead.
- ``testCreateLosslessFromImageUSHORT_555_RGB`` — TYPE_USHORT_555_RGB
  is AWT-specific (5/5/5 packing in a UInt16). PIL does not have a
  matching mode; converting to RGB defeats the test.
- ``testCreateLosslessFromTransparentGIF`` /
  ``testCreateLosslessFromTransparent1BitGIF`` — depend on the upstream
  ``gif.gif`` and ``gif-1bit-transparent.gif`` resources which are not
  imported into ``tests/fixtures``.
- ``testCreateLosslessFromGovdocs032163`` /
  ``testCreateLosslessFrom16BitPNG`` — depend on
  ``target/imgs/PDFBOX-4184-*`` resources not in this tree.
- ``testCreateLosslessFromImageCMYK`` — depends on the
  ``ISOcoated_v2_300_bas.icc`` resource and ICC-based color space
  embedding, deferred to a later cluster.
- ``testCreateLosslessFrom16Bit`` — exercises 16-bit RGB through the
  predictor encoder; we have a 16-bit grayscale equivalent and the
  predictor path is not yet implemented in the port.
- ``testCreateLosslessFromImageINT_BGR`` /
  ``testCreateLosslessFromImageINT_RGB`` /
  ``testCreateLosslessFromImageBYTE_3BGR`` — these all check that
  different AWT in-memory layouts produce the same RGB body. PIL
  uniformly stores ``"RGB"`` as packed bytes regardless of the
  caller's source layout, so the test would degenerate to "RGB → RGB"
  and add nothing over the hand-written RGB test.

Ported are the metadata-shape checks (width, height, BPC, color space
name) that exercise behaviour expressible without the rendering
pipeline.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.graphics.image import LosslessFactory, PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument


def _make_source_rgb(width: int = 33, height: int = 21) -> Image.Image:
    """Substitute for upstream's ``png.png`` resource: paint a small
    RGB canvas so the test exercises a non-trivial pixel grid (no
    multiple-of-8 width). Color content does not matter for the
    metadata assertions ported here."""
    src = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(src)
    draw.rectangle((0, 0, width // 2, height // 2), fill=(255, 0, 0))
    draw.rectangle((width // 2, height // 2, width - 1, height - 1), fill=(0, 0, 255))
    return src


def _validate(
    image_x: PDImageXObject,
    bpc: int,
    width: int,
    height: int,
    color_space_name: str,
) -> None:
    """Mirrors upstream ``ValidateXImage.validate`` (metadata-only
    portion). Confirms the dictionary entries ``LosslessFactory`` is
    expected to write."""
    assert image_x.get_bits_per_component() == bpc
    assert image_x.get_width() == width
    assert image_x.get_height() == height
    cs = image_x.get_color_space_cos_object()
    if isinstance(cs, COSName):
        assert cs.name == color_space_name
    elif isinstance(cs, COSArray):
        # Indexed / array form: first entry is the CS name.
        first = cs.get_object(0)
        assert isinstance(first, COSName)
        assert first.name == color_space_name
    else:
        raise AssertionError(f"unexpected /ColorSpace type: {type(cs).__name__}")


# ---------- ported metadata assertions ----------


def test_create_lossless_from_image_rgb() -> None:
    """Metadata portion of ``testCreateLosslessFromImageRGB`` —
    asserts that an opaque RGB source maps to ``/DeviceRGB`` 8 BPC."""
    document = PDDocument()
    image = _make_source_rgb()
    image_x = LosslessFactory.create_from_image(document, image)
    _validate(image_x, 8, image.width, image.height, "DeviceRGB")
    assert image_x.get_soft_mask() is None


def test_create_lossless_from_image_gray() -> None:
    """``BufferedImage.TYPE_BYTE_GRAY`` equivalent: 8-bit ``L`` source
    → ``/DeviceGray`` 8 BPC. (Upstream nests this inside the same
    ``testCreateLosslessFromImageRGB`` block.)"""
    document = PDDocument()
    image = _make_source_rgb().convert("L")
    image_x = LosslessFactory.create_from_image(document, image)
    _validate(image_x, 8, image.width, image.height, "DeviceGray")
    assert image_x.get_soft_mask() is None


def test_create_lossless_from_image_bitonal() -> None:
    """``BufferedImage.TYPE_BYTE_BINARY`` equivalent: 1-bit ``1``
    source → ``/DeviceGray`` 1 BPC. Upstream picks a width that is
    *not* a multiple of 8 to test the row-padding code path; we keep
    that constraint."""
    document = PDDocument()
    image = _make_source_rgb().convert("1")
    assert image.width % 8 != 0  # mirrors upstream's assertNotEquals check
    image_x = LosslessFactory.create_from_image(document, image)
    _validate(image_x, 1, image.width, image.height, "DeviceGray")
    assert image_x.get_soft_mask() is None


def test_create_lossless_from_image_argb_attaches_smask() -> None:
    """Metadata portion of ``testCreateLosslessFromImageINT_ARGB``:
    a translucent RGBA source → ``/DeviceRGB`` 8 BPC body and an
    8-bit ``/DeviceGray`` ``/SMask``."""
    document = PDDocument()
    image = _make_source_rgb().convert("RGBA")
    # Vary alpha so the SMask is non-trivial.
    width, height = image.size
    pixels = image.load()
    assert pixels is not None
    for y in range(height):
        for x in range(width):
            r, g, b, _ = pixels[x, y]
            pixels[x, y] = (r, g, b, (y // 4 * 4) % 256)

    image_x = LosslessFactory.create_from_image(document, image)
    _validate(image_x, 8, width, height, "DeviceRGB")

    smask = image_x.get_soft_mask()
    assert smask is not None
    _validate(smask, 8, width, height, "DeviceGray")


# ---------- helper-level entry points (parity with private helpers) ----------


def test_is_gray_image_dispatch_matches_create_from_image() -> None:
    """Mirrors upstream private ``isGrayImage`` (Java line 118): when it
    returns true, ``createFromImage`` routes through ``createFromGrayImage``;
    when false, through the predictor / RGB encoder. The Python port wires
    the same dispatch — confirm the predicate's verdict matches the
    DeviceGray vs DeviceRGB color-space stamp on the resulting XObject."""
    document = PDDocument()

    gray = _make_source_rgb().convert("L")
    assert LosslessFactory.is_gray_image(gray)
    cs_gray = LosslessFactory.create_from_image(document, gray)\
        .get_color_space_cos_object()
    assert isinstance(cs_gray, COSName) and cs_gray.name == "DeviceGray"

    rgb = _make_source_rgb()
    assert not LosslessFactory.is_gray_image(rgb)
    cs_rgb = LosslessFactory.create_from_image(document, rgb)\
        .get_color_space_cos_object()
    assert isinstance(cs_rgb, COSName) and cs_rgb.name == "DeviceRGB"


def test_create_from_gray_image_helper_matches_dispatch() -> None:
    """Calling the helper directly produces the same metadata shape as
    routing through the public entry point — mirrors upstream's
    ``createFromGrayImage`` (Java line 136) being the inner workhorse for
    grayscale dispatch."""
    document = PDDocument()
    gray = _make_source_rgb().convert("L")

    via_helper = LosslessFactory.create_from_gray_image(gray, document)
    via_public = LosslessFactory.create_from_image(document, gray)

    _validate(via_helper, 8, gray.width, gray.height, "DeviceGray")
    _validate(via_public, 8, gray.width, gray.height, "DeviceGray")


def test_create_from_rgb_image_helper_matches_dispatch() -> None:
    """Calling ``createFromRGBImage`` (Java line 164) directly produces
    the same metadata shape as routing through the public entry point."""
    document = PDDocument()
    rgb = _make_source_rgb()

    via_helper = LosslessFactory.create_from_rgb_image(rgb, document)
    via_public = LosslessFactory.create_from_image(document, rgb)

    _validate(via_helper, 8, rgb.width, rgb.height, "DeviceRGB")
    _validate(via_public, 8, rgb.width, rgb.height, "DeviceRGB")


def test_prepare_image_x_object_helper_smoke() -> None:
    """``LosslessFactory.prepareImageXObject`` (Java line 243) is the
    package-private helper every dispatch path funnels through. Confirm
    the Python equivalent stamps the same dictionary entries upstream
    does: /Width, /Height, /BitsPerComponent, /ColorSpace and a flate
    /Filter."""
    from pypdfbox.pdmodel.graphics.color import PDDeviceRGB

    document = PDDocument()
    width, height = 4, 2
    raw = bytes(range(width * height * 3))
    image_x = LosslessFactory.prepare_image_x_object(
        document, raw, width, height, 8, PDDeviceRGB.INSTANCE
    )
    _validate(image_x, 8, width, height, "DeviceRGB")
    f = image_x.get_filter()
    assert isinstance(f, COSName) and f.name == "FlateDecode"
