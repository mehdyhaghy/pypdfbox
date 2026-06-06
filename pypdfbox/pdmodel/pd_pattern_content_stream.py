from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSName, COSStream

from .pd_abstract_content_stream import PDAbstractContentStream
from .pd_page_content_stream import PDPageContentStream
from .pd_resources import PDResources

if TYPE_CHECKING:
    from .graphics.pattern.pd_tiling_pattern import PDTilingPattern


class PDPatternContentStream(PDPageContentStream):
    """Content-stream writer for a tiling-pattern cell body. Mirrors
    ``org.apache.pdfbox.pdmodel.PDPatternContentStream``.

    Upstream is a thin subclass of ``PDAbstractContentStream`` whose
    constructor wires the writer to the pattern's content-stream output and
    its ``/Resources`` (PDPatternContentStream.java:36-39). A tiling
    pattern is NOT a form XObject, so this subclass cannot reuse the parent
    constructor's PDFormXObject branch — it sets up the buffered-writer
    state directly against the pattern's backing ``COSStream``.

    Numeric operands emit at most 4 fractional digits, matching upstream's
    ``PDAbstractContentStream`` parent (the page writer uses 5).
    """

    def __init__(self, pattern: PDTilingPattern) -> None:
        # Local import to avoid a top-level cycle through the pattern package.
        from .graphics.pattern.pd_tiling_pattern import PDTilingPattern

        if not isinstance(pattern, PDTilingPattern):
            raise TypeError(
                "PDPatternContentStream requires a PDTilingPattern; got "
                f"{type(pattern).__name__}"
            )
        cos = pattern.get_cos_object()
        if not isinstance(cos, COSStream):
            raise TypeError(
                "PDPatternContentStream requires a stream-backed "
                "PDTilingPattern (its content stream describes one tile cell)"
            )
        # Replicate the buffered-writer state the parent constructor sets up
        # for its PDFormXObject branch, but bound to the pattern's COSStream
        # and /Resources. We deliberately do not call ``super().__init__``
        # because that constructor only accepts a PDPage / PDFormXObject.
        self._document = None
        self._closed = False
        self._buffer = bytearray()
        self._compress = False
        self._reset_context = False
        # Upstream's PDPatternContentStream extends PDAbstractContentStream,
        # so numeric operands use 4 fractional digits, not the page's 5.
        self._max_fraction_digits = (
            PDAbstractContentStream.DEFAULT_MAX_FRACTION_DIGITS
        )
        self._in_text_mode = False
        self._target_stream = cos
        existing_res = pattern.get_resources()
        if existing_res is None:
            self._resources = PDResources()
            pattern.set_resources(self._resources)
        else:
            self._resources = existing_res
        self._pattern = pattern

    def close(self) -> None:
        """Flush the buffered operator bytes into the pattern's COSStream."""
        if self._closed:
            return
        self._closed = True
        data = bytes(self._buffer)
        if self._compress:
            with self._target_stream.create_output_stream(
                COSName.FLATE_DECODE  # type: ignore[attr-defined]
            ) as out:
                out.write(data)
        else:
            self._target_stream.set_raw_data(data)

    def get_resources(self) -> PDResources:
        """Return the pattern's ``/Resources`` dictionary the writer binds
        names against."""
        return self._resources


__all__ = ["PDPatternContentStream"]
