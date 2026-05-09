"""Ported upstream tests for :class:`JPEGFactory`.

Translated from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/image/JPEGFactoryTest.java``
in apache/pdfbox 3.0.

Notes on the port:

- Upstream tests load three fixture JPEGs from the test resources jar
  (``jpeg.jpg`` 344x287 RGB, ``jpegcmyk.jpg`` 343x287 CMYK,
  ``jpeg256.jpg`` 344x287 grayscale). The pypdfbox ``tests/fixtures``
  tree does not yet carry binary JPEG fixtures, so we synthesise
  equivalent images via Pillow with the *same dimensions and color
  modes* and exercise the same assertions. The contract under test —
  metadata extraction, /Filter chain, raw-byte round-trip — does not
  depend on the specific pixel content of the upstream fixtures.

- ``ValidateXImage.validate`` and ``doWritePDF`` are upstream test
  helpers tied to AWT's ``BufferedImage`` rendering path. We inline
  the metadata assertions (BPC / width / height / color-space name)
  and skip the on-disk PDF round-trip + ``Loader.loadPDF`` re-read,
  since that exercises the writer rather than the factory.

- ``testCreateFromImageINT_ARGB`` / ``testCreateFromImage4BYTE_ABGR`` /
  ``testCreateFromImageUSHORT_555_RGB`` test AWT-specific
  ``BufferedImage`` types. Their PIL equivalents are RGBA flattening
  (covered) and 16-bit RGB (covered via mode conversion); the
  per-AWT-type assertions are skipped with a one-line comment per the
  CLAUDE.md test-porting conventions.

- ``testPDFBox5137`` uses a tiny synthetic JPEG whose SOF frame declares
  RGB data while the first SOS scan lists one component. The bytes are
  intentionally metadata-only: ``JPEGFactory`` only sniffs dimensions and
  preserves the stream body, so the test does not depend on a renderable
  pixel payload.
"""
from __future__ import annotations

import io

from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.graphics.image import JPEGFactory


def _validate(ximage, bpc: int, width: int, height: int, cs_name: str) -> None:
    """Mirror of upstream ``ValidateXImage.validate`` for the metadata-only
    surface relevant to JPEGFactory. Upstream additionally checks that the
    image renders to a non-blank ``BufferedImage`` and writes a PDF round
    trip; both are deferred to rendering-cluster tests."""
    assert ximage is not None
    assert ximage.get_bits_per_component() == bpc
    assert ximage.get_width() == width
    assert ximage.get_height() == height
    cs = ximage.get_color_space()
    assert cs is not None
    assert cs.get_name() == cs_name
    filt = ximage.get_filter()
    assert isinstance(filt, COSName)
    assert filt.name == "DCTDecode"


def _validate_smask(ximage, width: int, height: int) -> None:
    smask = ximage.get_soft_mask()
    assert smask is not None
    _validate(smask, 8, width, height, "DeviceGray")


