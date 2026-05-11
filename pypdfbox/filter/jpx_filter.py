"""JPX filter — upstream-named alias of :class:`JPXDecode`.

Mirrors ``org.apache.pdfbox.filter.JPXFilter``. The Java upstream **is**
the registered JPX filter implementation; in the Python port the heavy
lifting already lives in :class:`JPXDecode` (which wraps Pillow's
JPEG-2000 codec — library-first per project guidelines). This module
provides a thin subclass under the upstream class name so a direct port
from PDFBox Java sources can write::

    from pypdfbox.filter.jpx_filter import JPXFilter

and resolve the symbol without re-deriving it.
"""

from __future__ import annotations

from typing import BinaryIO

from pypdfbox.cos import COSDictionary

from .decode_result import DecodeResult
from .filter_factory import FilterFactory
from .jpx_decode import JPXDecode


class JPXFilter(JPXDecode):
    """Alias for :class:`JPXDecode` under the upstream class name."""

    def read_jpx(
        self,
        input_stream: BinaryIO,
        options=None,
        result: DecodeResult | None = None,
    ):
        """Read a JPEG-2000 (JPX) image into a decoded pixel buffer.

        Mirrors upstream's private ``readJPX()``: takes the encoded JPX
        bytes plus the optional decode options + result accumulator, and
        returns a decoded image. In pypdfbox the actual decode is handled
        by Pillow's JPEG-2000 plugin (already wrapped by :class:`JPXDecode`).
        """
        from io import BytesIO

        from PIL import Image

        data = input_stream.read()
        img = Image.open(BytesIO(data))
        img.load()
        if result is not None:
            # Upstream's readJPX populates the DecodeResult with the
            # discovered JPX colorspace metadata. Our parity surface just
            # leaves the result untouched when no metadata is available.
            pass
        return img

    def decode(
        self,
        encoded: BinaryIO,
        decoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> DecodeResult:
        return super().decode(encoded, decoded, parameters, index)

    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
    ) -> None:
        # Upstream throws UnsupportedOperationException — mirror via the
        # parent's encode() which raises.
        super().encode(raw, encoded, parameters)


# Register the upstream-named subclass under the upstream long name so
# callers using `FilterFactory.get("JPXFilter")` get the same wrapper.
# Do *not* overwrite the existing `JPXDecode` registration.
try:
    if not FilterFactory.is_registered("JPXFilter"):
        FilterFactory.register("JPXFilter", JPXFilter())
except Exception:
    pass
