from __future__ import annotations

from typing import TYPE_CHECKING, BinaryIO

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources

from .pd_abstract_pattern import PDAbstractPattern

if TYPE_CHECKING:
    from pypdfbox.pdmodel.common.pd_stream import PDStream
    from pypdfbox.pdmodel.pd_resource_cache import PDResourceCache

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_PATTERN: COSName = COSName.get_pdf_name("Pattern")
_PATTERN_TYPE: COSName = COSName.get_pdf_name("PatternType")
_PAINT_TYPE: COSName = COSName.get_pdf_name("PaintType")
_TILING_TYPE: COSName = COSName.get_pdf_name("TilingType")
_BBOX: COSName = COSName.get_pdf_name("BBox")
_X_STEP: COSName = COSName.get_pdf_name("XStep")
_Y_STEP: COSName = COSName.get_pdf_name("YStep")
_RESOURCES: COSName = COSName.RESOURCES  # type: ignore[attr-defined]


class PDTilingPattern(PDAbstractPattern):
    """Tiling pattern (``/PatternType 1``). Mirrors PDFBox
    ``PDTilingPattern`` lite surface — backed by a ``COSStream`` since
    tiling patterns carry a content stream describing one cell.

    Lite: ``get_b_box`` returns the raw ``COSArray`` (typed
    ``PDRectangle`` wrapping is offered by callers when needed); the
    ``PDContentStream`` mixin (``get_contents`` / ``getContentsForRandomAccess``)
    is deferred to the contentstream parsing cluster."""

    # Upstream PDFBox spelling — keep both ``PAINT_TYPE_*`` (canonical) and
    # the older ``PAINT_*`` aliases for back-compat with earlier callers.
    PAINT_TYPE_COLORED: int = 1
    PAINT_TYPE_UNCOLORED: int = 2
    PAINT_COLORED: int = 1
    PAINT_UNCOLORED: int = 2

    # Upstream PDFBox spelling — ``TILING_TYPE_*`` (canonical) plus the
    # older shorter aliases.
    TILING_TYPE_CONSTANT_SPACING: int = 1
    TILING_TYPE_NO_DISTORTION: int = 2
    TILING_TYPE_CONSTANT_SPACING_AND_FASTER_TILING: int = 3
    TILING_CONSTANT_SPACING: int = 1
    TILING_NO_DISTORTION: int = 2
    TILING_CONSTANT_SPACING_FASTER_TILING: int = 3

    def __init__(
        self,
        stream: COSStream | None = None,
        *,
        resource_cache: PDResourceCache | None = None,
    ) -> None:
        if stream is None:
            stream = COSStream()
            super().__init__(stream)
            # Fresh stream gets Type/PatternType up front; upstream also
            # attaches an empty PDResources so Adobe Reader will render the
            # pattern (per the PDF spec /Resources is required).
            stream.set_item(_TYPE, _PATTERN)
            stream.set_int(_PATTERN_TYPE, PDAbstractPattern.TYPE_TILING_PATTERN)
            self.set_resources(PDResources())
        else:
            super().__init__(stream)
        # Upstream's two-arg ctor stashes the resource cache so that
        # ``getResources()`` can pass it to the new PDResources wrapper.
        self._resource_cache = resource_cache

    # ---------- /PatternType ----------

    def get_pattern_type(self) -> int:
        return PDAbstractPattern.TYPE_TILING_PATTERN

    # ---------- /PaintType ----------

    def get_paint_type(self) -> int:
        return self._dict.get_int(_PAINT_TYPE, 0)

    def set_paint_type(self, paint_type: int) -> None:
        self._dict.set_int(_PAINT_TYPE, paint_type)

    def is_colored(self) -> bool:
        """``True`` when ``/PaintType`` is 1 (colored tiling pattern). The
        pattern's content stream specifies its own colours, ignoring any
        colours supplied by the caller."""
        return self.get_paint_type() == PDTilingPattern.PAINT_TYPE_COLORED

    def is_uncolored(self) -> bool:
        """``True`` when ``/PaintType`` is 2 (uncolored tiling pattern). The
        pattern's content stream is colourless and a colour must be supplied
        by the caller via the ``/Pattern`` colour space."""
        return self.get_paint_type() == PDTilingPattern.PAINT_TYPE_UNCOLORED

    # ---------- /TilingType ----------

    def get_tiling_type(self) -> int:
        return self._dict.get_int(_TILING_TYPE, 0)

    def set_tiling_type(self, tiling_type: int) -> None:
        self._dict.set_int(_TILING_TYPE, tiling_type)

    def is_constant_spacing(self) -> bool:
        """``True`` when ``/TilingType`` is 1 (constant spacing — pattern
        cells may be distorted to fit the tile grid)."""
        return (
            self.get_tiling_type()
            == PDTilingPattern.TILING_TYPE_CONSTANT_SPACING
        )

    def is_no_distortion(self) -> bool:
        """``True`` when ``/TilingType`` is 2 (no distortion — spacing may
        vary slightly to avoid pattern-cell distortion)."""
        return (
            self.get_tiling_type()
            == PDTilingPattern.TILING_TYPE_NO_DISTORTION
        )

    def is_constant_spacing_and_faster_tiling(self) -> bool:
        """``True`` when ``/TilingType`` is 3 (constant spacing and faster
        tiling — pattern cells may be distorted by up to one device pixel
        to enable faster rendering)."""
        return (
            self.get_tiling_type()
            == PDTilingPattern.TILING_TYPE_CONSTANT_SPACING_AND_FASTER_TILING
        )

    # ---------- /BBox ----------

    def get_b_box(self) -> PDRectangle | None:
        """``/BBox`` as a typed ``PDRectangle``, or ``None`` when missing /
        not a 4-entry numeric array. Mirrors upstream
        ``PDTilingPattern.getBBox``."""
        value = self._dict.get_dictionary_object(_BBOX)
        if isinstance(value, COSArray) and value.size() >= 4:
            return PDRectangle.from_cos_array(value)
        return None

    def has_b_box(self) -> bool:
        """``True`` when ``/BBox`` is present as a 4-entry ``COSArray`` —
        i.e. ``get_b_box`` would return a ``PDRectangle`` rather than
        ``None``. Useful for tooling that wants to flag tiling-pattern
        dictionaries missing the spec-required ``/BBox`` entry."""
        value = self._dict.get_dictionary_object(_BBOX)
        return isinstance(value, COSArray) and value.size() >= 4

    def set_b_box(self, bbox: PDRectangle | COSArray | None) -> None:
        """Accepts a typed ``PDRectangle``, a raw ``COSArray``, or ``None``
        (clears the entry)."""
        if bbox is None:
            self._dict.remove_item(_BBOX)
            return
        if isinstance(bbox, PDRectangle):
            self._dict.set_item(_BBOX, bbox.to_cos_array())
            return
        if isinstance(bbox, COSArray):
            self._dict.set_item(_BBOX, bbox)
            return
        raise TypeError(
            "set_b_box expects PDRectangle, COSArray, or None; got "
            f"{type(bbox).__name__}"
        )

    # ---------- /XStep / /YStep ----------

    def get_x_step(self) -> float:
        return self._dict.get_float(_X_STEP, 0.0)

    def set_x_step(self, x_step: float) -> None:
        self._dict.set_float(_X_STEP, float(x_step))

    def get_y_step(self) -> float:
        return self._dict.get_float(_Y_STEP, 0.0)

    def set_y_step(self, y_step: float) -> None:
        self._dict.set_float(_Y_STEP, float(y_step))

    # ---------- content stream ----------

    def get_content_stream(self) -> PDStream:
        """Return the wrapped content stream as a ``PDStream``. Mirrors
        upstream ``PDTilingPattern.getContentStream`` — tiling patterns
        carry a content stream describing one tile cell."""
        from pypdfbox.pdmodel.common.pd_stream import PDStream  # noqa: PLC0415

        cos = self._dict
        if not isinstance(cos, COSStream):
            # Defensive — upstream casts unconditionally; we surface a
            # clearer error if a caller bypassed the typed ctor.
            raise TypeError(
                "PDTilingPattern is not backed by a COSStream — content "
                "stream access requires a stream-typed pattern dictionary"
            )
        return PDStream(cos)

    # ---------- PDContentStream surface ----------

    def get_contents(self) -> BinaryIO | None:
        """Decoded byte stream of the tile's content stream — mirrors
        upstream ``PDTilingPattern.getContents`` (a ``PDContentStream``
        method). Returns ``None`` when the underlying ``COSDictionary`` is
        not a stream (i.e. nothing to read)."""
        cos = self._dict
        if not isinstance(cos, COSStream):
            return None
        return cos.create_input_stream()

    def get_contents_for_random_access(self) -> BinaryIO | None:
        """Random-access view onto the *encoded* body — mirrors upstream
        ``PDTilingPattern.getContentsForRandomAccess`` (which returns a
        ``RandomAccessRead``). The Python port returns a fresh raw
        ``BinaryIO`` over the encoded bytes since our I/O layer treats
        ``BinaryIO`` itself as random-access (``seek``/``tell``)."""
        cos = self._dict
        if not isinstance(cos, COSStream):
            return None
        return cos.create_raw_input_stream()

    def get_contents_for_stream_parsing(self) -> BinaryIO | None:
        """Random-access content stream used by parsers.

        Mirrors upstream ``PDContentStream.getContentsForStreamParsing``,
        whose default implementation delegates to
        ``getContentsForRandomAccess``.
        """
        return self.get_contents_for_random_access()

    # ---------- /Resources ----------

    def get_resources(self) -> PDResources | None:
        value = self._dict.get_dictionary_object(_RESOURCES)
        if isinstance(value, COSDictionary):
            return PDResources(value, resource_cache=self._resource_cache)
        return None

    def set_resources(
        self, resources: PDResources | COSDictionary | None
    ) -> None:
        if resources is None:
            self._dict.remove_item(_RESOURCES)
            return
        target = (
            resources.get_cos_object()
            if isinstance(resources, PDResources)
            else resources
        )
        self._dict.set_item(_RESOURCES, target)


__all__ = ["PDTilingPattern"]
