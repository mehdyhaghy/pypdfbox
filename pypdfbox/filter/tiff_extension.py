"""
TIFF tag-value constants used by the CCITT fax filter.

Mirrors ``org.apache.pdfbox.filter.TIFFExtension`` — a package-private
interface in upstream PDFBox that holds compression / photometric /
predictor / orientation / G3 / G4 / sample-format / YCbCr / fill-order
constant values from the TIFF 6.0 specification (and TwelveMonkeys'
TIFF extension set). The constants drive the synthetic TIFF wrapper
:mod:`pypdfbox.filter.ccitt_fax_decode` builds for libtiff and are kept
here as a single module so a direct port from PDFBox source can write::

    from pypdfbox.filter.tiff_extension import TIFFExtension

and resolve the symbols without re-deriving them.
"""

from __future__ import annotations

from typing import Final

__all__ = ["TIFFExtension"]


class TIFFExtension:
    """TIFF tag values used when decoding/encoding CCITT fax streams.

    Mirrors ``org.apache.pdfbox.filter.TIFFExtension``. All members are
    plain ``int`` constants — the class is never instantiated; it acts
    as a namespace exactly as the upstream Java interface does.
    """

    # ------------------------------------------------------------------
    # Compression (TIFF tag 259).
    # ------------------------------------------------------------------

    #: CCITT Modified Huffman RLE (TIFF 6.0 §11).
    COMPRESSION_CCITT_MODIFIED_HUFFMAN_RLE: Final[int] = 2
    #: CCITT T.4 / Group 3 Fax compression.
    COMPRESSION_CCITT_T4: Final[int] = 3
    #: CCITT T.6 / Group 4 Fax compression.
    COMPRESSION_CCITT_T6: Final[int] = 4
    #: LZW compression (was baseline; moved to extension over LZW IP issues).
    COMPRESSION_LZW: Final[int] = 5
    #: "Old-style" JPEG. Deprecated; retained for backwards compatibility.
    COMPRESSION_OLD_JPEG: Final[int] = 6
    #: JPEG (lossy) compression.
    COMPRESSION_JPEG: Final[int] = 7
    #: Adobe-style Deflate compression.
    COMPRESSION_ZLIB: Final[int] = 8
    #: PKZIP-style Deflate compression (custom tag value).
    COMPRESSION_DEFLATE: Final[int] = 32946

    # ------------------------------------------------------------------
    # Photometric interpretation (TIFF tag 262).
    # ------------------------------------------------------------------

    PHOTOMETRIC_SEPARATED: Final[int] = 5
    PHOTOMETRIC_YCBCR: Final[int] = 6
    PHOTOMETRIC_CIELAB: Final[int] = 8
    PHOTOMETRIC_ICCLAB: Final[int] = 9
    PHOTOMETRIC_ITULAB: Final[int] = 10

    # ------------------------------------------------------------------
    # Planar configuration (TIFF tag 284).
    # ------------------------------------------------------------------

    PLANARCONFIG_PLANAR: Final[int] = 2

    # ------------------------------------------------------------------
    # Predictor (TIFF tag 317).
    # ------------------------------------------------------------------

    PREDICTOR_HORIZONTAL_DIFFERENCING: Final[int] = 2
    PREDICTOR_HORIZONTAL_FLOATINGPOINT: Final[int] = 3

    # ------------------------------------------------------------------
    # Fill order (TIFF tag 266).
    # ------------------------------------------------------------------

    #: Default — most-significant-bit first within each byte.
    FILL_LEFT_TO_RIGHT: Final[int] = 1
    FILL_RIGHT_TO_LEFT: Final[int] = 2

    # ------------------------------------------------------------------
    # Sample format (TIFF tag 339).
    # ------------------------------------------------------------------

    SAMPLEFORMAT_INT: Final[int] = 2
    SAMPLEFORMAT_FP: Final[int] = 3
    SAMPLEFORMAT_UNDEFINED: Final[int] = 4

    # ------------------------------------------------------------------
    # YCbCr positioning (TIFF tag 531).
    # ------------------------------------------------------------------

    YCBCR_POSITIONING_CENTERED: Final[int] = 1
    YCBCR_POSITIONING_COSITED: Final[int] = 2

    # ------------------------------------------------------------------
    # Old-style JPEG processing (TIFF tag 512).
    # ------------------------------------------------------------------

    JPEG_PROC_BASELINE: Final[int] = 1
    JPEG_PROC_LOSSLESS: Final[int] = 14

    # ------------------------------------------------------------------
    # Ink set (TIFF tag 332).
    # ------------------------------------------------------------------

    #: For Photometric=5 (Separated) when the data is in CMYK.
    INKSET_CMYK: Final[int] = 1
    #: For Photometric=5 (Separated) with non-CMYK ink names.
    INKSET_NOT_CMYK: Final[int] = 2

    # ------------------------------------------------------------------
    # Orientation (TIFF tag 274).
    # ------------------------------------------------------------------

    ORIENTATION_TOPRIGHT: Final[int] = 2
    ORIENTATION_BOTRIGHT: Final[int] = 3
    ORIENTATION_BOTLEFT: Final[int] = 4
    ORIENTATION_LEFTTOP: Final[int] = 5
    ORIENTATION_RIGHTTOP: Final[int] = 6
    ORIENTATION_RIGHTBOT: Final[int] = 7
    ORIENTATION_LEFTBOT: Final[int] = 8

    # ------------------------------------------------------------------
    # Group 3 / Group 4 options (TIFF tags 292 / 293).
    # ------------------------------------------------------------------

    #: T4Options bit 0 — 2D coding.
    GROUP3OPT_2DENCODING: Final[int] = 1
    #: T4Options bit 1 — uncompressed mode permitted.
    GROUP3OPT_UNCOMPRESSED: Final[int] = 2
    #: T4Options bit 2 — fill-bits inserted before EOL codes.
    GROUP3OPT_FILLBITS: Final[int] = 4
    #: T4Options bit 3 — byte-aligned EOL codes (PDF /EncodedByteAlign).
    GROUP3OPT_BYTEALIGNED: Final[int] = 8
    #: T6Options bit 1 — uncompressed mode permitted.
    GROUP4OPT_UNCOMPRESSED: Final[int] = 2
    #: T6Options bit 2 — byte-aligned encoded data.
    GROUP4OPT_BYTEALIGNED: Final[int] = 4
