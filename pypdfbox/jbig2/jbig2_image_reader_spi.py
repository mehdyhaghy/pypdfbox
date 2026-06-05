"""Port of ``org.apache.pdfbox.jbig2.JBIG2ImageReaderSpi``.

The ``javax.imageio`` service-provider that registers the JBIG2 plugin. Python
has no ``ImageIO`` SPI registry, so this is a thin, behaviourally faithful port:
the constant metadata (vendor / version / names / suffixes / mime types) and the
two methods downstream code actually calls — :meth:`can_decode_input` (file-
header sniff per ISO/IEC 14492:2001 D.4.1) and :meth:`create_reader_instance`.
The class is kept for API-surface parity; the PDF ``/JBIG2Decode`` filter path
does not route through the SPI (it constructs :class:`JBIG2Document` directly).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
    from pypdfbox.jbig2.jbig2_image_reader import JBIG2ImageReader

LOG = logging.getLogger(__name__)


class JBIG2ImageReaderSpi:
    """Service-provider description for the JBIG2 image reader."""

    VENDOR = "Apache Software Foundation"
    VERSION = "1.4.1"
    READER_CLASS_NAME = "pypdfbox.jbig2.jbig2_image_reader.JBIG2ImageReader"
    NAMES = ("jbig2", "JBIG2")
    SUFFIXES = ("jb2", "jbig2", "JB2", "JBIG2")
    MIME_TYPES = ("image/x-jbig2", "image/x-jb2")

    # According to D.4.1: unique id string for jbig2 files. Only present in
    # native jbig2 data; missing when embedded in another file format (PDF).
    FILEHEADER_PREAMBLE = (0x97, 0x4A, 0x42, 0x32, 0x0D, 0x0A, 0x1A, 0x0A)

    WRITER_SPI_NAMES: tuple[str, ...] = ()

    SUPPORTS_STANDARD_STREAM_METADATE_FORMAT = False
    NATIVE_STREAM_METADATA_FORMAT_NAME = "JBIG2 Stream Metadata"
    NATIVE_STREAM_METADATA_FORMAT_CLASSNAME = "JBIG2Metadata"
    EXTRA_STREAM_METADATA_FORMAT_NAME = None
    EXTRA_STREAM_METADATA_FORMAT_CLASSNAME = None

    SUPPORTS_STANDARD_IMAGE_METADATA_FORMAT = False
    NATIVE_IMAGE_METADATA_FORMAT_NAME = "JBIG2 File Metadata"
    NATIVE_IMAGE_METADATA_FORMAT_CLASSNAME = "JBIG2Metadata"
    EXTRA_IMAGE_METADATA_FORMAT_NAME = None
    EXTRA_IMAGE_METADATA_FORMAT_CLASSNAME = None

    def can_decode_input(self, source: object) -> bool:
        """Whether the stream begins with the D.4.1 file-header preamble.

        Mirrors ``canDecodeInput``: marks the stream, reads the 8 preamble
        bytes, and (on a full match) resets to the mark. A non-stream source
        logs a warning and returns ``False``. As upstream, a mismatch returns
        ``False`` *without* resetting (the stream position is left advanced).
        """
        if source is None:
            raise ValueError("source must not be null")

        # Duck-type the ImageInputStream contract (mark/read/reset).
        if not (
            hasattr(source, "mark")
            and hasattr(source, "read")
            and hasattr(source, "reset")
        ):
            LOG.warning("source is not an ImageInputStream: %s", source)
            return False

        iis: ImageInputStream = source  # type: ignore[assignment]
        iis.mark()

        for expected in self.FILEHEADER_PREAMBLE:
            read = iis.read() & 0xFF
            if read != expected:
                return False

        iis.reset()
        return True

    def create_reader_instance(
        self, extension: object | None = None
    ) -> JBIG2ImageReader:
        """Instantiate a :class:`JBIG2ImageReader`. Mirrors ``createReaderInstance``."""
        from pypdfbox.jbig2.jbig2_image_reader import JBIG2ImageReader

        return JBIG2ImageReader(self)

    def get_description(self, locale: object | None = None) -> str:
        """Mirror ``getDescription`` — locale is accepted and ignored."""
        return "JBIG2 Image Reader"
