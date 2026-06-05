"""Port of ``org.apache.pdfbox.jbig2.JBIG2ImageReader``.

The ``javax.imageio.ImageReader`` plugin entry point for JBIG2. Upstream extends
``javax.imageio.ImageReader``; Python's stdlib has no ``ImageReader`` base, so
the subset of the contract the JBIG2 plugin overrides is inlined here. The
``BufferedImage`` return of ``read`` maps to a PIL ``Image`` (the established
``BufferedImage`` analogue in this repo — see ``tools/imageio``); a
``WritableRaster`` (``read_raster``) maps to the packed scanline ``bytes``
produced by :meth:`Bitmaps.as_raster`.

API mappings (Java -> Python), following the in-repo conventions:

* ``IOException`` (input not set / decode failure) -> ``OSError``.
* ``IndexOutOfBoundsException`` (page index out of range) -> ``IndexError``.
* ``IIOMetadata`` -> not modelled (upstream's ``JBIG2ImageMetadata`` only wraps
  the page); :meth:`get_image_metadata` returns the :class:`JBIG2Page` so callers
  can read width/height/resolution off it, and :meth:`get_stream_metadata`
  returns ``None`` exactly as upstream.

The PDF ``/JBIG2Decode`` filter does NOT route through this reader; it lives for
``javax.imageio``-surface parity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.jbig2.image.bitmaps import Bitmaps
from pypdfbox.jbig2.jbig2_document import JBIG2Document
from pypdfbox.jbig2.jbig2_read_param import JBIG2ReadParam

if TYPE_CHECKING:
    from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
    from pypdfbox.jbig2.jbig2_globals import JBIG2Globals
    from pypdfbox.jbig2.jbig2_page import JBIG2Page


class JBIG2ImageReader:
    """ImageIO-style reader delegating to :class:`JBIG2Document`."""

    def __init__(self, originating_provider: object | None = None) -> None:
        # Mirrors ImageReader(ImageReaderSpi). Stored for parity; unused here.
        self.originating_provider = originating_provider
        self._document: JBIG2Document | None = None
        self._globals: JBIG2Globals | None = None
        self._input: ImageInputStream | None = None
        self._seek_forward_only = False
        self._ignore_metadata = False

    # --- ImageReader subset -------------------------------------------------

    def set_input(
        self,
        input_: ImageInputStream,
        seek_forward_only: bool = False,
        ignore_metadata: bool = False,
    ) -> None:
        """Set the source stream. Mirrors ``setInput`` — invalidates the document."""
        self._input = input_
        self._seek_forward_only = seek_forward_only
        self._ignore_metadata = ignore_metadata
        self._document = None

    def get_default_read_param(self) -> JBIG2ReadParam:
        """Mirror ``getDefaultReadParam`` (no-arg) -> a fresh 1x1/null param."""
        return JBIG2ReadParam()

    def _get_default_read_param(self, image_index: int) -> JBIG2ReadParam:
        """Mirror the private per-page ``getDefaultReadParam(int)``."""
        width = 1
        height = 1
        try:
            index = (
                image_index
                if image_index < self._get_document().get_amount_of_pages()
                else 0
            )
            width = self.get_width(index)
            height = self.get_height(index)
        except OSError:
            # Dimensions could not be determined. Returning read params.
            pass
        return JBIG2ReadParam(1, 1, 0, 0, (0, 0, width, height), (width, height))

    def get_width(self, image_index: int) -> int:
        """Mirror ``getWidth``."""
        return self._get_page(image_index).get_width()

    def get_height(self, image_index: int) -> int:
        """Mirror ``getHeight``."""
        return self._get_page(image_index).get_height()

    def get_image_metadata(self, image_index: int) -> JBIG2Page:
        """Mirror ``getImageMetadata``.

        Upstream returns a ``JBIG2ImageMetadata`` wrapping the page; that class
        only exposes the page's width/height/resolution, so the port returns the
        :class:`JBIG2Page` itself (those getters live on it directly).
        """
        return self._get_page(image_index)

    def get_image_types(self, image_index: int) -> list[str]:
        """Mirror ``getImageTypes``.

        Java yields a single ``ImageTypeSpecifier`` for ``TYPE_BYTE_INDEXED``;
        the Python image stack is Pillow, whose 1-bit analogue is mode ``"1"``.
        """
        return ["1"]

    def get_num_images(self, allow_search: bool) -> int:
        """Mirror ``getNumImages`` — page count if searching, else -1."""
        return self._get_document().get_amount_of_pages() if allow_search else -1

    def get_stream_metadata(self) -> None:
        """Mirror ``getStreamMetadata`` — this plugin records none."""
        return None

    def get_globals(self) -> JBIG2Globals | None:
        """Mirror ``getGlobals`` — the document's decoded global segments."""
        return self._get_document().get_global_segments()

    def read(
        self, image_index: int, param: JBIG2ReadParam | None = None
    ) -> object:
        """Decode page ``image_index`` to a PIL ``Image``. Mirrors ``read``."""
        if param is None:
            param = self._get_default_read_param(image_index)

        page = self._get_page(image_index)
        page_bitmap = page.get_bitmap()
        return Bitmaps.as_buffered_image(page_bitmap, param, None)

    def can_read_raster(self) -> bool:
        """Mirror ``canReadRaster`` — always ``True``."""
        return True

    def read_raster(
        self, image_index: int, param: JBIG2ReadParam | None = None
    ) -> bytes:
        """Decode page ``image_index`` to packed raster bytes. Mirrors ``readRaster``.

        Java returns a ``Raster``; the Python analogue is the packed,
        polarity-inverted scanline ``bytes`` of the unscaled raster (the
        ``DataBufferByte`` content).
        """
        if param is None:
            param = self._get_default_read_param(image_index)

        page = self._get_page(image_index)
        page_bitmap = page.get_bitmap()
        return Bitmaps.as_raster(page_bitmap, param, None)

    def process_globals(
        self, globals_input_stream: ImageInputStream
    ) -> JBIG2Globals | None:
        """Decode and return the global segments. Mirrors ``processGlobals``."""
        doc = JBIG2Document(globals_input_stream)
        return doc.get_global_segments()

    def set_globals(self, globals_: JBIG2Globals | None) -> None:
        """Set the globals. Mirrors ``setGlobals`` — invalidates the document."""
        self._globals = globals_
        self._document = None

    # --- internals ----------------------------------------------------------

    def _get_document(self) -> JBIG2Document:
        if self._document is None:
            if self._input is None:
                raise OSError("Input not set.")
            self._document = JBIG2Document(self._input, self._globals)
        return self._document

    def _get_page(self, image_index: int) -> JBIG2Page:
        """Return the 0-based page. Mirrors the private ``getPage(int)``.

        :raises OSError: if the input wasn't set.
        :raises IndexError: if no page exists at that index (upstream
            ``IndexOutOfBoundsException``).
        """
        page = self._get_document().get_page(image_index + 1)
        if page is None:
            raise IndexError(
                f"Requested page at index={image_index} does not exist."
            )
        return page
