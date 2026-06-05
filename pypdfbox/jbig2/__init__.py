"""Python port of the Apache-2.0 ``apache/pdfbox-jbig2`` decoder.

Mirrors the ``org.apache.pdfbox.jbig2`` package layout so that JBIG2-encoded
image streams (``/JBIG2Decode``) can be decoded permissively.
"""

from pypdfbox.jbig2.jbig2_image_reader import JBIG2ImageReader
from pypdfbox.jbig2.jbig2_image_reader_spi import JBIG2ImageReaderSpi
from pypdfbox.jbig2.jbig2_read_param import JBIG2ReadParam

__all__ = [
    "JBIG2ImageReader",
    "JBIG2ImageReaderSpi",
    "JBIG2ReadParam",
]
