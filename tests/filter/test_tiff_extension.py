"""
Tests for :class:`pypdfbox.filter.tiff_extension.TIFFExtension`.

The class is a TIFF-tag-value namespace mirroring upstream
``org.apache.pdfbox.filter.TIFFExtension``. The values come straight from
the TIFF 6.0 specification (and the TwelveMonkeys TIFF extension tag
set used by PDFBox); we pin every member so a careless edit flips a
loud test failure rather than producing a malformed TIFF wrapper at
runtime.
"""

from __future__ import annotations

from pypdfbox.filter import TIFFExtension
from pypdfbox.filter.tiff_extension import TIFFExtension as DirectTIFFExtension


def test_tiff_extension_imports_match() -> None:
    assert TIFFExtension is DirectTIFFExtension


def test_compression_constants() -> None:
    assert TIFFExtension.COMPRESSION_CCITT_MODIFIED_HUFFMAN_RLE == 2
    assert TIFFExtension.COMPRESSION_CCITT_T4 == 3
    assert TIFFExtension.COMPRESSION_CCITT_T6 == 4
    assert TIFFExtension.COMPRESSION_LZW == 5
    assert TIFFExtension.COMPRESSION_OLD_JPEG == 6
    assert TIFFExtension.COMPRESSION_JPEG == 7
    assert TIFFExtension.COMPRESSION_ZLIB == 8
    assert TIFFExtension.COMPRESSION_DEFLATE == 32946


def test_photometric_constants() -> None:
    assert TIFFExtension.PHOTOMETRIC_SEPARATED == 5
    assert TIFFExtension.PHOTOMETRIC_YCBCR == 6
    assert TIFFExtension.PHOTOMETRIC_CIELAB == 8
    assert TIFFExtension.PHOTOMETRIC_ICCLAB == 9
    assert TIFFExtension.PHOTOMETRIC_ITULAB == 10


def test_planar_predictor_and_fill_constants() -> None:
    assert TIFFExtension.PLANARCONFIG_PLANAR == 2
    assert TIFFExtension.PREDICTOR_HORIZONTAL_DIFFERENCING == 2
    assert TIFFExtension.PREDICTOR_HORIZONTAL_FLOATINGPOINT == 3
    assert TIFFExtension.FILL_LEFT_TO_RIGHT == 1
    assert TIFFExtension.FILL_RIGHT_TO_LEFT == 2


def test_sample_format_and_ycbcr_constants() -> None:
    assert TIFFExtension.SAMPLEFORMAT_INT == 2
    assert TIFFExtension.SAMPLEFORMAT_FP == 3
    assert TIFFExtension.SAMPLEFORMAT_UNDEFINED == 4
    assert TIFFExtension.YCBCR_POSITIONING_CENTERED == 1
    assert TIFFExtension.YCBCR_POSITIONING_COSITED == 2


def test_jpeg_proc_and_inkset_constants() -> None:
    assert TIFFExtension.JPEG_PROC_BASELINE == 1
    assert TIFFExtension.JPEG_PROC_LOSSLESS == 14
    assert TIFFExtension.INKSET_CMYK == 1
    assert TIFFExtension.INKSET_NOT_CMYK == 2


def test_orientation_constants() -> None:
    assert TIFFExtension.ORIENTATION_TOPRIGHT == 2
    assert TIFFExtension.ORIENTATION_BOTRIGHT == 3
    assert TIFFExtension.ORIENTATION_BOTLEFT == 4
    assert TIFFExtension.ORIENTATION_LEFTTOP == 5
    assert TIFFExtension.ORIENTATION_RIGHTTOP == 6
    assert TIFFExtension.ORIENTATION_RIGHTBOT == 7
    assert TIFFExtension.ORIENTATION_LEFTBOT == 8


def test_group3_options_bit_layout() -> None:
    assert TIFFExtension.GROUP3OPT_2DENCODING == 0x1
    assert TIFFExtension.GROUP3OPT_UNCOMPRESSED == 0x2
    assert TIFFExtension.GROUP3OPT_FILLBITS == 0x4
    assert TIFFExtension.GROUP3OPT_BYTEALIGNED == 0x8


def test_group4_options_bit_layout() -> None:
    assert TIFFExtension.GROUP4OPT_UNCOMPRESSED == 0x2
    assert TIFFExtension.GROUP4OPT_BYTEALIGNED == 0x4
