"""Tests ported from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/image/CCITTFactoryTest.java``.

Several upstream tests rely on real-world CCITT TIFF fixtures
(``ccittg3.tif``, ``ccittg4.tif``, ``ccittg4multi.tif``, the
``ccittg3-garbage-padded-fields*.tif`` pair, and a remote ``Wing.tif``)
that are not yet vendored into ``tests/fixtures/``. Those are skipped
for now and listed below so a future fixture-vendoring wave can pick
them up:

* ``testCreateFromRandomAccessSingle``
* ``testCreateFromRandomAccessMulti``
* ``testCreateFromFileLock`` / ``testCreateFromFileNumberLock`` -- the
  hand-written test ``test_create_from_file_does_not_lock_source_file``
  in ``tests/pdmodel/graphics/image/test_ccitt_factory.py`` exercises
  the same property using a synthetic single-strip TIFF.
* ``testByteShortPaddedWithGarbage``
* ``testFillOrder2`` (downloads ``Wing.tif`` from a JIRA URL).

The synthetic ``testCreateFromBufferedChessImage`` ports cleanly: a
non-multiple-of-8 width is the only thing the test cares about and we
can build that with Pillow alone.
"""
from __future__ import annotations

import io

from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.graphics.color import PDDeviceGray
from pypdfbox.pdmodel.graphics.image import CCITTFactory


def test_create_from_buffered_chess_image() -> None:
    """Port of upstream ``testCreateFromBufferedChessImage``.

    Builds a 343x287 chess pattern (width is *not* a multiple of 8) and
    encodes it via CCITT Group 4. Mirrors upstream's ``BufferedImage(..,
    TYPE_BYTE_BINARY)`` loop and final ``validate(.., 1, 343, 287, ..)``
    check.
    """
    from pypdfbox.pdmodel.pd_document import PDDocument

    document = PDDocument()
    bim = Image.new("1", (343, 287), color=1)
    assert (bim.width // 8) * 8 != bim.width  # not a multiple of 8

    col = 1
    for x in range(bim.width):
        for y in range(bim.height):
            bim.putpixel((x, y), col & 1)
            col = ~col & 0xFFFFFFFF

    image_x = CCITTFactory.create_from_image(document, bim)

    assert image_x.get_width() == 343
    assert image_x.get_height() == 287
    assert image_x.get_bits_per_component() == 1
    cs = image_x.get_color_space()
    assert isinstance(cs, type(PDDeviceGray.INSTANCE))
    assert image_x.get_filter() == COSName.get_pdf_name("CCITTFaxDecode")


def test_create_from_buffered_image_round_trips_pixels() -> None:
    """Light-weight stand-in for upstream ``testCreateFromBufferedImage``.

    Upstream loads ``ccittg4.tif``, decodes it, re-encodes via
    ``CCITTFactory.createFromImage``, then asserts the decoded raster
    matches the original. We synthesize a 1-bit image instead so we can
    run without the binary fixture, but exercise the same encode→decode
    round-trip.
    """
    from pypdfbox.cos import COSStream
    from pypdfbox.filter import CCITTFaxDecode
    from pypdfbox.pdmodel.pd_document import PDDocument

    document = PDDocument()
    bim = Image.new("1", (48, 24), color=1)
    for x in range(0, 48, 3):
        for y in range(24):
            bim.putpixel((x, y), 0)

    image_x = CCITTFactory.create_from_image(document, bim)
    cos = image_x.get_cos_object()
    assert isinstance(cos, COSStream)

    out = io.BytesIO()
    CCITTFaxDecode().decode(io.BytesIO(cos.get_raw_data()), out, cos)
    assert out.getvalue() == bim.tobytes()
