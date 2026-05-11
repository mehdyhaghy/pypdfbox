"""``MetaUtil`` class port — XML metadata pretty-printer for debug log lines.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/imageio/MetaUtil.java
    (lines 36-81)

The Java implementation relies on JAXP. We use stdlib ``xml.etree`` for
the pretty-print; the behaviour is debug-only, so a small impedance is
acceptable.
"""
from __future__ import annotations

import logging
from typing import Any
from xml.dom.minidom import parseString

LOG = logging.getLogger(__name__)

SUN_TIFF_FORMAT = "com_sun_media_imageio_plugins_tiff_image_1.0"
JPEG_NATIVE_FORMAT = "javax_imageio_jpeg_image_1.0"
STANDARD_METADATA_FORMAT = "javax_imageio_1.0"


class MetaUtil:
    """Static-only utility, mirrors upstream final-class-with-private-ctor."""

    # Module-level constants are exposed as class attributes for parity.
    SUN_TIFF_FORMAT = SUN_TIFF_FORMAT
    JPEG_NATIVE_FORMAT = JPEG_NATIVE_FORMAT
    STANDARD_METADATA_FORMAT = STANDARD_METADATA_FORMAT

    def __new__(cls) -> MetaUtil:  # pragma: no cover — mirrors private ctor
        raise TypeError("MetaUtil is a static-only utility")

    @staticmethod
    def debug_log_metadata(metadata: Any, fmt: str) -> None:
        """Mirror of upstream package-private ``debugLogMetadata``."""
        if not LOG.isEnabledFor(logging.DEBUG):
            return
        try:
            xml_str = (
                metadata.to_xml(fmt) if hasattr(metadata, "to_xml")
                else str(metadata)
            )
            pretty = parseString(xml_str).toprettyxml(indent="  ")
            LOG.debug("\n%s", pretty)
        except Exception as ex:  # noqa: BLE001
            LOG.error(ex, exc_info=ex)
