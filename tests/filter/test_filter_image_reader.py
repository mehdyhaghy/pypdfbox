"""Hand-written tests for ``Filter.find_image_reader`` /
``Filter.find_raster_reader`` — Pillow-backed parity shims that mirror
upstream PDFBox's static ``Filter#findImageReader`` and
``Filter#findRasterReader`` (which delegate to ``javax.imageio.ImageIO``).
"""

from __future__ import annotations

import pytest

from pypdfbox.filter import Filter, MissingImageReaderException


class TestFindImageReader:
    def test_jpeg_returns_callable(self):
        # Pillow ships with the JPEG plugin enabled by default.
        reader = Filter.find_image_reader("JPEG", "no JPEG codec")
        assert callable(reader)

    def test_jpeg2000_returns_callable(self):
        # Pillow ships with the JPEG2000 plugin (OpenJPEG bridge).
        reader = Filter.find_image_reader("JPEG2000", "no JPEG2000 codec")
        assert callable(reader)

    def test_tiff_returns_callable(self):
        reader = Filter.find_image_reader("TIFF", "no TIFF codec")
        assert callable(reader)

    def test_lowercase_format_name_resolved(self):
        # Format names are case-folded to upper before lookup so
        # ``"jpeg"`` and ``"JPEG"`` resolve to the same factory.
        upper = Filter.find_image_reader("JPEG", "")
        lower = Filter.find_image_reader("jpeg", "")
        assert upper is lower

    def test_unknown_format_raises_missing(self):
        with pytest.raises(MissingImageReaderException) as exc:
            Filter.find_image_reader("XYZ_BOGUS", "for testing")
        # Upstream message format: "Cannot read FORMAT image: CAUSE".
        assert "Cannot read XYZ_BOGUS image" in str(exc.value)
        assert "for testing" in str(exc.value)

    def test_missing_image_reader_is_oserror(self):
        # The exception remains an OSError subclass (PDFBox extends
        # IOException; we map IOException → OSError per CLAUDE.md).
        with pytest.raises(OSError):
            Filter.find_image_reader("ZZZ_NOPE", "x")


class TestFindRasterReader:
    def test_jpeg_returns_callable(self):
        # ``find_raster_reader`` delegates to ``find_image_reader``;
        # the upstream Java distinction (``ImageReader.canReadRaster()``)
        # has no Pillow analog, so the two helpers must agree.
        reader = Filter.find_raster_reader("JPEG", "no JPEG codec")
        assert callable(reader)

    def test_unknown_format_raises_missing(self):
        with pytest.raises(MissingImageReaderException):
            Filter.find_raster_reader("UNKNOWN_FMT", "diagnostic")

    def test_matches_image_reader_for_jpeg(self):
        # The two helpers return the same plugin factory in our port.
        a = Filter.find_image_reader("JPEG", "")
        b = Filter.find_raster_reader("JPEG", "")
        assert a is b
