from __future__ import annotations

from typing import BinaryIO

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.input_stream_factory import InputStreamFactory


class DefaultInputStreamFactory(InputStreamFactory):
    """
    Mirrors ``org.apache.pdfbox.jbig2.io.DefaultInputStreamFactory``.

    Upstream this class is ``@Deprecated``: it picks a file-backed
    ``FileCacheImageInputStream`` (lower memory) falling back to a
    ``MemoryCacheImageInputStream`` on I/O failure, and its Javadoc tells
    callers to construct the appropriate ``ImageInputStream`` directly. The
    Python :class:`ImageInputStream` is always memory-backed (the JBIG2 filter
    payload is fully buffered before decoding), so this factory simply wraps the
    source into one. The deprecation is recorded here for parity; new code
    should construct :class:`ImageInputStream` directly.
    """

    def get_input_stream(
        self, is_: bytes | bytearray | memoryview | BinaryIO
    ) -> ImageInputStream:
        return ImageInputStream(is_)
