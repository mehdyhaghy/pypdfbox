from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream


class InputStreamFactory(ABC):
    """
    Mirrors ``org.apache.pdfbox.jbig2.io.InputStreamFactory``.

    Upstream this is an interface with a single method that wraps a
    ``java.io.InputStream`` into a ``javax.imageio.stream.ImageInputStream``.
    The Python port keeps the abstraction: implementations turn a binary,
    byte-oriented source into an :class:`ImageInputStream`.
    """

    @abstractmethod
    def get_input_stream(
        self, is_: bytes | bytearray | memoryview | BinaryIO
    ) -> ImageInputStream:
        """Wrap ``is_`` into an :class:`ImageInputStream`."""
        raise NotImplementedError
