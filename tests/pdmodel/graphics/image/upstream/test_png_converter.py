"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/image/PNGConverterTest.java

Upstream baseline: PDFBox 3.0.x. Skipped translations (Java-only plumbing
or fixture-dependent paths per CLAUDE.md test porting conventions):

* ``dumpChunkTypes`` — diagnostic helper, ``@Test`` is commented out.
* ``testImageConversionRGB`` / ``...RGBGamma`` / ``...RGB16BitICC`` /
  ``...RGBIndexed`` / ``...RGBIndexedAlpha[1248]Bit`` /
  ``testImageConversionIntentIndexed`` and the failure-path variants
  ``testImageConversionRGBAlpha`` / ``...GrayAlpha`` / ``...Gray`` /
  ``...GrayGamma`` — every one needs a binary PNG fixture
  (``png.png``, ``png_rgb_gamma.png``, ``png_indexed.png``, …) that
  pypdfbox does not bundle. The upstream tests also assume Java's
  ``BufferedImage`` round-trip semantics + Java's ImageIO PNG decoder; in
  pypdfbox the equivalent is :class:`PNGConverter.convert_png_image` →
  :class:`LosslessFactory`, which is exercised end-to-end against
  pillow-generated fixtures by
  ``tests/pdmodel/graphics/image/test_png_converter_coverage.py`` (see
  ``test_check_converter_state_accepts_populated_state``,
  ``test_convert_png_returns_image`` etc.). Adding a fresh raw-byte
  fixture per upstream PNG would duplicate that coverage without
  contributing to parity, so we restrict the port to the helper-level
  tests below.