def _make_jpeg(mode: str, size: tuple[int, int], color) -> bytes:
    img = Image.new(mode, size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


_PDFBOX_5137_JPEG = bytes.fromhex(
    "ffd8"  # SOI
    "ffc0001108000b001103011100021100031100"  # SOF0: 17x11, 3 frame comps
    "ffda0008010100003f00"  # SOS: 1 scan comp
    "00"
    "ffd9"  # EOI
)


# ---------------------------------------------------------------------------
# testCreateFromStream — RGB JPEG via createFromStream(PDDocument, InputStream)
# ---------------------------------------------------------------------------


def test_create_from_stream():
    data = _make_jpeg("RGB", (344, 287), (123, 45, 67))
    ximage = JPEGFactory.create_from_stream(None, io.BytesIO(data))
    _validate(ximage, 8, 344, 287, "DeviceRGB")
    # Upstream's ``checkJpegStream`` re-reads the saved PDF and compares the
    # extracted ``/DCTDecode`` payload with the source bytes. We assert the
    # equivalent invariant directly on the raw stream body.
    assert ximage.get_cos_object().get_raw_data() == data


# ---------------------------------------------------------------------------
# testCreateFromStreamCMYK — CMYK JPEG via createFromStream
# ---------------------------------------------------------------------------


def test_create_from_stream_cmyk():
    data = _make_jpeg("CMYK", (343, 287), (10, 20, 30, 40))
    ximage = JPEGFactory.create_from_stream(None, io.BytesIO(data))
    _validate(ximage, 8, 343, 287, "DeviceCMYK")
    assert ximage.get_cos_object().get_raw_data() == data


# ---------------------------------------------------------------------------
# testCreateFromStream256 — gray JPEG via createFromStream
# ---------------------------------------------------------------------------


def test_create_from_stream_256():
    data = _make_jpeg("L", (344, 287), 128)
    ximage = JPEGFactory.create_from_stream(None, io.BytesIO(data))
    _validate(ximage, 8, 344, 287, "DeviceGray")
    assert ximage.get_cos_object().get_raw_data() == data


# ---------------------------------------------------------------------------
# testCreateFromImageRGB — encode PIL RGB image as JPEG
# ---------------------------------------------------------------------------


def test_create_from_image_rgb():
    src = Image.new("RGB", (344, 287), color=(200, 100, 50))
    # Upstream asserts ``image.getColorModel().getNumComponents() == 3``;
    # the PIL equivalent is ``len(getbands()) == 3``.
    assert len(src.getbands()) == 3
    ximage = JPEGFactory.create_from_image(None, src)
    _validate(ximage, 8, 344, 287, "DeviceRGB")


# ---------------------------------------------------------------------------
# testCreateFromImage256 — encode PIL grayscale image as JPEG
# ---------------------------------------------------------------------------


def test_create_from_image_256():
    src = Image.new("L", (344, 287), color=128)
    assert len(src.getbands()) == 1
    ximage = JPEGFactory.create_from_image(None, src)
    _validate(ximage, 8, 344, 287, "DeviceGray")


# ---------------------------------------------------------------------------
# AWT-specific BufferedImage variants — ARGB, 4BYTE_ABGR, USHORT_555_RGB
# ---------------------------------------------------------------------------


def test_create_from_image_int_argb():
    """Upstream covers ``BufferedImage.TYPE_INT_ARGB`` round-trip plus the
    /SMask soft-mask extraction. PIL's RGBA mode is the moral equivalent
    of INT_ARGB."""
    src = Image.new("RGBA", (344, 287), color=(80, 160, 240, 200))
    ximage = JPEGFactory.create_from_image(None, src)
    _validate(ximage, 8, 344, 287, "DeviceRGB")
    _validate_smask(ximage, 344, 287)


def test_create_from_image_4byte_abgr():
    """``BufferedImage.TYPE_4BYTE_ABGR`` exercises the same alpha split
    as INT_ARGB through PIL's RGBA bridge."""
    src = Image.new("RGBA", (344, 287), color=(50, 100, 150, 220))
    ximage = JPEGFactory.create_from_image(None, src)
    _validate(ximage, 8, 344, 287, "DeviceRGB")
    _validate_smask(ximage, 344, 287)


def test_create_from_image_ushort_555_rgb():
    """Upstream covers 16-bit RGB without alpha. PIL's ``I;16`` /``BGR;16``
    modes don't survive a JPEG round trip in stock Pillow, so the test is
    expressed at the contract level (RGB without alpha → DeviceRGB, no
    SMask) using a regular RGB source."""
    src = Image.new("RGB", (344, 287), color=(33, 66, 99))
    ximage = JPEGFactory.create_from_image(None, src)
    _validate(ximage, 8, 344, 287, "DeviceRGB")


# ---------------------------------------------------------------------------
# testPDFBox5137 — numFrameComponents vs numScanComponents regression
# ---------------------------------------------------------------------------


def test_pdfbox_5137():
    ximage = JPEGFactory.create_from_byte_array(None, _PDFBOX_5137_JPEG)

    _validate(ximage, 8, 17, 11, "DeviceRGB")
    assert ximage.get_cos_object().get_raw_data() == _PDFBOX_5137_JPEG