"""

from __future__ import annotations

import zlib

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.graphics.image.png_converter import (
    Chunk,
    PNGConverter,
    _PNGConverterState,
)

# ---------------------------------------------------------------------------
# testChunkSane — Java line 320-341.
# ---------------------------------------------------------------------------


def test_chunk_sane() -> None:
    # Java: assertTrue(PNGConverter.checkChunkSane(null));
    assert PNGConverter.check_chunk_sane(None) is True

    chunk = Chunk()
    chunk.bytes_ = b"IHDRsomedummyvaluesDummyValuesAtEnd"
    chunk.length = 19
    assert len(chunk.bytes_) == 35

    # Java: assertEquals("IHDRsomedummyvalues", new String(chunk.getData()));
    # ``start`` defaults to 0, so ``get_data`` slices [0:19] from the buffer.
    assert chunk.get_data() == b"IHDRsomedummyvalues"

    # Java: assertFalse(PNGConverter.checkChunkSane(chunk));  // start == 0 < 4
    assert PNGConverter.check_chunk_sane(chunk) is False

    chunk.start = 4
    # Java: assertEquals("somedummyvaluesDumm", new String(chunk.getData()));
    assert chunk.get_data() == b"somedummyvaluesDumm"
    # Still false — the CRC field is still 0 but the byte range now hashes to
    # a non-zero value.
    assert PNGConverter.check_chunk_sane(chunk) is False

    # Java: chunk.crc = -1729802258; → unsigned 0x99EBC32E.
    chunk.crc = -1729802258 & 0xFFFFFFFF
    assert PNGConverter.check_chunk_sane(chunk) is True

    # Java: chunk.start = 6;  → CRC range shifts → fails.
    chunk.start = 6
    assert PNGConverter.check_chunk_sane(chunk) is False

    # Java: chunk.length = 60;  → start + length > bytes.length → fails.
    chunk.length = 60
    assert PNGConverter.check_chunk_sane(chunk) is False


# ---------------------------------------------------------------------------
# testCheckConverterState — Java line 257-318.
# ---------------------------------------------------------------------------


def test_check_converter_state() -> None:
    # Java: assertFalse(PNGConverter.checkConverterState(null));
    assert PNGConverter.check_converter_state(None) is False

    state = _PNGConverterState()
    # Java: PNGConverterState with no IHDR → false.
    assert PNGConverter.check_converter_state(state) is False

    # Build an invalid (zero-length) chunk and a valid 16-byte one with a
    # CRC matching the 12 zero-bytes that would precede the data slice.
    invalid_chunk = Chunk()
    invalid_chunk.bytes_ = b""
    assert PNGConverter.check_chunk_sane(invalid_chunk) is False

    valid_chunk = Chunk()
    valid_chunk.bytes_ = bytes(16)
    valid_chunk.start = 4
    valid_chunk.length = 8
    valid_chunk.crc = 2077607535  # = zlib.crc32(bytes(12))
    assert PNGConverter.check_chunk_sane(valid_chunk) is True

    # Invalid IHDR → still false.
    state.ihdr = invalid_chunk
    assert PNGConverter.check_converter_state(state) is False
    # Adding a valid IDAT doesn't fix the broken IHDR.
    state.idats = [valid_chunk]
    assert PNGConverter.check_converter_state(state) is False
    # Replace IHDR with the valid chunk → true.
    state.ihdr = valid_chunk
    assert PNGConverter.check_converter_state(state) is True
    # Empty IDATs → false.
    state.idats = []
    assert PNGConverter.check_converter_state(state) is False
    # Restore a single valid IDAT → true again.
    state.idats = [valid_chunk]
    assert PNGConverter.check_converter_state(state) is True

    for attr in ("plte", "chrm", "trns", "iccp", "srgb", "gama"):
        # Invalid optional chunk → false.
        setattr(state, attr, invalid_chunk)
        assert PNGConverter.check_converter_state(state) is False, (
            f"invalid {attr} should fail"
        )
        # Restoring it to the valid chunk → true.
        setattr(state, attr, valid_chunk)
        assert PNGConverter.check_converter_state(state) is True, (
            f"valid {attr} should pass"
        )

    # Java: state.IDATs = Arrays.asList(validChunk, invalidChunk);
    state.idats = [valid_chunk, invalid_chunk]
    assert PNGConverter.check_converter_state(state) is False


# ---------------------------------------------------------------------------
# testCRCImpl — Java line 343-349.
# ---------------------------------------------------------------------------


def test_crc_impl() -> None:
    b1 = b"Hello World!"
    # Java: assertEquals(472456355, PNGConverter.crc(b1, 0, b1.length));
    assert PNGConverter.crc(b1, 0, len(b1)) == 472456355
    # Java: assertEquals(-632335482, PNGConverter.crc(b1, 2, b1.length - 4));
    # Upstream's Java ``int`` wraps signed; Python returns the unsigned
    # value, so we compare modulo 2**32.
    expected = -632335482 & 0xFFFFFFFF
    assert PNGConverter.crc(b1, 2, len(b1) - 4) == expected

    # Cross-check that ``crc`` matches ``zlib.crc32`` (PDFBox's
    # implementation is a hand-rolled equivalent; aligning here pins the
    # upstream parity).
    assert PNGConverter.crc(b1, 0, len(b1)) == zlib.crc32(b1)


# ---------------------------------------------------------------------------
# testMapPNGRenderIntent — Java line 351-360.
# ---------------------------------------------------------------------------


def test_map_png_render_intent() -> None:
    assert PNGConverter.map_png_render_intent(0) == COSName.get_pdf_name("Perceptual")
    assert PNGConverter.map_png_render_intent(1) == COSName.get_pdf_name(
        "RelativeColorimetric"
    )
    assert PNGConverter.map_png_render_intent(2) == COSName.get_pdf_name("Saturation")
    assert PNGConverter.map_png_render_intent(3) == COSName.get_pdf_name(
        "AbsoluteColorimetric"
    )
    assert PNGConverter.map_png_render_intent(-1) is None
    assert PNGConverter.map_png_render_intent(4) is None


# ---------------------------------------------------------------------------
# The image-conversion tests below are documented above as skipped; we
# keep a single stub assertion so the file lists as a deliberate
# parity-aware port rather than a partial translation.
# ---------------------------------------------------------------------------


def test_image_conversion_tests_documented_skip() -> None:
    pytest.skip(
        "Image-conversion tests need binary PNG fixtures (png.png, "
        "png_rgb_gamma.png, png_indexed_*.png, …) that pypdfbox does not "
        "bundle. Equivalent end-to-end coverage lives in "
        "tests/pdmodel/graphics/image/test_png_converter_coverage.py "
        "against Pillow-generated PNGs."
    )
